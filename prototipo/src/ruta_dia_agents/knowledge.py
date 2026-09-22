from __future__ import annotations

import json
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
                        {"id": tool_id, "name": self.tool(tool_id).name}
                        for tool_id in stage.tools
                    ],
                }
                for stage in self.route.stages
            ],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def tool_allowed_in_stage(self, tool_id: str, stage_id: int) -> bool:
        return tool_id in self.stage(stage_id).tools

    def _tool_path(self, tool: ToolDefinition) -> Path:
        candidate = (self._base / tool.file).resolve()
        if self._base not in candidate.parents:
            raise ValueError(f"Ruta de ficha fuera de la biblioteca: {tool.file}")
        return candidate
