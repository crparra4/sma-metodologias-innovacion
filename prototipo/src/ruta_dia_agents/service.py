from __future__ import annotations

from .audit import NullRecorder, VerificationRecorder
from .contracts import (
    ProjectState,
    Severity,
    TurnResult,
    Verdict,
    VerificationFinding,
    VerificationResult,
)
from .guardrails import StructuralViolation, validate_candidate, validate_handoff
from .knowledge import KnowledgeCatalog
from .runtime import AgentRuntime

SAFE_DEGRADATION = (
    "No puedo confirmar esa orientación con la ficha metodológica cargada. "
    "Para no inventar pasos de la ruta, necesito que revisemos o completemos esa fuente."
)


class RutaDiaService:
    def __init__(
        self,
        catalog: KnowledgeCatalog,
        runtime: AgentRuntime,
        recorder: VerificationRecorder | None = None,
    ):
        catalog.require_valid()
        self.catalog = catalog
        self.runtime = runtime
        self.recorder = recorder or NullRecorder()

    def handle_turn(self, message: str, state: ProjectState) -> TurnResult:
        if not message.strip():
            raise ValueError("El mensaje no puede estar vacío")

        handoff = self.runtime.orchestrate(message, state, self.catalog.route_index())
        validate_handoff(handoff, self.catalog)
        if not handoff.active_tool:
            stage = self.catalog.stage(handoff.stage)
            verification = VerificationResult(
                verdict=Verdict.OBSERVED,
                severity=Severity.MEDIUM,
                findings=[
                    VerificationFinding(
                        code="knowledge_gap",
                        detail=f"La etapa {handoff.stage} aún no tiene fichas habilitadas",
                    )
                ],
                source_tool_id="",
            )
            return TurnResult(
                message=(
                    f"La etapa {handoff.stage}, «{stage.name}», sí existe en la ruta, "
                    "pero todavía no tiene una ficha metodológica validada. "
                    "No generaré pasos hasta que esa fuente sea incorporada."
                ),
                handoff=handoff,
                verification=verification,
                attempts=1,
                degraded=True,
            )
        tool_card = self.catalog.tool_card(handoff.active_tool)

        previous_verification: VerificationResult | None = None
        for attempt in (1, 2):
            candidate = self.runtime.guide(
                message=message,
                state=state,
                handoff=handoff,
                tool_card=tool_card,
                retry_feedback=previous_verification,
                allowed_fields=self.catalog.tool(handoff.active_tool).template_fields,
            )
            try:
                validate_candidate(candidate, handoff, self.catalog)
            except StructuralViolation as exc:
                verification = VerificationResult(
                    verdict=Verdict.REJECTED,
                    severity=Severity.HIGH,
                    findings=[
                        VerificationFinding(code="structural_violation", detail=str(exc))
                    ],
                    source_tool_id=handoff.active_tool,
                )
            else:
                verification = self.runtime.verify(
                    candidate, handoff, tool_card, message=message, state=state
                )
                if verification.source_tool_id != handoff.active_tool:
                    verification = VerificationResult(
                        verdict=Verdict.REJECTED,
                        severity=Severity.HIGH,
                        findings=[
                            VerificationFinding(
                                code="wrong_verification_source",
                                detail=(
                                    "El verificador declaró una fuente distinta "
                                    "de la ficha activa"
                                ),
                            )
                        ],
                        source_tool_id=handoff.active_tool,
                    )

            self.recorder.record(
                notebook_id=state.notebook_id,
                attempt=attempt,
                handoff=handoff,
                candidate=candidate,
                verification=verification,
            )
            if verification.verdict != Verdict.REJECTED:
                return TurnResult(
                    message=candidate.message,
                    handoff=handoff,
                    verification=verification,
                    attempts=attempt,
                    accepted_updates=(
                        candidate.template_updates
                        if verification.verdict == Verdict.APPROVED
                        else []
                    ),
                )
            previous_verification = verification

        return TurnResult(
            message=SAFE_DEGRADATION,
            handoff=handoff,
            verification=previous_verification,
            attempts=2,
            degraded=True,
        )
