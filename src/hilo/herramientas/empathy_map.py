from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Los seis bloques de la ficha, en su orden. En la ruta, «dolores» y «necesidades» se
# guardan desde el chat como `esfuerzos_N` y `resultados_N`.
BLOCKS = ("piensa_siente", "ve", "oye", "dice_hace", "dolores", "necesidades")
BLOCK_NAMES = {
    "piensa_siente": "¿Qué piensa y siente?", "ve": "¿Qué ve?", "oye": "¿Qué oye?",
    "dice_hace": "¿Qué dice y hace?", "dolores": "Dolores", "necesidades": "Necesidades",
}
MAX_ITEMS = 8  # por bloque


class EmpathyItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    text: str = Field(min_length=1, max_length=240, pattern=r"\S")
    # La ficha pide llenar con «lo que sabes/observas». Un mapa lleno de suposiciones es la
    # falla más común del método, así que cada nota dice de dónde sale.
    basis: Literal["", "observado", "supuesto"] = ""
    source: str = Field(default="", max_length=500)


class EmpathyMapUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    version: int = Field(ge=0)
    user: str = Field(min_length=1, max_length=300, pattern=r"\S")
    piensa_siente: list[EmpathyItem] = Field(default_factory=list, max_length=MAX_ITEMS)
    ve: list[EmpathyItem] = Field(default_factory=list, max_length=MAX_ITEMS)
    oye: list[EmpathyItem] = Field(default_factory=list, max_length=MAX_ITEMS)
    dice_hace: list[EmpathyItem] = Field(default_factory=list, max_length=MAX_ITEMS)
    dolores: list[EmpathyItem] = Field(default_factory=list, max_length=MAX_ITEMS)
    necesidades: list[EmpathyItem] = Field(default_factory=list, max_length=MAX_ITEMS)

    @model_validator(mode="after")
    def check_items(self) -> EmpathyMapUpdate:
        items = [item for block in BLOCKS for item in getattr(self, block)]
        if len({item.id for item in items}) != len(items):
            raise ValueError("Hay notas con el mismo identificador")
        return self


def empty_empathy_map() -> dict:
    return {"user": "", **{block: [] for block in BLOCKS}, "version": 0, "updated_at": None}


def context_lines(empathy_map: dict) -> list[str]:
    """El mapa del equipo, en frases para el contexto del agente. Es un borrador: «supuesto»
    y «sin marcar» no son observaciones, y así se le dice."""
    if not empathy_map.get("user"):
        return []
    lines = [f"Mapa de empatía (borrador del equipo, no verificado): usuario: "
             f"{empathy_map['user']}"]
    for block in BLOCKS:
        items = empathy_map.get(block) or []
        if not items:
            lines.append(f"Bloque {BLOCK_NAMES[block]}: sin notas todavía")
            continue
        for item in items:
            details = [item["basis"] or "sin marcar como observado o supuesto"]
            details.append(
                f"origen declarado: {item['source']}" if item["source"] else "sin fuente"
            )
            lines.append(f"Bloque {BLOCK_NAMES[block]}: {item['text']} ({'; '.join(details)})")
    return lines
