"""Notas de entrevista → post-its propuestos para el Customer Journey Map.

El modelo solo señala qué frases de las notas sirven y dónde irían. El código comprueba que
cada frase esté literal en el texto pegado y descarta la que no: así el mapa nunca recibe
algo que la persona entrevistada no dijo. Nada se guarda aquí; la persona acepta una por una.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from .journey import LANE_NAMES, LANES

MAX_TEXT = 1800  # caracteres por tanda: el modelo local es pequeño
MAX_PROPOSALS = 8
MIN_WORDS = 3
MAX_QUOTE = 240

LANE_HINTS = {
    "acciones": "algo que la persona hace",
    "contacto": "algo o alguien con lo que tiene contacto (un canal, un lugar, una persona)",
    "dolores": "algo que le molesta, le cuesta o le preocupa",
    "oportunidades": "algo que pide o que se podría mejorar",
}


class NotesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=20, max_length=MAX_TEXT)


def extraction_model(stage_count: int) -> type[BaseModel]:
    """Salida restringida: la etapa es un número que existe y la fila, una de las cuatro."""
    numbers = tuple(str(number) for number in range(1, stage_count + 1))
    item = create_model(
        "JourneyQuote",
        __config__=ConfigDict(extra="forbid", str_strip_whitespace=True),
        quote=(str, Field(max_length=MAX_QUOTE + 60)),
        # Antes de elegir la etapa, el modelo dice en qué momento ocurre la frase. Sin este
        # paso repartía las frases en orden, una etapa tras otra, sin mirar de qué hablaban.
        moment=(str, Field(max_length=80)),
        stage=(Literal.__getitem__(numbers), ...),
        lane=(Literal.__getitem__(LANES), ...),
    )
    return create_model(
        "JourneyQuotes",
        __config__=ConfigDict(extra="forbid"),
        items=(list[item], Field(default_factory=list, max_length=MAX_PROPOSALS)),
    )


def extraction_prompt(text: str, journey: dict) -> str:
    def described(stage: dict) -> str:
        known = [note["text"] for lane in LANES for note in stage.get(lane) or []][:3]
        return f"{stage['name']}" + (f" (ya se anotó: {'; '.join(known)})" if known else "")

    stages = "\n".join(
        f"{number}. {described(stage)}" for number, stage in enumerate(journey["stages"], 1)
    )
    lanes = "\n".join(f"- {lane}: {LANE_HINTS[lane]}" for lane in LANES)
    return f"""
Lee estas notas de una entrevista y elige las frases que sirven para un Customer Journey Map.

USUARIO DEL RECORRIDO: {journey['user']}
ESCENARIO: {journey.get('scenario') or 'sin definir'}

ETAPAS DEL RECORRIDO (usa su número):
{stages}

FILAS:
{lanes}

NOTAS DE LA ENTREVISTA:
\"\"\"
{text}
\"\"\"

Reglas:
- quote: copia la frase EXACTAMENTE como está en las notas, letra por letra. No la resumas,
  no la corrijas, no cambies ni una palabra. Una sola idea por frase, de 3 a 30 palabras.
- moment: en pocas palabras, qué está haciendo la persona cuando pasa eso.
- stage: el número de la etapa cuyo nombre corresponde a ese momento. Varias frases pueden
  ir a la misma etapa; no las repartas en orden.
- lane: la fila que mejor describe la frase. Si la frase es una queja, es dolores.
- Elige como máximo {MAX_PROPOSALS} frases, las más útiles. Si ninguna sirve, devuelve items vacío.
- No inventes nada que no esté en las notas.
""".strip()


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _find_literal(quote: str, text: str) -> str:
    """El fragmento tal como está escrito en las notas, o «» si no aparece. Tolera diferencias
    de espacios, mayúsculas y comillas o puntos en los bordes; no tolera palabras cambiadas."""
    words = quote.strip(" \t\n\"'«»“”.,;:").split()
    if len(words) < MIN_WORDS:
        return ""
    pattern = r"\s+".join(re.escape(word) for word in words)
    match = re.search(pattern, text, re.IGNORECASE)
    return " ".join(match.group(0).split()) if match else ""


def grounded_quotes(output: BaseModel, text: str, journey: dict) -> tuple[list[dict], int]:
    """Propuestas que pasan la comprobación y cuántas se descartaron."""
    stages = journey["stages"]
    existing = {
        _plain(note["text"]) for stage in stages for lane in LANES for note in stage.get(lane) or []
    }
    proposals: list[dict] = []
    seen: set[str] = set()
    discarded = 0
    for item in getattr(output, "items", []):
        literal = _find_literal(item.quote, text)
        index = int(item.stage) - 1
        key = _plain(literal)
        if not literal or len(literal) > MAX_QUOTE or not 0 <= index < len(stages):
            discarded += 1
            continue
        if key in seen or key in existing:
            continue  # repetida: no es un error del modelo, solo sobra
        seen.add(key)
        proposals.append({
            "quote": literal,
            "stage_id": stages[index]["id"],
            "lane": item.lane,
            "lane_name": LANE_NAMES[item.lane],
        })
    return proposals, discarded
