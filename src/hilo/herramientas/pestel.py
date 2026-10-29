from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Los seis factores de la ficha, en su orden. Coinciden con los `template_fields` de la ruta.
FACTORS = ("politico", "economico", "social", "tecnologico", "ecologico", "legal")
FACTOR_NAMES = {
    "politico": "Político", "economico": "Económico", "social": "Social",
    "tecnologico": "Tecnológico", "ecologico": "Ecológico", "legal": "Legal",
}
MAX_ITEMS = 8  # por factor; la ficha pide 2–3
MAX_PRIORITY = 5  # la ficha pide priorizar entre 3 y 5


class PestelItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    text: str = Field(min_length=1, max_length=240, pattern=r"\S")
    # Vacío mientras la persona no decide: el paso 3 de la ficha va después de identificar.
    kind: Literal["", "oportunidad", "amenaza"] = ""
    source: str = Field(default="", max_length=500)
    priority: bool = False


class PestelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    version: int = Field(ge=0)
    challenge: str = Field(min_length=1, max_length=500, pattern=r"\S")
    politico: list[PestelItem] = Field(default_factory=list, max_length=MAX_ITEMS)
    economico: list[PestelItem] = Field(default_factory=list, max_length=MAX_ITEMS)
    social: list[PestelItem] = Field(default_factory=list, max_length=MAX_ITEMS)
    tecnologico: list[PestelItem] = Field(default_factory=list, max_length=MAX_ITEMS)
    ecologico: list[PestelItem] = Field(default_factory=list, max_length=MAX_ITEMS)
    legal: list[PestelItem] = Field(default_factory=list, max_length=MAX_ITEMS)

    @model_validator(mode="after")
    def check_items(self) -> PestelUpdate:
        items = [item for factor in FACTORS for item in getattr(self, factor)]
        if len({item.id for item in items}) != len(items):
            raise ValueError("Hay elementos con el mismo identificador")
        if sum(item.priority for item in items) > MAX_PRIORITY:
            raise ValueError(f"Se pueden priorizar hasta {MAX_PRIORITY} elementos")
        return self


def empty_pestel() -> dict:
    return {"challenge": "", **{factor: [] for factor in FACTORS}, "version": 0,
            "updated_at": None}


def context_lines(pestel: dict) -> list[str]:
    """El PESTEL del equipo, en frases para el contexto del agente. Es un borrador: lo que
    alguien anotó, no un hecho comprobado."""
    if not pestel.get("challenge"):
        return []
    lines = [f"PESTEL (borrador del equipo, no verificado): reto analizado: "
             f"{pestel['challenge']}"]
    for factor in FACTORS:
        items = pestel.get(factor) or []
        if not items:
            lines.append(f"Factor {FACTOR_NAMES[factor]}: sin elementos todavía")
            continue
        for item in items:
            details = [item["kind"] or "sin marcar como oportunidad o amenaza"]
            if item["priority"]:
                details.append("prioritario")
            details.append(
                f"origen declarado: {item['source']}" if item["source"] else "sin fuente"
            )
            lines.append(f"Factor {FACTOR_NAMES[factor]}: {item['text']} ({'; '.join(details)})")
    return lines
