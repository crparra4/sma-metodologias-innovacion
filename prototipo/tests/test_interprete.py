import json
import re
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ruta_dia_agents.config import Settings
from ruta_dia_agents.contracts import ProjectState
from ruta_dia_agents.knowledge import KnowledgeCatalog
from ruta_dia_agents.variantes import (
    InterpreteAmpliado,
    InterpreteAparte,
    SoloControlesEnCodigo,
    aclaracion_breve,
)

DUDA = "Lo de las bolsas blanca, negra y verde, ¿eso cuenta como político?"
LECTURA = {
    "pregunta_de_la_persona": "¿eso cuenta como político?",
    "datos_aportados": ["separar en bolsa blanca, negra y verde"],
    "confundida": False,
}


def settings():
    return replace(Settings.from_env(), base_url="http://127.0.0.1:18083/v1", api_key="test")


@pytest.fixture
def catalog():
    return KnowledgeCatalog(Settings.from_env().route_path)


def cliente(kind: str, lectura_en_orquestador: bool, headings: list[str]):
    """Modelo falso: contesta según el contrato que se le pide y guarda lo que recibió."""
    recibidos: dict[str, str] = {}

    def crear(**options):
        nombre = options["response_format"]["json_schema"]["name"]
        recibidos[nombre] = options["messages"][-1]["content"]
        if nombre == "LecturaTurno":
            salida = LECTURA
        elif nombre == "RouteDecision":
            salida = {"selection": "1:pestel", "intent": "Trabajar PESTEL", "kind": kind,
                      "expertise": "novel", "context_summary": "Reto de reciclaje.",
                      "reason": "Pidió PESTEL."}
            if lectura_en_orquestador:
                salida = {**salida, **LECTURA}
        else:
            salida = {"message": "¿Qué otra norma conoces sobre el reciclaje en tu barrio?",
                      "tool_id": "pestel", "next_step": "Pedir otro elemento político",
                      "source_sections": headings[:1], "template_updates": []}
            if "aclaracion" in options["response_format"]["json_schema"]["schema"]["properties"]:
                salida["aclaracion"] = ("Sí: separar las bolsas es una norma de la ciudad, así "
                                        "que va en el factor Político. ¿Te sirve?")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(salida)))],
            usage=None,
        )

    client = Mock()
    client.chat.completions.create.side_effect = crear
    return client, recibidos


def turno(runtime_class, catalog, kind="explicacion", mensaje=DUDA, en_orquestador=False):
    card = catalog.tool_card("pestel")
    headings = [h.strip() for h in re.findall(r"^#{1,6}\s+(.+)$", card, re.MULTILINE)]
    client, recibidos = cliente(kind, en_orquestador, headings)
    runtime = runtime_class(settings(), client=client)
    state = ProjectState(notebook_id="n", stage=1, phase="Descubrimiento", active_tool="pestel")
    handoff = runtime.orchestrate(mensaje, state, catalog.route_index())
    candidate = None
    if handoff.kind == "trabajo":
        candidate = runtime.guide(mensaje, state, handoff, card, allowed_fields=["politico"])
    return runtime, handoff, candidate, recibidos


@pytest.mark.parametrize("variante,en_orquestador", [
    (InterpreteAparte, False), (InterpreteAmpliado, True),
])
def test_a_point_doubt_is_answered_briefly_instead_of_pasting_the_card(
    catalog, variante, en_orquestador,
):
    runtime, handoff, candidate, recibidos = turno(
        variante, catalog, en_orquestador=en_orquestador)

    assert handoff.kind == "trabajo"  # ya no «explicacion»: no se pega la ficha completa
    assert "LA PERSONA PREGUNTÓ: «¿eso cuenta como político?»" in recibidos[
        "GroundedCandidateResponse"]
    assert "separar en bolsa blanca, negra y verde" in recibidos["GroundedCandidateResponse"]
    aclaracion, pregunta = candidate.message.split("\n\n")
    assert aclaracion.startswith("Sí: separar las bolsas") and "?" not in aclaracion
    assert pregunta.count("?") == 1
    # (f) es un agente aparte: una llamada propia; (e) lee el turno dentro del Orquestador.
    assert ("LecturaTurno" in recibidos) is (variante is InterpreteAparte)


def test_asking_about_the_whole_card_still_gets_the_card(catalog):
    _, handoff, _, _ = turno(InterpreteAparte, catalog, mensaje="¿Qué es un PESTEL?")
    assert handoff.kind == "explicacion"


def test_code_only_variant_keeps_its_previous_behaviour(catalog):
    runtime, handoff, _, recibidos = turno(SoloControlesEnCodigo, catalog, kind="trabajo")
    assert "LecturaTurno" not in recibidos
    assert "LA PERSONA PREGUNTÓ" not in recibidos["GroundedCandidateResponse"]


def test_a_failed_reading_falls_back_to_the_usual_turn(catalog):
    runtime = InterpreteAparte(settings(), client=Mock())
    runtime.client.chat.completions.create.side_effect = RuntimeError("sin modelo")
    runtime._leer_turno(DUDA, ProjectState(notebook_id="n", stage=1, phase="Descubrimiento"))
    assert runtime.lectura is None


def test_clarification_is_short_and_has_no_question():
    texto = "Primera frase. Segunda frase. ¿Una pregunta? Tercera frase."
    assert aclaracion_breve(texto) == "Primera frase. Segunda frase."
    largo = aclaracion_breve(" ".join(["palabra"] * 80) + ".")
    assert len(largo.split()) == 45 and largo.endswith("…")
