import json
import re
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ruta_dia_agents.acompanamiento.planificador import (
    NO_SABE,
    RESPONDIDA,
    _todas,
    antes_de_la_pregunta,
    cierre,
    consejo_de_la_ficha,
    es_duda,
    partes_de,
    partes_repetidas,
    planear,
    salida_con_plan,
)
from ruta_dia_agents.acompanamiento.variantes import PlanificadorConControles
from ruta_dia_agents.compartido.contracts import (
    HandoffContract,
    ProjectState,
    TurnResult,
    Verdict,
    VerificationResult,
)
from ruta_dia_agents.config import Settings
from ruta_dia_agents.conocimiento.knowledge import KnowledgeCatalog
from ruta_dia_agents.proyectos.memory import NotebookMemory

RETO = "Lanzar una app que pague por reciclar en conjuntos de Bogotá."


@pytest.fixture
def catalog():
    return KnowledgeCatalog(Settings.from_env().route_path)


def estados(plan):
    return {k: v["estado"] for k, v in plan.progreso["partes"].items()}


def test_every_part_definition_is_literal_text_from_its_card(catalog):
    for ficha, partes in _todas().items():
        como = re.sub(r"\s+", " ", catalog.card_section(ficha, "how"))
        for parte in partes:
            assert parte.definicion in como, (ficha, parte.id)


def test_the_plan_walks_the_parts_without_asking_twice():
    plan = planear("pestel", None, "Quiero hacer un PESTEL", RETO)
    assert plan.objetivo.id == "politico" and estados(plan) == {"reto": RESPONDIDA}

    plan = planear("pestel", plan.progreso, "Separar las basuras en tres bolsas es obligatorio.")
    assert estados(plan)["politico"] == RESPONDIDA and plan.objetivo.id == "economico"

    plan = planear("pestel", plan.progreso, "no sé")
    assert estados(plan)["economico"] == NO_SABE and plan.objetivo.id == "social"
    assert plan.nota  # se le dice que quedó anotado


def test_a_doubt_is_answered_from_the_card_and_the_part_stays_open():
    plan = planear("pestel", {"en_curso": "politico", "partes": {}},
                   "Lo de las bolsas, ¿eso cuenta como político? ¿Qué significa normativa?")
    assert plan.intencion == "aclarar" and plan.objetivo.id == "politico"
    assert "«Político: normativas, políticas públicas" in plan.aclaracion
    assert "politico" not in plan.progreso["partes"]


def test_asking_to_move_and_labelling_another_part_are_respected():
    plan = planear("pestel", {"en_curso": "politico", "partes": {}}, "pasemos a lo legal")
    assert plan.objetivo.id == "legal" and "politico" not in plan.progreso["partes"]

    plan = planear("pestel", plan.progreso, "En lo social, la gente quiere que le paguen rápido.")
    assert estados(plan) == {"social": RESPONDIDA}
    assert plan.objetivo.id == "legal"  # se retoma la parte que quedó sin responder


def test_when_every_part_is_done_the_plan_closes():
    partes = {p: {"estado": RESPONDIDA, "texto": "x"} for p in
              ["reto", "politico", "economico", "social", "tecnologico", "ecologico", "legal",
               "oportunidad_amenaza"]}
    plan = planear("pestel", {"en_curso": "priorizar", "partes": partes},
                   "Lo más relevante es lo legal y lo económico.")
    assert plan.intencion == "cerrar" and plan.objetivo is None
    texto = cierre(plan, "PESTEL", "Customer Journey Map")
    # Solo dice lo cierto (ya pasó por cada parte); no da la ficha por completa.
    assert texto.startswith("Ya pasamos por cada parte de **PESTEL**.")
    assert "completaste" not in texto and "anotaste" not in texto
    # y recomienda la herramienta que sigue en la ruta
    assert "Te recomiendo seguir con **Customer Journey Map**" in texto
    assert cierre(plan, "Lean Canvas").endswith("¿Quieres revisar alguna parte antes de seguir?")


def test_a_tentative_answer_is_not_a_no_se():
    plan = planear("ficha-hipotesis", {"en_curso": "criterio", "partes": {}},
                   "No sé, ¿2 de cada 10 citas perdidas ya sería un buen umbral?")
    assert plan.progreso["partes"]["criterio"]["estado"] == RESPONDIDA and not plan.nota


def test_repeated_parts_are_detected_only_in_the_question():
    plan = planear("pestel", {"en_curso": "politico", "partes": {}}, "La alcaldía da becas.")
    assert [p.id for p in partes_repetidas("¿Qué otra norma política conoces?", plan)] == [
        "politico"]
    assert partes_repetidas("Anotado lo político. ¿Qué pasa con la economía?", plan) == []


def test_point_doubts_are_not_requests_to_continue():
    assert es_duda("¿eso va en dolores o en necesidades?")
    assert not es_duda("¿qué hago ahora?")
    assert not es_duda("Lo de las bolsas cuenta como político.")


def test_tools_without_parts_get_no_plan():
    assert planear("trabajo-de-campo", None, "Quiero planear entrevistas") is None


def test_memory_returns_the_progress_saved_with_the_last_answer(tmp_path):
    progreso = {"pestel": {"en_curso": "economico",
                           "partes": {"politico": {"estado": RESPONDIDA, "texto": "becas"}}}}
    estado = ProjectState(notebook_id="n")
    handoff = HandoffContract(intent="i", phase="Descubrimiento", stage=1, expertise="novel",
                              context_summary="c")
    resultado = TurnResult(
        message="¿Y lo económico?", handoff=handoff, attempts=1, progreso=progreso,
        verification=VerificationResult(verdict=Verdict.APPROVED, severity="none",
                                        findings=[], source_tool_id=""),
    )
    with NotebookMemory(tmp_path / "n.sqlite3") as memoria:
        memoria.save_exchange("La alcaldía da becas.", resultado, estado)
        assert memoria.load(estado).progreso == progreso


def test_planner_variant_asks_only_for_the_part_that_is_due(catalog):
    card = catalog.tool_card("pestel")
    headings = [h.strip() for h in re.findall(r"^#{1,6}\s+(.+)$", card, re.MULTILINE)]
    recibido = {}

    def crear(**options):
        nombre = options["response_format"]["json_schema"]["name"]
        recibido[nombre] = options["messages"][-1]["content"]
        salida = (
            {"selection": "1:pestel", "intent": "PESTEL", "kind": "trabajo",
             "expertise": "novel", "context_summary": "c", "reason": "r"}
            if nombre == "RouteDecision" else
            {"message": "¿Qué otra norma política conoces?", "tool_id": "pestel",
             "next_step": "Preguntar", "source_sections": headings[:1], "template_updates": []}
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(salida)))],
            usage=None)

    client = Mock()
    client.chat.completions.create.side_effect = crear
    settings = replace(Settings.from_env(), base_url="http://127.0.0.1:18083/v1", api_key="t")
    runtime = PlanificadorConControles(settings, client=client)
    state = ProjectState(notebook_id="n", stage=1, active_tool="pestel",
                         context={"question": RETO},
                         progreso={"pestel": {"en_curso": "politico", "partes": {}}})
    mensaje = "La alcaldía tiene becas de tecnología para colegios."
    handoff = runtime.orchestrate(mensaje, state, catalog.route_index())
    handoff = runtime.planificar(mensaje, state, handoff, catalog.route_index())
    candidate = runtime.guide(mensaje, state, handoff, card)

    assert "Parte que toca ahora: «Económico»" in recibido["GroundedCandidateResponse"]
    assert "Político: «La alcaldía tiene becas" in recibido["GroundedCandidateResponse"]
    veredicto = runtime.verify(candidate, handoff, card, message=mensaje, state=state)
    assert veredicto.verdict == Verdict.REJECTED  # preguntó otra vez por lo político
    assert runtime.progreso_turno["pestel"]["en_curso"] == "economico"


@pytest.mark.parametrize("duda", [
    "¿Qué diferencia hay entre una causa y un efecto?",
    "¿Cuál es la diferencia entre causa y causa de fondo?",
    "¿Qué es una causa de fondo?",
])
def test_these_doubts_are_clarified_not_taken_as_answers(duda):
    avance = {"en_curso": "causas", "partes": {}}
    plan = planear("arbol-problemas", avance, duda, reto="Los mayores no usan la app")
    assert plan.intencion == "aclarar"
    assert "causas" not in plan.progreso["partes"]


def test_asking_to_start_the_card_is_not_an_answer():
    avance = {"en_curso": "causas", "partes": {}}
    plan = planear("arbol-problemas", avance, "Quiero hacer el árbol de problemas.",
                   reto="Los mayores no usan la app")
    assert plan.objetivo.id == "causas" and "causas" not in plan.progreso["partes"]
    # una respuesta de verdad sí cuenta, aunque empiece con «quiero»
    plan = planear("arbol-problemas", avance, "Quiero decir que la letra de la app es pequeña.",
                   reto="Los mayores no usan la app")
    assert plan.progreso["partes"]["causas"]["estado"] == "respondida"


def test_a_doubt_quotes_the_longest_part_name_it_mentions():
    avance = {"en_curso": "causa_de_fondo", "partes": {}}
    plan = planear("arbol-problemas", avance, "¿Qué es una causa de fondo?", reto="x")
    assert "causa de fondo" in plan.aclaracion and "anótalas como raíces" not in plan.aclaracion


def test_the_safe_exit_follows_the_plan_instead_of_pasting_the_card():
    avance = {"en_curso": "efectos", "partes": {"causas": {"estado": "respondida", "texto": "x"}}}
    plan = planear("arbol-problemas", avance, "Pierden la cita y se forman filas largas.",
                   reto="Los mayores no usan la app")
    texto = salida_con_plan(plan)
    assert plan.objetivo.id == "causa_de_fondo" and "**Causa de fondo**" in texto
    assert "Escribe el **problema central**" not in texto
    assert salida_con_plan(None) is None


def test_the_safe_exit_does_not_quote_the_same_part_twice():
    avance = {"en_curso": "causa_de_fondo", "partes": {}}
    plan = planear("arbol-problemas", avance, "¿Qué es una causa de fondo?", reto="x")
    assert salida_con_plan(plan).count("anida la respuesta") == 1


def test_the_card_tip_for_a_part_is_quoted_literally():
    tarjeta = KnowledgeCatalog(Settings.from_env().route_path).tool_card("arbol-problemas")
    fondo = next(p for p in partes_de("arbol-problemas") if p.id == "causa_de_fondo")
    assert consejo_de_la_ficha(fondo, tarjeta) == (
        "Quedarse en la causa superficial lleva a soluciones superficiales.")
    causas = next(p for p in partes_de("arbol-problemas") if p.id == "causas")
    assert consejo_de_la_ficha(causas, tarjeta) == ""  # ese paso no trae consejo


def test_text_goes_right_before_the_question():
    assert antes_de_la_pregunta("Buen punto. ¿Y qué más?", "Un consejo.") == (
        "Buen punto. Un consejo. ¿Y qué más?")
    assert antes_de_la_pregunta("Anota las causas.", "Un consejo.") == (
        "Anota las causas. Un consejo.")


def test_a_tip_that_leans_on_the_previous_sentence_is_not_shown_alone():
    tarjeta = KnowledgeCatalog(Settings.from_env().route_path).tool_card("arbol-problemas")
    revision = next(p for p in partes_de("arbol-problemas") if p.id == "revision")
    assert consejo_de_la_ficha(revision, tarjeta) == ""


def test_the_safe_exit_also_brings_the_card_tip():
    tarjeta = KnowledgeCatalog(Settings.from_env().route_path).tool_card("arbol-problemas")
    avance = {"en_curso": "causas", "partes": {"causas": {"estado": "respondida", "texto": "x"}}}
    plan = planear("arbol-problemas", avance, "Otra cosa más sobre esto.", reto="x")
    assert plan.objetivo.id == "causa_de_fondo"
    assert "Un consejo de la ficha: «Quedarse en la causa superficial" in salida_con_plan(
        plan, tarjeta)
