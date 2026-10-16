from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    file: str
    methodology: str
    template_fields: list[str] = Field(default_factory=list)


class StageDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1, le=10)
    phase: str
    name: str
    objective: str
    tools: list[str] = Field(default_factory=list)


class RouteDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    version: str
    stages: list[StageDefinition]
    tools: list[ToolDefinition]

    @model_validator(mode="after")
    def identifiers_are_unique(self) -> RouteDefinition:
        stage_ids = [stage.id for stage in self.stages]
        tool_ids = [tool.id for tool in self.tools]
        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError("La ruta contiene etapas repetidas")
        if len(tool_ids) != len(set(tool_ids)):
            raise ValueError("La ruta contiene herramientas repetidas")
        return self


@dataclass(frozen=True)
class KnowledgeIssue:
    code: str
    detail: str


PROMPT_CARD_LIMIT = 7000  # caracteres: deja sitio al resto del prompt en 8.192 tokens

_SECTION_HEADINGS = {
    "what": r"(?:Qu[eé] es|TL;DR)",  # la guía de trabajo de campo abre con un resumen
    "when": r"Cu[aá]ndo(?: se usa| usarla)",
    "how": r"C[oó]mo se usa",
}


def card_section(card: str, section: str) -> str:
    """Contenido bajo el encabezado de segundo nivel pedido, sin notas de borrador (`> …`)."""
    match = re.search(
        rf"^##[ \t]*{_SECTION_HEADINGS[section]}[^\n]*\n(.*?)(?=^##[ \t]|\Z)",
        card.replace("\r\n", "\n"),
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return ""
    lines = [line.rstrip() for line in match.group(1).splitlines()]
    kept = [line for line in lines if not line.lstrip().startswith(">")]
    text = "\n".join(kept).strip()
    # Las secciones de una línea se devuelven sin saltos; las listas conservan su formato.
    return text if section == "how" or text.startswith("-") else " ".join(text.split())


class KnowledgeCatalog:
    def __init__(self, route_path: Path):
        self.route_path = Path(route_path).resolve()
        raw = json.loads(self.route_path.read_text(encoding="utf-8"))
        self.route = RouteDefinition.model_validate(raw)
        self._base = self.route_path.parent.parent
        self._stages = {stage.id: stage for stage in self.route.stages}
        self._tools = {tool.id: tool for tool in self.route.tools}

    def validate(self) -> list[KnowledgeIssue]:
        issues: list[KnowledgeIssue] = []
        for stage in self.route.stages:
            for tool_id in stage.tools:
                if tool_id not in self._tools:
                    issues.append(
                        KnowledgeIssue(
                            code="unknown_tool",
                            detail=(
                                f"Etapa {stage.id} referencia la herramienta "
                                f"inexistente {tool_id!r}"
                            ),
                        )
                    )
        for tool in self.route.tools:
            path = self._tool_path(tool)
            if not path.is_file():
                issues.append(
                    KnowledgeIssue(
                        code="missing_file",
                        detail=f"La ficha {tool.id!r} no existe en {path}",
                    )
                )
        return issues

    def require_valid(self) -> None:
        issues = self.validate()
        if issues:
            details = "\n".join(f"- [{issue.code}] {issue.detail}" for issue in issues)
            raise ValueError(f"Biblioteca de conocimiento inválida:\n{details}")

    def stage(self, stage_id: int) -> StageDefinition:
        try:
            return self._stages[stage_id]
        except KeyError as exc:
            raise KeyError(f"La etapa {stage_id} no existe en la ruta") from exc

    def tool(self, tool_id: str) -> ToolDefinition:
        try:
            return self._tools[tool_id]
        except KeyError as exc:
            raise KeyError(f"La herramienta {tool_id!r} no existe en la biblioteca") from exc

    def tool_card(self, tool_id: str) -> str:
        tool = self.tool(tool_id)
        return self._tool_path(tool).read_text(encoding="utf-8-sig")

    def prompt_card(self, tool_id: str, limit: int = PROMPT_CARD_LIMIT) -> str:
        """La ficha tal como se le pasa al modelo. Una ficha larga (la guía de trabajo de
        campo tiene 26 mil caracteres) no cabe en la ventana del modelo local: se conservan
        en orden las secciones que quepan y se dice cuáles se omitieron."""
        card = self.tool_card(tool_id)
        if len(card) <= limit:
            return card
        head, *sections = re.split(r"(?m)^(?=## )", card)
        kept, skipped, size = [head], [], len(head)
        for section in sections:
            if size + len(section) <= limit:
                kept.append(section)
                size += len(section)
            else:
                skipped.append(section.splitlines()[0].lstrip("# ").strip())
        note = (
            "\n> Ficha resumida para el asistente. Secciones omitidas por extensión: "
            f"{', '.join(skipped)}.\n"
        )
        return "".join(kept).rstrip() + "\n" + note

    def route_index(self) -> str:
        data: dict[str, Any] = {
            "route_id": self.route.id,
            "route_name": self.route.name,
            "stages": [
                {
                    "id": stage.id,
                    "phase": stage.phase,
                    "name": stage.name,
                    "objective": stage.objective,
                    "tools": [
                        {
                            "id": tool_id,
                            "name": self.tool(tool_id).name,
                            # Para que el Orquestador elija por propósito y no solo por nombre.
                            "use_when": self.card_section(tool_id, "when"),
                        }
                        for tool_id in stage.tools
                    ],
                }
                for stage in self.route.stages
            ],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def card_section(self, tool_id: str, section: str) -> str:
        """Texto literal de una sección de la ficha: "what", "when" o "how". Vacío si no existe.

        Se usa para explicar o recomendar con las palabras de la ficha, sin pasar por el modelo.
        """
        return card_section(self.tool_card(tool_id), section)

    def tool_allowed_in_stage(self, tool_id: str, stage_id: int) -> bool:
        return tool_id in self.stage(stage_id).tools

    def _tool_path(self, tool: ToolDefinition) -> Path:
        candidate = (self._base / tool.file).resolve()
        if self._base not in candidate.parents:
            raise ValueError(f"Ruta de ficha fuera de la biblioteca: {tool.file}")
        return candidate
