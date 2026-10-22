"""Hilo no pierde el lugar de la persona en la ruta (conversación real del 22 oct 2026).

Con el Customer Journey Map ya recorrido, la persona preguntó «¿qué es un árbol de problemas?» y
Hilo pasó el cuaderno al árbol; después, a «¿qué realizamos?» y «¿en qué ficha quedamos?»
respondió con el árbol, y al repetir el cierre el Verificador lo rechazó como pregunta repetida.
"""

import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ruta_dia_agents.audit import NullRecorder
from ruta_dia_agents.config import Settings
from ruta_dia_agents.contracts import ProjectState
from ruta_dia_agents.knowledge import KnowledgeCatalog
from ruta_dia_agents.langgraph_workflow import LangGraphRutaDia
from ruta_dia_agents.memory import NotebookMemory
from ruta_dia_agents.planificador import (
    RESPONDIDA,
    acepta_seguir,
    bloque_para_metodologo,
    partes_de,
    pide_resumen,
    planear,
)
from ruta_dia_agents.variantes import PlanificadorConControles

RETO = "Los afiliados de 60 a 75 años casi no usan la app para agendar sus citas."
CIERRE_CJM = (
    "Asistente: Ya pasamos por cada parte de **Customer Journey Map**. Te recomiendo seguir con "
    "**Trabajo de campo**, la herramienta que viene en la ruta. ¿Quieres revisar alguna parte "
    "o pasamos a Trabajo de campo?"
)


@pytest.mark.parametrize("mensaje", [
    "me podrias recordar que realizamos anteriormente ?",
    "me podrias recordar en ficha quedamos ?",
    "pero yo estoy observando que vamos custorme journe map?",
    "¿En qué vamos?",
    "¿Dónde quedamos la vez pasada?",
    "¿Qué hemos hecho hasta ahora?",
])
def test_these_ask_for_a_recap(mensaje):
    assert pide_resumen(mensaje)


@pytest.mark.parametrize("mensaje", [
    "¿Qué es un árbol de problemas?",
    "¿Qué vamos a poner en dolores?",
    "Hacen fila en la sede desde temprano y luego llaman.",
    "¿Eso cuenta como un dolor?",
])
def test_these_do_not(mensaje):
    assert not pide_resumen(mensaje)


def test_short_yes_accepts_moving_on():
    assert acepta_seguir("Sí, dale") and acepta_seguir("listo")
    assert not acepta_seguir("¿sí?") and not acepta_seguir("Sí, la gente hace fila desde las 5 am")


def _cjm_recorrido() -> dict:
    return {"customer-journey": {"en_curso": "", "partes": {
        p.id: {"estado": RESPONDIDA, "texto": "x"} for p in partes_de("customer-journey")}}}


def _estado(**cambios) -> ProjectState:
    base = dict(notebook_id="n", stage=3, phase="Descubrimiento", active_tool="customer-journey",
                context={"question": RETO}, progreso=_cjm_recorrido(),
                completed_tools=["arbol-problemas"])
    return ProjectState(**{**base, **cambios})


def _grafo(seleccion: str, kind: str):
    """Grafo con el Planificador y un modelo falso que elige `seleccion`."""
    catalog = KnowledgeCatalog(Settings.from_env().route_path)

    def crear(**options):
        nombre = options["response_format"]["json_schema"]["name"]
        assert nombre == "RouteDecision", "solo debería llamarse al Orquestador"
        salida = {"selection": seleccion, "intent": "i", "kind": kind, "expertise": "novel",
                  "context_summary": "c", "reason": "r"}
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(salida)))],
            usage=None)

    client = Mock()
    client.chat.completions.create.side_effect = crear
    settings = replace(Settings.from_env(), base_url="http://127.0.0.1:18083/v1", api_key="t")
    runtime = PlanificadorConControles(settings, client=client)
    return LangGraphRutaDia(catalog, runtime, NullRecorder()), client


def test_explaining_another_tool_keeps_the_notebook_where_it_was(tmp_path):
    grafo, _ = _grafo("1:arbol-problemas", "explicacion")
    estado = _estado()
    mensaje = "me gustaria que dijieres que es un arbol de problemas?"
    resultado = grafo.handle_turn(mensaje, estado)

    assert "**Árbol de problemas.**" in resultado.message  # la explicación literal de la ficha
    assert "seguimos con **Customer Journey Map**, donde íbamos?" in resultado.message
    assert "Ya pasamos por cada parte" not in resultado.message
    assert "etapa 1" not in resultado.message  # sin aviso de etapa: no cambia de ficha
    assert not resultado.degraded
    assert resultado.progreso == estado.progreso

    memoria = NotebookMemory(tmp_path / "m.sqlite3")
    guardado = memoria.save_exchange(mensaje, resultado, estado)
    assert (guardado.active_tool, guardado.stage) == ("customer-journey", 3)


def test_a_recap_is_answered_from_the_notebook_without_the_model():
    grafo, client = _grafo("3:customer-journey", "trabajo")
    resultado = grafo.handle_turn("me podrias recordar que realizamos anteriormente ?", _estado())

    client.chat.completions.create.assert_not_called()
    assert resultado.message.startswith("Estás en la etapa 3, «Profundización y empatía».")
    assert "Vamos con **Customer Journey Map**." in resultado.message
    assert "Antes trabajamos: Árbol de problemas." in resultado.message
    assert "pasamos a **Trabajo de campo**?" in resultado.message
    assert resultado.handoff.active_tool == "customer-journey"
    assert resultado.verification.findings[0].code == "recap"


def test_the_closing_is_not_rejected_when_it_comes_twice():
    grafo, _ = _grafo("3:customer-journey", "trabajo")
    estado = _estado(recent_turns=["Usuario: Quiero seguir con el customer journey.", CIERRE_CJM])
    resultado = grafo.handle_turn("bueno y ahora que hago con esto", estado)

    assert not resultado.degraded and resultado.attempts == 1
    assert resultado.message.startswith("Seguimos en **Customer Journey Map**")
    assert "pasamos a **Trabajo de campo**?" in resultado.message


def test_yes_to_the_recommendation_moves_to_the_next_tool():
    grafo, _ = _grafo("3:mapa-empatia", "trabajo")
    cierre = CIERRE_CJM.replace("Customer Journey Map", "Mapa de empatía").replace(
        "Trabajo de campo", "Canvas de propuesta de valor")
    estado = _estado(active_tool="mapa-empatia", recent_turns=["Usuario: listo", cierre],
                     progreso={"mapa-empatia": {"en_curso": "", "partes": {
                         p.id: {"estado": RESPONDIDA, "texto": "x"}
                         for p in partes_de("mapa-empatia")}}})
    runtime, indice = grafo.runtime, grafo.catalog.route_index()
    handoff = runtime.planificar("Sí, dale", estado,
                                 runtime.orchestrate("Sí, dale", estado, indice), indice)
    assert (handoff.active_tool, handoff.stage) == ("canvas-propuesta-valor", 3)
    assert runtime.plan.intencion == "preguntar"  # empieza por su primera parte


def test_the_board_button_reopens_the_block_it_names():
    avance = {"en_curso": "", "partes": {p.id: {"estado": RESPONDIDA, "texto": "x"}
                                         for p in partes_de("mapa-empatia")}}
    plan = planear("mapa-empatia", avance,
                   "Quiero seguir con el mapa de empatía: bloque «¿Qué piensa y siente?».")
    assert plan.intencion == "preguntar" and plan.objetivo.id == "piensa_siente"
    bloque = bloque_para_metodologo(plan)
    assert "pidió volver a esta parte" in bloque
    assert "¿Qué piensa y siente?: «x»" not in bloque
