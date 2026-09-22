from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .audit import NullRecorder, VerificationRecorder
from .contracts import (
    CandidateResponse,
    HandoffContract,
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
from .service import SAFE_DEGRADATION


class RutaDiaGraphState(TypedDict, total=False):
    message: str
    project_state: dict
    handoff: dict
    tool_card: str
    candidate: dict
    verification: dict
    attempts: int
    result: dict


class LangGraphRutaDia:
    """Flujo explícito Orquestador → Metodólogo → Verificador con un reintento."""

    def __init__(
        self,
        catalog: KnowledgeCatalog,
        runtime: AgentRuntime,
        recorder: VerificationRecorder | None = None,
        checkpointer=None,
    ):
        catalog.require_valid()
        self.catalog = catalog
        self.runtime = runtime
        self.recorder = recorder or NullRecorder()
        builder = StateGraph(RutaDiaGraphState)
        builder.add_node("orchestrate", self._orchestrate)
        builder.add_node("knowledge_gap", self._knowledge_gap)
        builder.add_node("guide", self._guide)
        builder.add_node("verify", self._verify)
        builder.add_node("finalize", self._finalize)
        builder.add_node("degrade", self._degrade)
        builder.add_edge(START, "orchestrate")
        builder.add_conditional_edges(
            "orchestrate",
            self._after_orchestration,
            {"knowledge_gap": "knowledge_gap", "guide": "guide"},
        )
        builder.add_edge("knowledge_gap", END)
        builder.add_edge("guide", "verify")
        builder.add_conditional_edges(
            "verify",
            self._after_verification,
            {"finalize": "finalize", "retry": "guide", "degrade": "degrade"},
        )
        builder.add_edge("finalize", END)
        builder.add_edge("degrade", END)
        self.graph = builder.compile(checkpointer=checkpointer or InMemorySaver())

    def handle_turn(self, message: str, state: ProjectState) -> TurnResult:
        if not message.strip():
            raise ValueError("El mensaje no puede estar vacío")
        final = self.graph.invoke(
            self._turn_input(message, state),
            config={"configurable": {"thread_id": state.notebook_id}},
        )
        return TurnResult.model_validate(final["result"])

    @staticmethod
    def _turn_input(message: str, state: ProjectState) -> dict:
        # Un nuevo turno conserva el cuaderno, pero no hereda el veredicto del turno anterior.
        return {
            "message": message,
            "project_state": state.model_dump(mode="json"),
            "attempts": 0,
            "handoff": {},
            "tool_card": "",
            "candidate": {},
            "verification": {},
            "result": {},
        }

    def stream_turn(
        self, message: str, state: ProjectState, thread_id: str | None = None
    ) -> Iterator[dict]:
        """Eventos reales del grafo; nunca expone una respuesta candidata sin verificar."""
        if not message.strip():
            raise ValueError("El mensaje no puede estar vacío")
        started: dict[str, float] = {}
        final_result = None
        source_sections: list[str] = []
        for part in self.graph.stream(
            self._turn_input(message, state),
            config={"configurable": {"thread_id": thread_id or state.notebook_id}},
            stream_mode=["tasks", "updates"],
            version="v2",
        ):
            data = part["data"]
            if part["type"] == "tasks":
                task_id = data["id"]
                if "input" in data:
                    started[task_id] = time.monotonic()
                    attempt = data["input"].get("attempts", 0)
                    if data["name"] == "guide":
                        attempt += 1
                    yield {
                        "type": "node",
                        "node": data["name"],
                        "status": "started",
                        "attempt": attempt,
                    }
                else:
                    yield {
                        "type": "node",
                        "node": data["name"],
                        "status": "failed" if data.get("error") else "completed",
                        "duration_ms": round(
                            (time.monotonic() - started.pop(task_id, time.monotonic())) * 1000
                        ),
                    }
            elif part["type"] == "updates":
                for update in data.values():
                    if "handoff" in update:
                        yield {"type": "handoff", "handoff": update["handoff"]}
                    if "verification" in update:
                        yield {
                            "type": "verification",
                            "verification": update["verification"],
                        }
                    if "candidate" in update:
                        source_sections = update["candidate"].get("source_sections", [])
                    if "result" in update:
                        final_result = TurnResult.model_validate(update["result"])
        if final_result is None:
            raise RuntimeError("El grafo terminó sin producir un resultado")
        yield {
            "type": "result",
            "result": final_result.model_dump(mode="json"),
            "source_sections": source_sections if not final_result.degraded else [],
        }

    def _orchestrate(self, graph_state: RutaDiaGraphState) -> dict:
        project_state = ProjectState.model_validate(graph_state["project_state"])
        handoff = self.runtime.orchestrate(
            graph_state["message"],
            project_state,
            self.catalog.route_index(),
        )
        validate_handoff(handoff, self.catalog)
        update = {"handoff": handoff.model_dump(mode="json")}
        if handoff.active_tool:
            update["tool_card"] = self.catalog.tool_card(handoff.active_tool)
        return update

    @staticmethod
    def _after_orchestration(
        graph_state: RutaDiaGraphState,
    ) -> Literal["knowledge_gap", "guide"]:
        handoff = HandoffContract.model_validate(graph_state["handoff"])
        return "guide" if handoff.active_tool else "knowledge_gap"

    def _knowledge_gap(self, graph_state: RutaDiaGraphState) -> dict:
        handoff = HandoffContract.model_validate(graph_state["handoff"])
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
        return {
            "verification": verification.model_dump(mode="json"),
            "attempts": 1,
            "result": TurnResult(
                message=(
                    f"La etapa {handoff.stage}, «{stage.name}», sí existe en la ruta, "
                    "pero todavía no tiene una ficha metodológica validada. "
                    "No generaré pasos hasta que esa fuente sea incorporada."
                ),
                handoff=handoff,
                verification=verification,
                attempts=1,
                degraded=True,
            ).model_dump(mode="json"),
        }

    def _guide(self, graph_state: RutaDiaGraphState) -> dict:
        handoff = HandoffContract.model_validate(graph_state["handoff"])
        project_state = ProjectState.model_validate(graph_state["project_state"])
        previous = graph_state.get("verification")
        attempt = graph_state.get("attempts", 0) + 1
        candidate = self.runtime.guide(
            message=graph_state["message"],
            state=project_state,
            handoff=handoff,
            tool_card=graph_state["tool_card"],
            retry_feedback=(VerificationResult.model_validate(previous) if previous else None),
            allowed_fields=self.catalog.tool(handoff.active_tool).template_fields,
        )
        return {"candidate": candidate.model_dump(mode="json"), "attempts": attempt}

    def _verify(self, graph_state: RutaDiaGraphState) -> dict:
        candidate = CandidateResponse.model_validate(graph_state["candidate"])
        handoff = HandoffContract.model_validate(graph_state["handoff"])
        project_state = ProjectState.model_validate(graph_state["project_state"])
        try:
            validate_candidate(candidate, handoff, self.catalog)
        except StructuralViolation as exc:
            verification = VerificationResult(
                verdict=Verdict.REJECTED,
                severity=Severity.HIGH,
                findings=[VerificationFinding(code="structural_violation", detail=str(exc))],
                source_tool_id=handoff.active_tool,
            )
        else:
            verification = self.runtime.verify(
                candidate,
                handoff,
                graph_state["tool_card"],
                message=graph_state["message"],
                state=project_state,
            )
            if verification.source_tool_id != handoff.active_tool:
                verification = VerificationResult(
                    verdict=Verdict.REJECTED,
                    severity=Severity.HIGH,
                    findings=[
                        VerificationFinding(
                            code="wrong_verification_source",
                            detail="El verificador declaró una fuente distinta de la ficha activa",
                        )
                    ],
                    source_tool_id=handoff.active_tool,
                )
        self.recorder.record(
            notebook_id=project_state.notebook_id,
            attempt=graph_state["attempts"],
            handoff=handoff,
            candidate=candidate,
            verification=verification,
        )
        return {"verification": verification.model_dump(mode="json")}

    @staticmethod
    def _after_verification(
        graph_state: RutaDiaGraphState,
    ) -> Literal["finalize", "retry", "degrade"]:
        verification = VerificationResult.model_validate(graph_state["verification"])
        if verification.verdict != Verdict.REJECTED:
            return "finalize"
        return "retry" if graph_state["attempts"] < 2 else "degrade"

    @staticmethod
    def _finalize(graph_state: RutaDiaGraphState) -> dict:
        candidate = CandidateResponse.model_validate(graph_state["candidate"])
        verification = VerificationResult.model_validate(graph_state["verification"])
        return {
            "result": TurnResult(
                message=candidate.message,
                handoff=graph_state["handoff"],
                verification=verification,
                attempts=graph_state["attempts"],
                accepted_updates=(
                    candidate.template_updates
                    if verification.verdict == Verdict.APPROVED
                    else []
                ),
            ).model_dump(mode="json")
        }

    @staticmethod
    def _degrade(graph_state: RutaDiaGraphState) -> dict:
        return {
            "result": TurnResult(
                message=SAFE_DEGRADATION,
                handoff=graph_state["handoff"],
                verification=graph_state["verification"],
                attempts=2,
                degraded=True,
            ).model_dump(mode="json")
        }
