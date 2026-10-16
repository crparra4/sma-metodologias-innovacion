from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Lo que la ficha pide anotar en cada etapa, más la emoción (una cara de 1 a 5) y si la
# etapa es crítica: la ficha manda buscar oportunidades «en las etapas más críticas».
LANES = ("acciones", "contacto", "dolores", "oportunidades")
LANE_NAMES = {
    "acciones": "Acciones", "contacto": "Puntos de contacto", "dolores": "Dolores",
    "oportunidades": "Oportunidades de mejora",
}
EMOTIONS = {1: "muy mal", 2: "mal", 3: "neutral", 4: "bien", 5: "muy bien"}
MAX_STAGES = 8
MAX_NOTES = 6  # por fila de una etapa


class JourneyNote(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    text: str = Field(min_length=1, max_length=240, pattern=r"\S")


class JourneyStage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=60, pattern=r"\S")
    emotion: int = Field(default=0, ge=0, le=5)  # 0: sin marcar
    critical: bool = False
    acciones: list[JourneyNote] = Field(default_factory=list, max_length=MAX_NOTES)
    contacto: list[JourneyNote] = Field(default_factory=list, max_length=MAX_NOTES)
    dolores: list[JourneyNote] = Field(default_factory=list, max_length=MAX_NOTES)
    oportunidades: list[JourneyNote] = Field(default_factory=list, max_length=MAX_NOTES)


class JourneyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    version: int = Field(ge=0)
    user: str = Field(min_length=1, max_length=300, pattern=r"\S")
    scenario: str = Field(default="", max_length=300)
    stages: list[JourneyStage] = Field(default_factory=list, max_length=MAX_STAGES)

    @model_validator(mode="after")
    def check_ids(self) -> JourneyUpdate:
        ids = [stage.id for stage in self.stages]
        ids += [note.id for stage in self.stages for lane in LANES for note in getattr(stage, lane)]
        if len(set(ids)) != len(ids):
            raise ValueError("Hay etapas o notas con el mismo identificador")
        return self


def empty_journey() -> dict:
    return {"user": "", "scenario": "", "stages": [], "version": 0, "updated_at": None}


def context_lines(journey: dict) -> list[str]:
    """El recorrido del equipo, en frases para el contexto del agente. Dice qué falta en cada
    etapa para que la siguiente pregunta vaya a un hueco real. Es un borrador, no un hecho."""
    if not journey.get("user"):
        return []
    head = f"Customer Journey Map (borrador del equipo, no verificado): usuario: {journey['user']}"
    if journey.get("scenario"):
        head += f"; escenario: {journey['scenario']}"
    stages = journey.get("stages") or []
    if not stages:
        return [head, "Todavía no hay etapas: falta listar el recorrido en orden"]
    lines = [head, "Etapas en orden: " + " → ".join(stage["name"] for stage in stages)]
    for number, stage in enumerate(stages, 1):
        state = [f"emoción: {EMOTIONS[stage['emotion']]}" if stage["emotion"]
                 else "emoción: sin marcar"]
        if stage["critical"]:
            state.append("marcada como crítica")
        parts = []
        for lane in LANES:
            texts = [note["text"] for note in stage.get(lane) or []]
            parts.append(f"{LANE_NAMES[lane]}: {'; '.join(texts) if texts else 'sin anotar'}")
        lines.append(f"Etapa {number} «{stage['name']}» ({', '.join(state)}): {'. '.join(parts)}")
    return lines
