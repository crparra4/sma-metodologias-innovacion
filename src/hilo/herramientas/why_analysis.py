"""Análisis de 5 porqués que parte de una causa del árbol de problemas.

Reparto de trabajo:
- El agente formula cada «¿por qué?» y conduce la revisión de la cadena.
- El código registra cada respuesta tal como la escribió la persona (ya es el paso de la
  cadena: no hace falta que el modelo la extraiga), fija la herramienta mientras el análisis
  está en curso y conserva el vínculo con la tarjeta de origen.

Cinco respuestas no confirman una causa raíz. La persona revisa la cadena, elige la causa
candidata y decide si la incorpora al árbol; como el árbol admite dos niveles, se incorpora
solo la causa candidata, como causa de fondo de la tarjeta de partida.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TOOL_ID = "cinco-porques"
MAX_STEPS = 7
SUGGESTED_STEPS = 5
Status = Literal["en_curso", "cerrado", "descartado"]

# Respuestas que dicen que no se sabe: pasan a dudas por investigar, no a la cadena.
_UNKNOWN = re.compile(
    r"^\s*(no (lo )?s[eé]|tampoco( lo)? s[eé]|no sabr[ií]a|no tengo (idea|claro)"
    r"|no estoy segur[oa]|desconozco|ni idea)\b",
    re.IGNORECASE,
)
# Las reglas siguientes se aplican a la respuesta ya sin «porque» ni «creo que» (as_clause).
# Priman la precisión: ante la duda, la respuesta entra a la cadena y la persona la puede quitar.
# Respuestas tan generales que no se puede preguntar «¿por qué?» sobre ellas.
_VAGUE = re.compile(
    r"^((por|de) )?(muchas|varias|diversas|distintas|diferentes|tantas|mil) "
    r"(cosas|razones|causas|motivos|factores)\b"
    r"|^(s[ií]|as[ií] es|es as[ií]|depende|es complicado|por todo|de todo un poco)\W*$",
    re.IGNORECASE,
)
# Una herramienta que falta es una solución, no una causa (la misma regla del diagnóstico
# del árbol). Solo se marca si nombra una herramienta, para no atrapar «no hay tiempo».
_SOLUTION = re.compile(
    r"^(no (hemos|han|se ha|se han) (comprado|adquirido|contratado|implementado|instalado)\b"
    r"|(no (hay|tenemos|tienen|existe|existen|contamos con|se cuenta con)|falta(n)?( de)?"
    r"|ausencia de|carencia de|sin)\b.{0,40}?\b(herramienta|software|app|aplicaci[oó]n|sistema"
    r"|plataforma|licencia|tablero|dashboard|power ?bi|inteligencia artificial|ia|programa"
    r"|bot|crm|erp)s?\b)",
    re.IGNORECASE,
)
# En la revisión: la persona no ve ninguna conexión débil.
_NO_WEAK_LINK = re.compile(
    r"\b(todas|ninguna|todo bien|me parecen? bien|est[aá]n? bien)\b", re.IGNORECASE,
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class WhyStep(_Strict):
    text: str = Field(min_length=1, max_length=500, pattern=r"\S")
    evidence: str = Field(default="", max_length=500)


class WhyStart(_Strict):
    cause_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class WhyUpdate(_Strict):
    steps: list[WhyStep] | None = Field(default=None, max_length=MAX_STEPS)
    doubts: list[str] | None = Field(default=None, max_length=10)


class WhyClose(_Strict):
    candidate: str = Field(min_length=1, max_length=240, pattern=r"\S")


def is_unknown(message: str) -> bool:
    return bool(_UNKNOWN.match(message))


def _snippet(text: str, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


_LEADING = re.compile(
    r"^(porque|ya que|pues|creo que|pienso que|supongo que|tal vez|quiz[aá]s)\s+", re.IGNORECASE,
)


def as_clause(text: str) -> str:
    """Respuesta convertida en cláusula para preguntar por ella: sin «porque» ni «creo que»
    al inicio. «Creo que nunca se definió un formato» → «nunca se definió un formato»."""
    clause = re.sub(r"\s+", " ", text).strip().rstrip(".")
    while (stripped := _LEADING.sub("", clause)) != clause:
        clause = stripped
    if len(clause) > 1 and clause[1].islower():  # no tocar siglas como «KR» u «OKR»
        clause = clause[0].lower() + clause[1:]
    return clause


def last_link(analysis: dict) -> str:
    """Lo último afirmado en la cadena: sobre eso va el siguiente «¿por qué?»."""
    steps = analysis["steps"]
    return steps[-1]["text"] if steps else analysis["cause_text"]


def pending_question(analysis: dict) -> str:
    """Duda que queda cuando la persona no sabe responder el paso actual."""
    return f"¿Por qué ocurre «{_snippet(last_link(analysis), 90)}»?"


def is_question(message: str) -> bool:
    """Una pregunta no responde el «¿por qué?», salvo que empiece con «porque»."""
    return "?" in message and not re.match(r"^\W*porque\b", message, re.IGNORECASE)


def notice_of(analysis: dict) -> tuple[str, str]:
    """Lo que el código notó en el último mensaje: (tipo, texto del mensaje)."""
    kind, _, text = analysis.get("notice", "").partition("|")
    return kind, text


def apply_turn(analysis: dict, message: str) -> dict:
    """Decide qué hacer con un mensaje de la persona durante el análisis.

    Devuelve los campos que cambian: steps, doubts, awaiting_plan y notice. El aviso
    («notice») le dice al agente qué pasó con el mensaje, para que no pregunte en falso.
    Una respuesta general o que nombra una herramienta no entra a la cadena la primera
    vez; si la persona insiste, entra, porque la cadena es suya.
    """
    steps, doubts = list(analysis["steps"]), list(analysis["doubts"])
    text = message.strip()
    clause = as_clause(text)
    previous, _ = notice_of(analysis)
    result = {"steps": steps, "doubts": doubts, "awaiting_plan": False, "notice": ""}
    if analysis["awaiting_plan"] and doubts:
        doubts[-1] += " Plan: " + ("sin definir" if is_unknown(text) else text[:300])
    elif is_question(text):
        result["notice"] = f"pregunta|{text[:200]}"
    elif is_unknown(text):
        question = pending_question(analysis)
        if any(doubt.startswith(question) for doubt in doubts):
            result["notice"] = "sin_hipotesis|"  # ya se le pidió una hipótesis y no la tiene
        else:
            doubts.append(question)
            result["awaiting_plan"] = True
    elif _VAGUE.match(clause) and previous != "vaga":
        result["notice"] = f"vaga|{text[:200]}"
    elif _SOLUTION.match(clause) and previous != "solucion":
        result["notice"] = f"solucion|{text[:200]}"
    elif len(steps) < MAX_STEPS:
        steps.append({"text": text[:500], "evidence": ""})
    return result


def review_notice(message: str) -> str:
    """Aviso para un comentario durante la revisión de la cadena."""
    none = is_unknown(message) or _NO_WEAK_LINK.search(message)
    return "revision_ninguna|" if none else "revision|"


def _doubt_statement(doubt: str) -> str:
    """«¿Por qué ocurre «X»? Plan: Y» → «el motivo de «X» (plan: Y)»."""
    match = re.match(r"^¿Por qué ocurre (.+?)\?(?: Plan: (.*))?$", doubt)
    if not match:
        return doubt
    plan = f" (plan: {match.group(2)})" if match.group(2) else ""
    return f"el motivo de {match.group(1)}{plan}"


def context_text(analysis: dict) -> str:
    """Texto breve para el contexto del agente mientras el análisis está en curso."""
    steps = analysis["steps"]
    parts = [
        f"Análisis de 5 porqués en curso sobre la causa «{_snippet(analysis['cause_text'])}» "
        f"del problema «{_snippet(analysis['problem_text'])}».",
        "Cadena registrada: " + "; ".join(
            f"{index}) {_snippet(step['text'])}" for index, step in enumerate(steps, 1)
        ) + "." if steps else "Aún no hay respuestas registradas.",
    ]
    if analysis["doubts"]:
        parts.append(
            "Por investigar, ya registrado (no lo vuelvas a preguntar): "
            + "; ".join(_doubt_statement(doubt) for doubt in analysis["doubts"]) + "."
        )
    # Con el modelo pequeño, las instrucciones generales cedían ante el historial reciente;
    # el texto literal de la pregunta sí se sigue. Por eso cada estado lleva su pregunta exacta.
    clause = _snippet(as_clause(last_link(analysis)), 150)
    kind, said = notice_of(analysis)
    said = _snippet(said)
    paused = any(doubt.startswith(pending_question(analysis)) for doubt in analysis["doubts"])
    question = (
        f"«Aunque todavía no esté confirmado, ¿por qué crees que {clause}?»" if paused
        else f"«¿Por qué ocurre que {clause}?»"
    )
    # El Verificador exige exactamente una pregunta por respuesta, y las comillas anidadas
    # hacían que el modelo cortara el JSON: cada texto literal es una sola pregunta, sin anidar.
    finish = ("«¿Quieres seguir preguntando para cambiar algo de la cadena, o prefieres "
              "terminar y elegir cuál respuesta es la causa candidata?»")
    if analysis["reviewing"]:
        # review_turns cuenta los mensajes desde que empezó la revisión; el primero la abre.
        if analysis.get("review_turns", 1) <= 1:
            parts.append(
                "La persona pidió revisar la cadena. Pregúntale exactamente: «Mirando la cadena "
                "completa, ¿qué conexión entre dos respuestas te parece más débil y por qué?». "
                "No afirmes que ya es la causa raíz."
            )
        elif kind == "revision" and analysis["review_turns"] == 2:
            parts.append(
                "La persona ya respondió la pregunta de revisión: no la repitas. Pregúntale "
                "exactamente: «¿Qué otra razón, distinta de la que anotaste, podría explicar "
                "ese salto?». No afirmes que ya es la causa raíz."
            )
        else:
            parts.append(
                "La persona ya revisó la cadena: no repitas la pregunta de revisión. Dile "
                f"exactamente: {finish}"
            )
    elif analysis.get("awaiting_plan"):
        parts.append(
            "La persona no sabe todavía por qué ocurre "
            f"«{_snippet(last_link(analysis))}». No repitas esa pregunta. Pregúntale "
            "exactamente: «¿Qué podrías observar, o a quién podrías preguntarle, para "
            f"averiguar por qué {clause}?»"
        )
    elif kind == "pregunta":
        parts.append(
            f"La persona escribió una pregunta, no una respuesta: «{said}». No se anotó en la "
            "cadena. No la respondas con datos que no estén en este contexto (precios, "
            "cifras, nombres). Dile en una frase que esa pregunta queda fuera de este "
            f"análisis y pregúntale exactamente: {question}"
        )
    elif kind == "vaga":
        parts.append(
            f"La última respuesta, «{said}», es demasiado general y no se anotó en la cadena. "
            "Pregúntale exactamente: «De todo eso, ¿qué es lo que más pesa? Nombra una sola "
            "razón, lo más concreta posible.»"
        )
    elif kind == "solucion":
        parts.append(
            f"La última respuesta, «{said}», nombra una herramienta que falta: eso es una "
            "solución y todavía no explica la causa, así que no se anotó en la cadena. "
            "Pregúntale exactamente: «¿Qué dificultad concreta hay hoy que esa herramienta "
            "resolvería? Esa dificultad es la respuesta que buscamos.»"
        )
    elif kind == "sin_hipotesis":
        parts.append(
            "La persona tampoco tiene una idea de por qué ocurre "
            f"«{_snippet(last_link(analysis))}». No insistas. Dile exactamente: «Queda "
            "anotado como algo por investigar. ¿Prefieres revisar la cadena con lo que ya "
            "tienes o probar con otra razón?»"
        )
    elif paused:
        parts.append(
            f"La respuesta sobre «{_snippet(last_link(analysis))}» quedó por investigar. "
            f"Pregúntale exactamente: {question}. No le pidas hacer gestiones ahora."
        )
    elif len(steps) >= SUGGESTED_STEPS:
        parts.append(
            "Ya hay cinco respuestas: propón revisar la cadena antes de seguir. Cinco "
            "respuestas no confirman por sí solas una causa raíz."
        )
    else:
        parts.append(
            f"Siguiente paso: pregúntale exactamente: «¿Por qué ocurre que {clause}?». Es "
            "sobre la última respuesta: no vuelvas a preguntar por respuestas anteriores ni "
            "por la causa original."
        )
    return " ".join(parts)
