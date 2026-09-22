from collections import deque

from ruta_dia_agents.audit import NullRecorder
from ruta_dia_agents.config import Settings
from ruta_dia_agents.contracts import (
    CandidateResponse,
    HandoffContract,
    ProjectState,
    Severity,
    TemplateUpdate,
    Verdict,
    VerificationFinding,
    VerificationResult,
)
from ruta_dia_agents.knowledge import KnowledgeCatalog
from ruta_dia_agents.langgraph_workflow import LangGraphRutaDia
from ruta_dia_agents.service import SAFE_DEGRADATION


class FakeRuntime:
    def __init__(self, verdicts, gap=False):
        self.verdicts = deque(verdicts)
        self.gap = gap
        self.guide_calls = 0

    def orchestrate(self, message, state, route_index):
        if self.gap:
            return HandoffContract(
                intent="brecha",
                phase="Incubación",
                stage=7,
                expertise="novel",
                active_tool="",
                context_summary="Sin ficha",
            )
        return HandoffContract(
            intent="analizar",
            phase="Descubrimiento",
            stage=1,
            expertise="novel",
            recommendations=[{"tool_id": "pestel", "reason": "Solicitada"}],
            active_tool="pestel",
            context_summary="Prueba",
        )

    def guide(self, message, state, handoff, tool_card, retry_feedback=None, allowed_fields=None):
        self.guide_calls += 1
        return CandidateResponse(
            message=f"¿Cuál es el factor observado? Intento {self.guide_calls}",
            tool_id="pestel",
            next_step="Identificar un factor.",
            source_sections=["Cómo se usa (paso a paso)"],
        )

    def verify(self, candidate, handoff, tool_card, *, message="", state=None):
        verdict = self.verdicts.popleft()
        return VerificationResult(
            verdict=verdict,
            severity=Severity.NONE if verdict == Verdict.APPROVED else Severity.HIGH,
            findings=(
                []
                if verdict == Verdict.APPROVED
                else [VerificationFinding(code="prueba", detail="Reintentar")]
            ),
            source_tool_id=handoff.active_tool,
        )


def workflow(runtime):
    catalog = KnowledgeCatalog(Settings.from_env().route_path)
    return LangGraphRutaDia(catalog, runtime, NullRecorder())


def test_langgraph_exposes_the_expected_workflow_nodes():
    graph = workflow(FakeRuntime([Verdict.APPROVED])).graph.get_graph()
    assert {"orchestrate", "guide", "verify", "finalize", "degrade"}.issubset(graph.nodes)


def test_langgraph_delivers_an_approved_candidate():
    runtime = FakeRuntime([Verdict.APPROVED])
    result = workflow(runtime).handle_turn("Quiero PESTEL", ProjectState(notebook_id="lg-ok"))
    assert result.verification.verdict == Verdict.APPROVED
    assert result.attempts == 1
    assert runtime.guide_calls == 1


def test_langgraph_routes_a_rejection_back_to_the_methodologist_once():
    runtime = FakeRuntime([Verdict.REJECTED, Verdict.APPROVED])
    result = workflow(runtime).handle_turn("Quiero PESTEL", ProjectState(notebook_id="lg-retry"))
    assert result.verification.verdict == Verdict.APPROVED
    assert result.attempts == 2
    assert runtime.guide_calls == 2


def test_langgraph_degrades_after_the_second_rejection():
    runtime = FakeRuntime([Verdict.REJECTED, Verdict.REJECTED])
    result = workflow(runtime).handle_turn("Quiero PESTEL", ProjectState(notebook_id="lg-stop"))
    assert result.message == SAFE_DEGRADATION
    assert result.degraded is True
    assert result.attempts == 2


def test_langgraph_skips_generation_when_the_stage_has_no_card():
    runtime = FakeRuntime([], gap=True)
    result = workflow(runtime).handle_turn(
        "Estoy en ejecución", ProjectState(notebook_id="lg-gap", stage=7, phase="Incubación")
    )
    assert result.degraded is True
    assert result.verification.findings[0].code == "knowledge_gap"
    assert runtime.guide_calls == 0


def test_observed_orientation_is_delivered_without_promoting_updates_to_memory():
    class ObservedRuntime(FakeRuntime):
        def guide(self, *args, **kwargs):
            candidate = super().guide(*args, **kwargs)
            candidate.template_updates = [TemplateUpdate(field="politico", value="Dato anterior")]
            return candidate

    result = workflow(ObservedRuntime([Verdict.OBSERVED])).handle_turn(
        "Quiero PESTEL", ProjectState(notebook_id="lg-observed")
    )
    assert result.verification.verdict == Verdict.OBSERVED
    assert result.degraded is False
    assert result.accepted_updates == []
