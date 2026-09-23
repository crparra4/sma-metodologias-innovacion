"""Diagnóstico del árbol de problemas en dos capas.

1. Reglas: comprobaciones exactas e instantáneas que no usan el modelo.
2. Contenido: el modelo local revisa si el problema central describe una solución. Debe
   citar literalmente el fragmento; el código descarta lo que no pueda comprobar.

El diagnóstico sugiere y no reescribe: nunca modifica el árbol.

Alcance decidido con Qwen3.5-4B (dos árboles, uno con errores y otro correcto, dos semillas,
septiembre de 2026):
- Problema redactado como solución: detectado siempre, sin alarmas falsas. Queda en el modelo.
- Causa redactada como falta de solución: pedida al modelo, la aplicaba a casi todas las
  causas (9 alarmas falsas). Es un patrón de redacción, así que la resuelve una regla exacta.
- Tarjeta en el lado equivocado y causa muy general: hasta 7 alarmas falsas por corrida;
  llegó a marcar las cinco tarjetas de un árbol correcto. Se retiraron: una alarma falsa haría
  que un novato mueva tarjetas correctas. Quedan pendientes para un modelo mayor.
- Razonamiento activado: 4 veces más lento (16 s frente a 4 s) sin más aciertos. Apagado.
- En cada iteración se pidió la evidencia antes que el veredicto: con el veredicto primero,
  el modelo decidía en el primer token y después razonaba en contra de su propia etiqueta.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TREE_TOOL_ID = "arbol-problemas"
MIN_QUOTE = 4

# Causas que nombran lo que falta en lugar de lo que ocurre.
_ABSENCE = re.compile(
    r"^(falta(n)?|no (hay|existe|existen|se cuenta con)|ausencia de|carencia de|sin)\b",
    re.IGNORECASE,
)


class ModelReview(BaseModel):
    """Contrato de salida del modelo: primero la evidencia, después la explicación.

    El modelo copia el fragmento del problema central que nombra una solución, o lo deja
    vacío; el veredicto lo deduce el código.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    problem_solution_fragment: str = Field(max_length=240)
    problem_explanation: str = Field(max_length=320)


class DiagnosisFinding(BaseModel):
    code: str
    layer: Literal["regla", "contenido"]
    severity: Literal["alta", "media", "baja"]
    target: str
    message: str


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _sentence(text: str) -> str:
    """Si la explicación quedó cortada por el límite de salida, termina en la última
    frase completa en vez de mostrar media palabra."""
    text = text.strip()
    if not text or text[-1] in ".!?…":
        return text
    end = max(text.rfind(". "), text.rfind("? "), text.rfind("! "))
    return text[: end + 1] if end > 0 else text.rstrip(" ,;:") + "…"


def rule_findings(tree: dict) -> list[DiagnosisFinding]:
    """Lo que se puede afirmar sin interpretar: se calcula con exactitud."""
    causes, effects = tree.get("causes", []), tree.get("effects", [])
    findings: list[DiagnosisFinding] = []

    def add(code, severity, target, message):
        findings.append(DiagnosisFinding(
            code=code, layer="regla", severity=severity, target=target, message=message,
        ))

    if not causes:
        add("carril_vacio", "alta", "causes",
            "Todavía no hay causas. Sin ellas, el árbol no explica por qué ocurre el problema.")
    if not effects:
        add("carril_vacio", "alta", "effects",
            "Todavía no hay efectos. Sin ellos no queda claro por qué vale la pena "
            "resolver el problema.")

    nodes = [*causes, *effects]
    unsourced = [node for node in nodes if not node.get("source", "").strip()]
    if unsourced:
        add("sin_fuente", "media", "tree",
            f"{len(unsourced)} de {len(nodes)} tarjetas todavía no registran de dónde salen. "
            "Contrasta al menos las causas principales antes de avanzar.")

    if causes and not any(node.get("parent") for node in causes):
        add("sin_causa_de_fondo", "media", "causes",
            "Ninguna causa baja a su causa de fondo. Pregunta «¿y por qué ocurre eso?» "
            "sobre las causas principales y anida la respuesta.")

    for node in causes:
        if _ABSENCE.match(node.get("text", "").strip()):
            add("falta_de_solucion", "media", node["id"],
                "Nombra lo que falta en lugar de lo que ocurre, y así ya anticipa la solución. "
                "Describe la situación que produce esa ausencia.")

    seen: set[str] = set()
    for node in nodes:
        key = _normalize(node.get("text", ""))
        if key in seen:
            add("repetida", "media", node["id"], "Repite el texto de otra tarjeta del árbol.")
        seen.add(key)
        if len(key.split()) < 3:
            add("muy_breve", "baja", node["id"],
                "Es muy breve para entender qué afirma. Escríbela como una frase completa.")
    return findings


def review_prompt(tree: dict, tool_card: str) -> str:
    """Solo lo que el modelo revisa: el problema central, con la ficha como criterio."""
    return f"""Revisa el problema central de este árbol usando los criterios de la ficha.

FICHA
{tool_card}

PROBLEMA CENTRAL
{tree['problem']}

Un problema describe una situación que ocurre; no nombra la solución. En
problem_solution_fragment copia literalmente la parte del problema central que nombra una
solución, herramienta, sistema o acción por implementar (verbos como implementar, crear,
desarrollar, adoptar). En problem_explanation explica en una sola frase, de máximo 25 palabras
y sin proponer soluciones, por qué eso es una solución y no una situación. Si el problema
central solo describe una situación, deja ambos campos vacíos."""


def grounded(review: ModelReview, tree: dict) -> tuple[list[DiagnosisFinding], int]:
    """Conserva la observación solo si el fragmento aparece literalmente en el problema."""
    fragment = _normalize(review.problem_solution_fragment)
    if not fragment:
        return [], 0
    if (
        len(fragment) < MIN_QUOTE
        or fragment not in _normalize(tree.get("problem", ""))
        or not review.problem_explanation
    ):
        return [], 1
    return [DiagnosisFinding(
        code="problema_como_solucion", layer="contenido", severity="alta",
        target="problem", message=_sentence(review.problem_explanation),
    )], 0


MAX_SUMMARY_LINES = 6
_SEVERITY_ORDER = {"alta": 0, "media": 1, "baja": 2}


def _snippet(text: str, limit: int = 60) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def summary_text(findings: list[DiagnosisFinding], tree: dict, version: int,
                 model_status: str) -> str:
    """Resumen breve para el contexto del agente: una frase fija por hallazgo, lo más grave
    primero. No usa las explicaciones del modelo, que son largas y varían entre corridas."""
    causes, effects = tree.get("causes", []), tree.get("effects", [])
    texts = {node["id"]: node.get("text", "") for node in (*causes, *effects)}
    nodes = len(causes) + len(effects)
    unsourced = sum(1 for node in (*causes, *effects) if not node.get("source", "").strip())

    def line(finding: DiagnosisFinding) -> str:
        card = f"«{_snippet(texts.get(finding.target, ''))}»"
        return {
            "problema_como_solucion": "el problema central describe una solución, no una situación",
            "carril_vacio": "no hay causas" if finding.target == "causes" else "no hay efectos",
            "sin_causa_de_fondo": "ninguna causa baja a su causa de fondo",
            "sin_fuente": f"{unsourced} de {nodes} tarjetas sin fuente",
            "falta_de_solucion": f"la causa {card} nombra lo que falta en lugar de lo que ocurre",
            "repetida": f"la tarjeta {card} repite otra",
            "muy_breve": f"la tarjeta {card} es demasiado breve",
        }.get(finding.code, _snippet(finding.message, 120))

    head = f"Diagnóstico del árbol (versión {version}, sugerencias no verificadas"
    head += ")" if model_status == "ok" else "; el problema central no se revisó)"
    lines = [line(item) for item in sorted(findings, key=lambda f: _SEVERITY_ORDER[f.severity])]
    if not lines:
        return f"{head}: sin observaciones."
    shown, rest = lines[:MAX_SUMMARY_LINES], len(lines) - MAX_SUMMARY_LINES
    text = f"{head}: {'; '.join(shown)}."
    return text + (f" Hay {rest} más de menor prioridad." if rest > 0 else "")
