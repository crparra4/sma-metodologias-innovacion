from collections import deque

from ruta_dia_agents.audit import NullRecorder
from ruta_dia_agents.config import Settings
from ruta_dia_agents.contracts import (
    CandidateResponse,
    ExpertiseLevel,
    HandoffContract,
    ProjectState,
    Severity,
    ToolRecommendation,
    Verdict,
    VerificationFinding,
    VerificationResult,
)
from ruta_dia_agents.knowledge import KnowledgeCatalog
from ruta_dia_agents.service import SAFE_DEGRADATION, RutaDiaService


def handoff():
    return HandoffContract(
        intent="orientacion",
        phase="Descubrimiento",
        stage=1,
        expertise=ExpertiseLevel.NOVEL,
        recommendations=[ToolRecommendation(tool_id="pestel", reason="analizar entorno")],
        active_tool="pestel",
        context_summary="Proyecto en etapa inicial",
    )


def candidate(message="Empecemos por el factor político."):
    return CandidateResponse(
        message=message,
        tool_id="pestel",
        next_step="Describe el factor político.",
        source_sections=["Cómo se usa (paso a paso)"],
    )


def verification(verdict):
    findings = []
    severity = Severity.NONE
    if verdict == Verdict.REJECTED:
        findings = [VerificationFinding(code="invented_step", detail="Paso no respaldado")]
        severity = Severity.HIGH
    return VerificationResult(
        verdict=verdict,
        severity=severity,
        findings=findings,
        source_tool_id="pestel",
    )


class FakeRuntime:
    def __init__(self, verdicts):
        self.verdicts = deque(verdicts)
        self.guide_calls = 0

    def orchestrate(self, message, state, route_index):
        return handoff()

    def guide(self, message, state, handoff, tool_card, retry_feedback=None, allowed_fields=None):
        self.guide_calls += 1
        return candidate(message=f"Intento {self.guide_calls}")

    def verify(self, candidate, handoff, tool_card, *, message="", state=None):
        self.verified_message = message
        self.verified_state = state
        return verification(self.verdicts.popleft())


class KnowledgeGapRuntime(FakeRuntime):
    def __init__(self):
        super().__init__([])

    def orchestrate(self, message, state, route_index):
        return HandoffContract(
            intent="brecha_conocimiento",
            phase="Incubación",
            stage=7,
            expertise=ExpertiseLevel.NOVEL,
            recommendations=[],
            active_tool="",
            context_summary="Etapa aún sin fichas",
        )


def service(runtime):
    catalog = KnowledgeCatalog(Settings.from_env().route_path)
    return RutaDiaService(catalog, runtime, NullRecorder())


def test_approved_response_is_delivered():
    runtime = FakeRuntime([Verdict.APPROVED])
    result = service(runtime).handle_turn("¿Qué sigue?", ProjectState())

    assert result.message == "Intento 1"
    assert result.attempts == 1
    assert result.degraded is False
    assert runtime.verified_message == "¿Qué sigue?"
    assert runtime.verified_state.notebook_id == "demo"


def test_rejected_response_gets_one_retry():
    runtime = FakeRuntime([Verdict.REJECTED, Verdict.APPROVED])
    result = service(runtime).handle_turn("¿Qué sigue?", ProjectState())

    assert result.message == "Intento 2"
    assert result.attempts == 2
    assert runtime.guide_calls == 2


def test_second_rejection_degrades_honestly():
    runtime = FakeRuntime([Verdict.REJECTED, Verdict.REJECTED])
    result = service(runtime).handle_turn("¿Qué sigue?", ProjectState())

    assert result.message == SAFE_DEGRADATION
    assert result.attempts == 2
    assert result.degraded is True


def test_stage_without_cards_reports_knowledge_gap_without_inventing():
    runtime = KnowledgeGapRuntime()
    result = service(runtime).handle_turn(
        "¿Cómo ejecuto el experimento?",
        ProjectState(phase="Incubación", stage=7),
    )

    assert "todavía no tiene una ficha metodológica validada" in result.message
    assert result.verification.findings[0].code == "knowledge_gap"
    assert result.degraded is True
    assert runtime.guide_calls == 0
