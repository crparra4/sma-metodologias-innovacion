"""Fallos que aparecieron al probar las quince fichas seguidas en un proyecto (oct. 2026):
el agente cambiaba de ficha ante una respuesta, tomaba respuestas por pedidos de explicación,
contestaba lo ajeno con una pregunta de la ficha y fallaba con la ficha más larga."""

import json

import pytest

from hilo.acompanamiento.audit import NullRecorder
from hilo.acompanamiento.langgraph_workflow import OUT_OF_SCOPE, LangGraphRutaDia
from hilo.acompanamiento.runtime import (
    ContractRuntime,
    answered_block,
    asks_to_confirm_answer,
    drop_filler,
    follows_previous_step,
    grounded_verdict,
    is_thanks,
    keeps_active_tool,
    next_step_hint,
    repeats_previous_question,
    resolve_kind,
    state_for_new_card,
)
from hilo.compartido.contracts import (
    CandidateResponse,
    HandoffContract,
    ProjectState,
    VerificationAssessment,
)
from hilo.config import Settings
from hilo.conocimiento.knowledge import PROMPT_CARD_LIMIT, KnowledgeCatalog, card_section


def catalog() -> KnowledgeCatalog:
    return KnowledgeCatalog(Settings.from_env().route_path)


def kind(decided, message, *, explicit=False, mentioned=False, **state):
    return resolve_kind(
        decided, message, ProjectState(**state), explicit=explicit, mentioned=mentioned,
    )


class Orchestrator(ContractRuntime):
    """Simula un Orquestador que elige la ficha y el tipo que se le indiquen."""

    def __init__(self, selection, decided="trabajo"):
        self.orchestrator = "orchestrator"
        self.selection, self.decided = selection, decided

    def _run(self, agent, description, output_model):
        return output_model(
            selection=self.selection, intent="x", kind=self.decided, expertise="novel",
            context_summary="x", reason="x",
        )


def routed(message, selection, *, decided="trabajo", **state):
    return Orchestrator(selection, decided).orchestrate(
        message, ProjectState(**state), catalog().route_index(),
    )


# ---------- una respuesta no cambia de ficha ----------

def test_an_answer_stays_in_the_card_even_if_the_model_picks_another():
    message = "En lo político, la alcaldía tiene un programa de becas en tecnología."
    handoff = routed(message, "5:ficha-hipotesis", decided="recomendacion",
                     stage=1, active_tool="pestel")
    assert (handoff.active_tool, handoff.stage, handoff.kind) == ("pestel", 1, "trabajo")


@pytest.mark.parametrize("message, selection, tool", [
    ("Necesito redactar una hipótesis para mi experimento.", "5:ficha-hipotesis",
     "ficha-hipotesis"),
    ("Quiero hacer un PESTEL para la academia.", "1:pestel", "pestel"),  # ficha nombrada
    ("Ahora quiero priorizar mis ideas.", "4:moscow", "moscow"),
])
def test_asking_for_another_card_does_switch(message, selection, tool):
    handoff = routed(message, selection, stage=4, active_tool="matriz-priorizacion")
    assert handoff.active_tool == tool


def test_without_a_card_in_progress_the_model_chooses():
    assert not keeps_active_tool("Tengo una idea", ProjectState(), "pestel",
                                 explicit=False, mentioned=False)


# ---------- qué pide el mensaje ----------

def test_a_clear_off_topic_request_is_declined_even_inside_a_card():
    assert kind("trabajo", "¿Cuál es la capital de Francia?", active_tool="lean-canvas") == "fuera"
    assert kind("trabajo", "Escríbeme un poema sobre el café.", active_tool="pestel") == "fuera"
    # nombrar la palabra sin pedir nada no es un pedido ajeno
    assert kind("trabajo", "La capital de trabajo es poca.", active_tool="lean-canvas") == "trabajo"


def test_an_answer_is_not_an_explanation_request_whatever_the_model_says():
    answer = "Porque los colegios públicos del barrio no tienen profesor de tecnología."
    assert kind("explicacion", answer, active_tool="arbol-problemas") == "trabajo"
    question = "¿Y eso qué significa?"
    assert kind("explicacion", question, active_tool="arbol-problemas") == "explicacion"


def test_the_model_cannot_recommend_while_a_card_is_in_progress():
    assert kind("recomendacion", "Cada mes le mandan un video.", active_tool="customer-journey") \
        == "trabajo"
    assert kind("recomendacion", "Tengo una idea de negocio.") == "recomendacion"


@pytest.mark.parametrize("message, expected", [
    ("Gracias, ya cerré ese análisis.", True),
    ("Muchas gracias", True),
    ("Gracias. ¿Y ahora qué sigue?", False),
    ("Gracias a la beca de la alcaldía los niños pueden estudiar programación gratis.", False),
])
def test_thanks_are_short_and_ask_nothing(message, expected):
    assert is_thanks(message) is expected


def test_a_thank_you_gets_a_short_reply_and_keeps_the_place():
    class Courtesy:
        def orchestrate(self, message, state, route_index):
            return HandoffContract(
                intent="x", phase="Descubrimiento", stage=1, expertise="novel",
                recommendations=[{"tool_id": "cinco-porques", "reason": "x"}],
                active_tool="cinco-porques", context_summary="x",
                kind=kind("trabajo", message, active_tool="cinco-porques"),
            )

    state = ProjectState(stage=1, active_tool="cinco-porques")
    result = LangGraphRutaDia(catalog(), Courtesy(), NullRecorder()).handle_turn(
        "Gracias, ya cerré ese análisis.", state,
    )
    assert result.message.startswith("¡Con gusto!") and result.message != OUT_OF_SCOPE
    assert result.handoff.active_tool == "cinco-porques" and not result.degraded


# ---------- la ficha larga ----------

def test_a_long_card_is_trimmed_to_fit_the_model_and_says_what_was_left_out():
    full = catalog().tool_card("trabajo-de-campo")
    trimmed = catalog().prompt_card("trabajo-de-campo")
    assert len(full) > PROMPT_CARD_LIMIT >= len(trimmed) - 200
    assert trimmed.startswith(full[:200]) and "## TL;DR" in trimmed
    assert "Secciones omitidas por extensión: Details" in trimmed


def test_short_cards_reach_the_model_untouched():
    assert catalog().prompt_card("pestel") == catalog().tool_card("pestel")


def test_the_field_guide_can_be_explained_from_its_summary():
    what = card_section(catalog().tool_card("trabajo-de-campo"), "what")
    assert what.startswith("- **Puedes hacer investigación de campo rigurosa")
    assert "\n" in what  # conserva la lista


# ---------- la pregunta repetida ----------

def test_a_repeated_question_is_told_which_step_comes_next():
    card = catalog().tool_card("ficha-hipotesis")
    question = "Completa la hipótesis de la ficha: ¿qué acción crees que logrará el resultado?"
    assert next_step_hint(question, card) == "Define la métrica que lo demuestra."
    state = ProjectState(
        recent_turns=["Usuario: Necesito una hipótesis.", f"Asistente: {question}"])
    handoff = HandoffContract(
        intent="x", phase=catalog().stage(5).phase, stage=5, expertise="novel",
        recommendations=[{"tool_id": "ficha-hipotesis", "reason": "x"}],
        active_tool="ficha-hipotesis", context_summary="x",
    )
    candidate = CandidateResponse(
        message=question, next_step="Completar la hipótesis.", tool_id="ficha-hipotesis",
        source_sections=["Qué es"],
    )
    result = grounded_verdict(
        VerificationAssessment(), candidate, handoff, card,
        "Creemos que dos clases semanales lograrán 20 inscritos para los padres.", state,
    )
    assert result.findings[0].code == "repeated_question"
    assert "Define la métrica que lo demuestra" in result.findings[0].detail


def test_a_repeated_instruction_counts_as_a_repeated_question():
    previous = "Completa la hipótesis con la plantilla: Creemos que [acción] logrará [resultado]."
    state = ProjectState(recent_turns=[f"Asistente: {previous}"])
    again = previous
    answer = "Creemos que dos clases semanales lograrán 20 inscritos para los padres."
    assert repeats_previous_question(again, answer, state)
    assert not repeats_previous_question("Define la métrica que lo demuestra.", answer, state)


def test_asking_for_the_step_after_the_answered_one_is_not_premature():
    card = catalog().tool_card("lean-canvas")
    state = ProjectState(recent_turns=[
        "Asistente: Para el bloque Problema, ¿cuáles son los tres problemas principales?"])
    handoff = HandoffContract(
        intent="x", phase=catalog().stage(6).phase, stage=6, expertise="novel",
        recommendations=[{"tool_id": "lean-canvas", "reason": "x"}],
        active_tool="lean-canvas", context_summary="x",
    )

    def candidate(message):
        return CandidateResponse(message=message, next_step="Siguiente bloque.",
                                 tool_id="lean-canvas", source_sections=["Qué es"])

    following = candidate("¿A quién va dirigido tu producto, cuáles son tus segmentos de cliente?")
    jumping = candidate("¿Cuáles son tus fuentes de ingreso?")
    assert follows_previous_step(following, state, card)
    assert not follows_previous_step(jumping, state, card)
    premature = VerificationAssessment(method_error="premature_or_conflicting_step")
    answer = "Los tres problemas son: no hay oferta, es caro y no saben evaluar."
    def verdict(item):
        return grounded_verdict(premature, item, handoff, card, answer, state).verdict

    assert verdict(following) == "approved" and verdict(jumping) == "rejected"


def test_a_stuck_repeat_ends_with_the_next_step_instead_of_the_whole_card():
    question = "Completa la hipótesis de la ficha: ¿qué acción crees que logrará el resultado?"

    class Stuck:
        def orchestrate(self, message, state, route_index):
            return HandoffContract(
                intent="x", phase=catalog().stage(5).phase, stage=5, expertise="novel",
                recommendations=[{"tool_id": "ficha-hipotesis", "reason": "x"}],
                active_tool="ficha-hipotesis", context_summary="x",
            )

        def guide(self, message, state, handoff, tool_card, retry_feedback=None,
                  allowed_fields=None):
            return CandidateResponse(message=question, next_step="Completar la hipótesis.",
                                     tool_id="ficha-hipotesis", source_sections=["Qué es"])

        def verify(self, candidate, handoff, tool_card, *, message="", state=None):
            return grounded_verdict(VerificationAssessment(), candidate, handoff, tool_card,
                                    message, state)

    state = ProjectState(stage=5, active_tool="ficha-hipotesis",
                         recent_turns=[f"Asistente: {question}"])
    result = LangGraphRutaDia(catalog(), Stuck(), NullRecorder()).handle_turn(
        "Creemos que dos clases semanales lograrán 20 inscritos para los padres.", state)
    assert result.degraded and result.attempts == 2
    assert result.message.startswith("Ya tengo tu respuesta")
    assert "Define la métrica que lo demuestra" in result.message
    assert "paso a paso tal como está en la ficha" not in result.message


# ---------- partir de lo que la persona respondió ----------

def lean_handoff(kind="trabajo"):
    return HandoffContract(
        intent="x", phase=catalog().stage(6).phase, stage=6, expertise="novel",
        recommendations=[{"tool_id": "lean-canvas", "reason": "x"}],
        active_tool="lean-canvas", context_summary="x", kind=kind,
    )


def test_the_model_is_shown_its_question_the_answer_and_what_comes_next():
    card = catalog().tool_card("lean-canvas")
    state = ProjectState(stage=6, active_tool="lean-canvas", recent_turns=[
        "Usuario: Quiero llenar un Lean Canvas.",
        "Asistente: Empecemos. Para el bloque Problema, ¿cuáles son los 3 problemas principales?",
    ])
    answer = "Los tres problemas son: no hay oferta cerca, es caro y no saben evaluar la calidad."
    block = answered_block(answer, state, lean_handoff(), card)
    assert "Tu pregunta fue: «Empecemos. Para el bloque Problema, ¿cuáles son los 3" in block
    assert f"Su respuesta es: «{answer}»" in block
    assert "No vuelvas a preguntar lo mismo" in block
    assert "Lo que sigue en la ficha: «Segmentos de cliente — a quién va dirigido.»" in block


@pytest.mark.parametrize("message, changes", [
    ("¿A qué te refieres con problema?", {}),  # la persona pregunta: no es una respuesta
    ("Los problemas son tres.", {"active_tool": "pestel"}),  # venía de otra ficha
    ("Los problemas son tres.", {"recent_turns": []}),  # primer turno
    ("Los problemas son tres.", {"locked_tool": "lean-canvas"}),  # la cadena la lleva el código
])
def test_the_answer_block_is_only_for_answers_inside_the_same_card(message, changes):
    state = ProjectState(**{
        "stage": 6, "active_tool": "lean-canvas",
        "recent_turns": ["Asistente: ¿Cuáles son los 3 problemas principales?"], **changes,
    })
    assert answered_block(message, state, lean_handoff(), "ficha") == ""


def test_the_hint_skips_a_step_the_answer_already_covers():
    card = catalog().prompt_card("matriz-priorizacion")
    handoff = HandoffContract(
        intent="x", phase=catalog().stage(4).phase, stage=4, expertise="novel",
        recommendations=[{"tool_id": "matriz-priorizacion", "reason": "x"}],
        active_tool="matriz-priorizacion", context_summary="x",
    )
    state = ProjectState(stage=4, active_tool="matriz-priorizacion", recent_turns=[
        "Asistente: Lista las ideas candidatas para aplicar la matriz."])
    block = answered_block("Clases en el salón comunal: impacto alto y esfuerzo bajo.",
                           state, handoff, card)
    assert "Ubícalas en 4 cuadrantes" in block and "Evalúa cada idea" not in block


def test_an_instruction_with_a_verb_of_the_card_is_one_action():
    card = catalog().prompt_card("matriz-priorizacion")
    handoff = HandoffContract(
        intent="x", phase=catalog().stage(4).phase, stage=4, expertise="novel",
        recommendations=[{"tool_id": "matriz-priorizacion", "reason": "x"}],
        active_tool="matriz-priorizacion", context_summary="x",
    )
    candidate = CandidateResponse(
        message="Evalúa cada idea por **impacto** (bajo/alto) y **esfuerzo** (bajo/alto).",
        next_step="Evaluar cada idea.", tool_id="matriz-priorizacion",
        source_sections=["Qué es"],
    )
    result = grounded_verdict(VerificationAssessment(), candidate, handoff, card,
                              "Tengo cuatro ideas.", ProjectState(stage=4))
    assert not result.findings


def test_a_question_written_in_bold_is_still_one_question():
    card = catalog().prompt_card("lean-canvas")
    candidate = CandidateResponse(
        message="Para el siguiente bloque, **¿Quién es el segmento de cliente ideal?**",
        next_step="Definir el segmento de cliente.", tool_id="lean-canvas",
        source_sections=["Qué es"],
    )
    result = grounded_verdict(VerificationAssessment(), candidate, lean_handoff(), card,
                              "Los tres problemas son esos.", ProjectState(stage=6))
    assert "interaction_error" not in [finding.code for finding in result.findings]


def test_an_explanation_turn_gets_no_answer_block():
    state = ProjectState(stage=6, active_tool="lean-canvas",
                         recent_turns=["Asistente: ¿Cuáles son los 3 problemas principales?"])
    assert answered_block("Cuéntame más.", state, lean_handoff("explicacion"), "ficha") == ""


def test_a_sentence_that_quotes_the_card_is_not_filler():
    card = catalog().tool_card("ficha-hipotesis")
    text = ("La fórmula de la hipótesis es: Creemos que [acción/solución] logrará [resultado] "
            "para [usuario]. Completa los tres espacios con tu idea.")
    assert drop_filler(text, "Necesito redactar una hipótesis.", card) == text
    filler = "Es un excelente punto de partida. Completa los tres espacios con tu idea."
    assert drop_filler(filler, "Necesito redactar una hipótesis.", card) \
        == "Completa los tres espacios con tu idea."


@pytest.mark.parametrize("reply, message, expected", [
    ("Para la idea «Clases en el salón comunal», ¿debes marcarla como impacto alto y esfuerzo "
     "bajo?", "Clases en el salón comunal: impacto alto y esfuerzo bajo.", True),
    ("Ya los tienes: ¿Puedes confirmarlos como los tres problemas centrales?",
     "Los tres problemas son: no hay oferta cerca, los cursos son caros.", True),
    ("¿Por qué no hay profesor de tecnología en los colegios públicos del barrio?",
     "Porque los colegios públicos del barrio no tienen profesor de tecnología.", False),
    ("¿Cuál es la siguiente idea y qué impacto y esfuerzo le ves?",
     "Clases en el salón comunal: impacto alto y esfuerzo bajo.", False),
    ("¿Debes marcarla como impacto alto y esfuerzo bajo?",
     "¿La marco como impacto alto y esfuerzo bajo?", False),
    ("Anotada: clases en el salón comunal, impacto alto y esfuerzo bajo. Lista la siguiente "
     "idea.", "Clases en el salón comunal: impacto alto y esfuerzo bajo.", False),
    ("¿Qué dato podrías confirmar con el rector del colegio?",
     "Puedo preguntarle al rector del colegio San José.", False),
])
def test_a_question_that_only_returns_the_answer_is_detected(reply, message, expected):
    card = catalog().tool_card("matriz-priorizacion")
    assert asks_to_confirm_answer(reply, message, card) is expected


def test_asking_to_sort_the_list_the_person_gave_is_not_a_repeat():
    card = catalog().tool_card("moscow")
    options = "clases presenciales, plataforma en línea, préstamo de computadores, certificado"
    question = f"¿Cuál de estos es un Must (imprescindible): {options} o transporte?"
    assert not asks_to_confirm_answer(
        question, f"Quiero priorizar con MoSCoW: {options} y transporte.", card)


def test_asking_to_confirm_the_answer_is_rejected_as_a_repeat():
    card = catalog().tool_card("matriz-priorizacion")
    handoff = HandoffContract(
        intent="x", phase=catalog().stage(4).phase, stage=4, expertise="novel",
        recommendations=[{"tool_id": "matriz-priorizacion", "reason": "x"}],
        active_tool="matriz-priorizacion", context_summary="x",
    )
    candidate = CandidateResponse(
        message="¿Debes marcarla como impacto alto y esfuerzo bajo?",
        next_step="Evaluar la idea.", tool_id="matriz-priorizacion", source_sections=["Qué es"],
    )
    result = grounded_verdict(
        VerificationAssessment(), candidate, handoff, card,
        "Clases en el salón comunal: impacto alto y esfuerzo bajo.",
        ProjectState(stage=4, active_tool="matriz-priorizacion"),
    )
    assert [finding.code for finding in result.findings] == ["repeated_question"]


def archetype_handoff(kind="trabajo"):
    return HandoffContract(
        intent="x", phase=catalog().stage(3).phase, stage=3, expertise="novel",
        recommendations=[{"tool_id": "arquetipo-usuario", "reason": "x"}],
        active_tool="arquetipo-usuario", context_summary="x", kind=kind,
    )


OLD_TURNS = ["Usuario: El trabajo de los padres es que su hijo aprenda algo útil.",
             "Asistente: ¿Qué alegrías experimentan cuando su hijo aprende a programar?"]
NEW_CARD = "Quiero crear un arquetipo de usuario: Carolina, 38 años, mamá de un niño de 9."


def test_a_new_card_does_not_see_the_questions_of_the_previous_one():
    state = ProjectState(stage=3, active_tool="canvas-propuesta-valor", recent_turns=OLD_TURNS)
    assert state_for_new_card(NEW_CARD, state, archetype_handoff()).recent_turns == OLD_TURNS[:1]
    assert state.recent_turns == OLD_TURNS  # el estado del cuaderno no se toca


@pytest.mark.parametrize("message, kind, active", [
    (NEW_CARD, "trabajo", "arquetipo-usuario"),          # sigue en la misma ficha
    ("¿Cómo empiezo el arquetipo?", "explicacion", "canvas-propuesta-valor"),
    ("Quiero un arquetipo con esos padres.", "trabajo", "canvas-propuesta-valor"),
])
def test_the_conversation_is_kept_when_it_still_matters(message, kind, active):
    state = ProjectState(stage=3, active_tool=active, recent_turns=OLD_TURNS)
    assert state_for_new_card(message, state, archetype_handoff(kind)) is state


def test_the_prompt_of_a_new_card_leaves_out_the_old_question():
    class Captured(ContractRuntime):
        def __init__(self):
            self.methodologist = "methodologist"

        def _run(self, agent, description, output_model):
            self.prompt = description
            headings = output_model.model_fields["source_sections"].annotation
            return output_model(
                message="¿Quién es la persona?", next_step="Definir a la persona.",
                tool_id="arquetipo-usuario",
                source_sections=[headings.__args__[0].__args__[0]],
            )

    runtime = Captured()
    state = ProjectState(stage=3, active_tool="canvas-propuesta-valor", recent_turns=OLD_TURNS)
    runtime.guide(NEW_CARD, state, archetype_handoff(), catalog().prompt_card("arquetipo-usuario"))
    assert "alegrías experimentan" not in runtime.prompt
    assert "aprenda algo útil" in runtime.prompt


def test_a_failed_explanation_still_gives_what_the_card_says():
    class Failing:
        def orchestrate(self, message, state, route_index):
            return HandoffContract(
                intent="x", phase=catalog().stage(3).phase, stage=3, expertise="novel",
                recommendations=[{"tool_id": "trabajo-de-campo", "reason": "x"}],
                active_tool="trabajo-de-campo", context_summary="x", kind="explicacion",
            )

        def guide(self, message, state, handoff, tool_card, retry_feedback=None,
                  allowed_fields=None):
            return CandidateResponse(message="¿Qué dolores reportaron?", next_step="x",
                                     tool_id="trabajo-de-campo", source_sections=[])

        def verify(self, candidate, handoff, tool_card, *, message="", state=None):
            return grounded_verdict(
                VerificationAssessment(method_error="invented_step"), candidate, handoff,
                tool_card, message, state,
            )

    result = LangGraphRutaDia(catalog(), Failing(), NullRecorder()).handle_turn(
        "Quiero usar la ficha de trabajo de campo. ¿Cómo empiezo?", ProjectState(stage=3))
    assert result.degraded
    assert result.message.startswith("**Trabajo de campo**")
    assert "No puedo confirmar esa orientación" not in result.message


def test_route_index_still_lists_every_stage():
    assert len(json.loads(catalog().route_index())["stages"]) == 10
