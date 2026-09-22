from ruta_dia_agents.contracts import (
    CandidateResponse,
    HandoffContract,
    TemplateUpdate,
    VerificationAssessment,
)
from ruta_dia_agents.runtime import (
    claim_supported_by_user,
    grounded_verdict,
    method_step_supported,
)


def test_an_unsupported_cause_cannot_be_downgraded_to_a_minor_observation():
    candidate, handoff = example()
    assessment = VerificationAssessment(
        unsupported_claims=[candidate.message],
    )
    result = grounded_verdict(assessment, candidate, handoff, "Pregunta por qué.", "No lo sé.")
    assert result.verdict == "rejected"
    assert result.findings[0].code == "unsupported_claim"


def test_user_data_does_not_need_to_appear_in_the_method_card():
    candidate, handoff = example()
    user_text = "Los clientes dicen: el envío es caro."
    assessment = VerificationAssessment(
        unsupported_claims=[],
    )
    result = grounded_verdict(assessment, candidate, handoff, "Pregunta por qué.", user_text)
    assert result.verdict == "approved"
    assert result.findings == []


def test_template_update_must_come_from_the_current_user_message():
    candidate, handoff = example()
    candidate.template_updates = [
        TemplateUpdate(field="problema", value="Los clientes abandonan por el envío")
    ]
    assessment = VerificationAssessment()
    result = grounded_verdict(
        assessment,
        candidate,
        handoff,
        "Pregunta por qué.",
        "El efecto es que dejan el carrito sin pagar.",
    )
    assert result.verdict == "observed"
    assert result.findings[0].code == "unsupported_template_update"


def test_short_template_value_can_be_saved_when_it_is_explicit():
    candidate, handoff = example()
    candidate.template_updates = [TemplateUpdate(field="causa", value="inflación")]
    assessment = VerificationAssessment()
    result = grounded_verdict(
        assessment,
        candidate,
        handoff,
        "Pregunta por qué.",
        "La causa observada es la inflación.",
    )
    assert result.verdict == "approved"


def test_agent_cannot_ask_again_for_a_field_just_supplied():
    candidate, handoff = example()
    candidate.message = "¿Qué efecto concreto experimenta el cliente?"
    candidate.template_updates = [
        TemplateUpdate(field="efecto", value="Deja el carrito sin pagar")
    ]
    result = grounded_verdict(
        VerificationAssessment(),
        candidate,
        handoff,
        "Pregunta por qué.",
        "El efecto es que deja el carrito sin pagar.",
    )
    assert result.verdict == "rejected"
    assert result.findings[0].code == "repeated_known_field"


def test_an_audit_claim_absent_from_the_candidate_is_rejected():
    candidate, handoff = example()
    assessment = VerificationAssessment(
        unsupported_claims=["Una afirmación que no produjo el asistente."],
    )
    result = grounded_verdict(assessment, candidate, handoff, "Pregunta por qué.", "No lo sé.")
    assert result.verdict == "rejected"
    assert result.findings[0].code == "invalid_audit_claim"


def test_close_paraphrase_of_user_evidence_is_detected():
    claim = "Según lo que te dijeron los clientes, el envío les resulta demasiado caro."
    user = "Entrevisté a clientes y dijeron que abandonan porque el envío es demasiado caro."
    assert claim_supported_by_user(claim, user) is True


def test_invented_cause_is_not_mistaken_for_user_evidence():
    claim = "La causa es que el envío resulta demasiado caro para tus clientes."
    user = "Abandonan la compra al ver el envío. No he investigado por qué."
    assert claim_supported_by_user(claim, user) is False


def test_completed_challenge_step_is_supported_by_explicit_user_challenge():
    claim = "Ya definiste el reto."
    user = "Quiero aplicar PESTEL. Mi reto es mejorar la participación estudiantil."
    assert claim_supported_by_user(claim, user) is True


def test_five_whys_question_after_a_user_problem_is_not_premature():
    candidate = CandidateResponse(
        message=(
            "El problema es que los clientes abandonan al ver el envío. "
            "¿Por qué ocurre esto?"
        ),
        next_step="Preguntar por qué ocurre.",
        tool_id="cinco-porques",
        source_sections=["Cómo se usa (paso a paso)"],
    )
    _, handoff = example()
    assessment = VerificationAssessment(method_error="premature_or_conflicting_step")
    result = grounded_verdict(
        assessment,
        candidate,
        handoff,
        "Pregunta por qué ocurre.",
        "Los clientes abandonan al ver el envío.",
    )
    assert result.verdict == "approved"


def test_method_step_that_appears_in_the_card_is_supported():
    assert method_step_supported(
        "Enunciar el problema concreto.",
        "1. Enuncia el problema concreto. 2. Pregunta por qué ocurre.",
    )


def test_method_step_with_new_number_and_requirement_is_not_supported():
    assert not method_step_supported(
        "Entrevistar obligatoriamente a 100 clientes y completar PESTEL.",
        "1. Enuncia el problema concreto. 2. Pregunta por qué ocurre.",
    )


def example():
    candidate = CandidateResponse(
        message="El envío es caro. ¿Qué observaste?",
        next_step="Preguntar por qué.",
        tool_id="cinco-porques",
        source_sections=["Cómo se usa"],
    )
    handoff = HandoffContract(
        intent="analizar",
        phase="Descubrimiento",
        stage=1,
        expertise="novel",
        recommendations=[{"tool_id": "cinco-porques", "reason": "solicitado"}],
        active_tool="cinco-porques",
        context_summary="prueba",
    )
    return candidate, handoff
