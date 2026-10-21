from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .audit import NullRecorder, VerificationRecorder
from .contracts import (
    DIRECT_KINDS,
    CandidateResponse,
    ExpertiseLevel,
    HandoffContract,
    ProjectState,
    Severity,
    TurnResult,
    Verdict,
    VerificationFinding,
    VerificationResult,
    has_value,
)
from .guardrails import StructuralViolation, validate_candidate, validate_handoff
from .knowledge import KnowledgeCatalog
from .runtime import AgentRuntime, is_thanks, next_step_hint
from .sensitive import DISTRESS_OPENING, SENSITIVE_REPLIES, sensitive_topic, shows_distress
from .service import SAFE_DEGRADATION

# Respuestas fijas: no usan una ficha, así que no pasan por el Metodólogo ni el Verificador.
OUT_OF_SCOPE = (
    "Eso se sale de lo que puedo acompañar: aquí trabajo contigo tu proyecto, con las fichas "
    "de la ruta de innovación. ¿Qué parte de tu proyecto quieres trabajar ahora?"
)
DIRECT_FINDINGS = {
    "saludo": ("greeting", "Saludo: respuesta fija del sistema, sin ficha."),
    "fuera": ("out_of_scope", "El mensaje no trata del proyecto: respuesta fija, sin ficha."),
    "concepto": ("no_card", "No hay una ficha validada sobre ese tema."),
    "sensible": ("sensitive_topic", "Tema sensible: respuesta fija del sistema, sin modelo."),
}


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
        builder.add_node("plan", self._plan)
        builder.add_node("knowledge_gap", self._knowledge_gap)
        builder.add_node("guide", self._guide)
        builder.add_node("verify", self._verify)
        builder.add_node("finalize", self._finalize)
        builder.add_node("degrade", self._degrade)
        builder.add_edge(START, "orchestrate")
        builder.add_conditional_edges(
            "orchestrate",
            self._after_orchestration,
            {"knowledge_gap": "knowledge_gap", "guide": "plan"},
        )
        builder.add_edge("plan", "guide")
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
        return self._con_progreso(TurnResult.model_validate(final["result"]), state)

    def _con_progreso(self, result: TurnResult, state: ProjectState) -> TurnResult:
        """Guarda el avance de las fichas en cada respuesta, también en las fijas.

        Si el turno tuvo Planificador, vale su avance; si no (saludo, tema sensible, otra
        variante), se conserva el que traía el cuaderno.
        """
        progreso = getattr(self.runtime, "progreso_turno", None)
        return result.model_copy(
            update={"progreso": progreso if progreso is not None else state.progreso})

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
                    if not update:  # un paso que no cambió nada (p. ej. «plan» sin Planificador)
                        continue
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
        final_result = self._con_progreso(final_result, state)
        yield {
            "type": "result",
            "result": final_result.model_dump(mode="json"),
            "source_sections": source_sections if not final_result.degraded else [],
        }

    def _orchestrate(self, graph_state: RutaDiaGraphState) -> dict:
        project_state = ProjectState.model_validate(graph_state["project_state"])
        if sensitive_topic(graph_state["message"]):
            # Un tema sensible no se le envía al modelo: lo decide y lo responde el código.
            stage = self.catalog.stage(project_state.stage)
            handoff = self._keep_place(
                HandoffContract(
                    intent="Tema sensible: respuesta fija del sistema.",
                    phase=stage.phase,
                    stage=stage.id,
                    expertise=ExpertiseLevel.NOVEL,
                    context_summary="El mensaje no se envió al modelo.",
                    kind="sensible",
                ),
                project_state,
            )
            return {"handoff": handoff.model_dump(mode="json")}
        handoff = self.runtime.orchestrate(
            graph_state["message"],
            project_state,
            self.catalog.route_index(),
        )
        if handoff.kind in DIRECT_KINDS:
            handoff = self._keep_place(handoff, project_state)
        validate_handoff(handoff, self.catalog)
        update = {"handoff": handoff.model_dump(mode="json")}
        if handoff.active_tool:
            update["tool_card"] = self.catalog.prompt_card(handoff.active_tool)
        return update

    def _keep_place(self, handoff: HandoffContract, state: ProjectState) -> HandoffContract:
        """Un saludo o un pedido ajeno no cambia la etapa ni la ficha en curso del cuaderno."""
        stage = self.catalog.stage(state.stage)
        tool = state.active_tool if state.active_tool in stage.tools else ""
        return HandoffContract(
            intent=handoff.intent,
            phase=stage.phase,
            stage=stage.id,
            expertise=handoff.expertise,
            recommendations=[{"tool_id": tool, "reason": "Ficha en curso."}] if tool else [],
            active_tool=tool,
            context_summary=handoff.context_summary,
            kind=handoff.kind,
        )

    def _plan(self, graph_state: RutaDiaGraphState) -> dict:
        """Planificador: con el avance de la ficha decide qué parte toca (`planificador.py`).

        Es código, no modelo. Si la variante no tiene Planificador, el paso no cambia nada.
        """
        planificar = getattr(self.runtime, "planificar", None)
        if planificar is None:
            return {}
        handoff = planificar(
            graph_state["message"],
            ProjectState.model_validate(graph_state["project_state"]),
            HandoffContract.model_validate(graph_state["handoff"]),
            self.catalog.route_index(),
        )
        return {"handoff": handoff.model_dump(mode="json")}

    @staticmethod
    def _after_orchestration(
        graph_state: RutaDiaGraphState,
    ) -> Literal["knowledge_gap", "guide"]:
        handoff = HandoffContract.model_validate(graph_state["handoff"])
        direct = handoff.kind in DIRECT_KINDS
        return "guide" if handoff.active_tool and not direct else "knowledge_gap"

    def _direct_reply(
        self, handoff: HandoffContract, state: ProjectState, user_message: str = "",
    ) -> dict:
        """Respuesta fija para un saludo, un pedido ajeno, un concepto sin ficha o un tema
        sensible."""
        stage = self.catalog.stage(handoff.stage)
        names = [self.catalog.tool(tool_id).name for tool_id in stage.tools]
        listed = (
            names[0] if len(names) == 1
            else f"{', '.join(names[:-1])} y {names[-1]}" if names else ""
        )
        topic = sensitive_topic(user_message) if handoff.kind == "sensible" else ""
        if topic:
            message = SENSITIVE_REPLIES[topic]
        elif handoff.kind == "saludo" and is_thanks(user_message):
            message = (
                "¡Con gusto! Aquí sigo cuando quieras. "
                "¿Qué parte de tu proyecto trabajamos ahora?"
            )
        elif handoff.kind == "saludo":
            reto = state.context.question.strip()
            message = (
                f"¡Hola! Soy Hilo y te acompaño en tu proyecto con una pregunta a la vez. "
                f"Estás en la etapa {stage.id}, «{stage.name}». "
                + (f"Tu reto es «{reto}». ¿Seguimos con eso?" if reto
                   else "¿Qué reto o problema quieres trabajar hoy?")
            )
        elif handoff.kind == "fuera":
            message = OUT_OF_SCOPE
        elif listed:
            message = (
                "Todavía no tengo una ficha validada sobre eso y prefiero no explicarlo de "
                f"memoria. En esta etapa, «{stage.name}», sí puedo explicarte: {listed}. "
                "¿Cuál quieres ver?"
            )
        else:
            message = (
                "Todavía no tengo una ficha validada sobre eso y prefiero no explicarlo de "
                f"memoria. La etapa {stage.id}, «{stage.name}», aún no tiene fichas habilitadas."
            )
        code, detail = DIRECT_FINDINGS[handoff.kind]
        if topic:
            detail = f"{detail} Categoría: {topic}."
        verification = VerificationResult(
            verdict=Verdict.OBSERVED,
            severity=Severity.LOW,
            findings=[VerificationFinding(code=code, detail=detail)],
            source_tool_id=handoff.active_tool,
        )
        return {
            "verification": verification.model_dump(mode="json"),
            "attempts": 1,
            "result": TurnResult(
                message=message,
                handoff=handoff,
                verification=verification,
                attempts=1,
                # Un concepto sin ficha es una brecha de conocimiento, como una etapa sin fichas.
                degraded=handoff.kind == "concepto",
            ).model_dump(mode="json"),
        }

    def _knowledge_gap(self, graph_state: RutaDiaGraphState) -> dict:
        handoff = HandoffContract.model_validate(graph_state["handoff"])
        if handoff.kind in DIRECT_KINDS:
            state = ProjectState.model_validate(graph_state["project_state"])
            return self._direct_reply(handoff, state, graph_state["message"])
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
            # Con un análisis en curso la cadena la registra el código; ofrecer los
            # campos de la plantilla solo producía actualizaciones que el Verificador rechaza.
            allowed_fields=(
                [] if project_state.locked_tool == handoff.active_tool
                else self.catalog.tool(handoff.active_tool).template_fields
            ),
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

    def _card_preface(self, handoff: HandoffContract) -> str:
        """Texto literal de la ficha que se antepone cuando piden explicar o recomendar.

        Sale de la ficha, no del modelo: por eso no necesita verificación.
        """
        if handoff.kind not in {"explicacion", "recomendacion"} or not handoff.active_tool:
            return ""
        name = self.catalog.tool(handoff.active_tool).name
        what, when, how = (
            self.catalog.card_section(handoff.active_tool, section)
            for section in ("what", "when", "how")
        )
        # «Para elegir…», «Cuando necesitas…», «Al inicio…»: todas leen bien tras «Se usa».
        usage = f"Se usa {when[0].lower()}{when[1:]}" if when else ""
        if handoff.kind == "recomendacion":
            return f"Te recomiendo la ficha **{name}**. {usage or what}".strip()
        if not (what or how):
            return ""
        if what.startswith("-"):  # una ficha que abre con una lista de puntos
            parts = [f"**{name}**", what, *([usage] if usage else [])]
        else:
            parts = [f"**{name}.** {' '.join(part for part in (what, usage) if part)}".strip()]
        if how:
            parts.append(f"**Cómo se usa**\n\n{how}")
        return "\n\n".join(parts)

    def _stage_notice(self, handoff: HandoffContract, state: ProjectState) -> str:
        """Aviso cuando la ficha pedida es de una etapa posterior a la del cuaderno."""
        if not handoff.active_tool or handoff.stage <= state.stage:
            return ""
        here, there = self.catalog.stage(state.stage), self.catalog.stage(handoff.stage)
        name = self.catalog.tool(handoff.active_tool).name
        return (
            f"**{name}** es una ficha de la etapa {there.id}, «{there.name}», y tu cuaderno va "
            f"en la etapa {here.id}, «{here.name}». Te acompaño con ella, pero lo que no se "
            "haya resuelto en las etapas anteriores seguirá pendiente."
        )

    def _opening(self, graph_state: RutaDiaGraphState, handoff: HandoffContract) -> list[str]:
        """Textos fijos del sistema que van antes de lo que escribió el modelo."""
        state = ProjectState.model_validate(graph_state["project_state"])
        return [
            part
            for part in (
                DISTRESS_OPENING if shows_distress(graph_state["message"]) else "",
                self._stage_notice(handoff, state),
            )
            if part
        ]

    def _finalize(self, graph_state: RutaDiaGraphState) -> dict:
        candidate = CandidateResponse.model_validate(graph_state["candidate"])
        verification = VerificationResult.model_validate(graph_state["verification"])
        handoff = HandoffContract.model_validate(graph_state["handoff"])
        parts = [*self._opening(graph_state, handoff), self._card_preface(handoff)]
        return {
            "result": TurnResult(
                message="\n\n".join([*(part for part in parts if part), candidate.message]),
                handoff=handoff,
                verification=verification,
                attempts=graph_state["attempts"],
                accepted_updates=(
                    [update for update in candidate.template_updates if has_value(update.value)]
                    if verification.verdict == Verdict.APPROVED
                    else []
                ),
            ).model_dump(mode="json")
        }

    def _degrade(self, graph_state: RutaDiaGraphState) -> dict:
        handoff = HandoffContract.model_validate(graph_state["handoff"])
        steps = self.catalog.card_section(handoff.active_tool, "how") if handoff.active_tool else ""
        message = SAFE_DEGRADATION
        verification = VerificationResult.model_validate(graph_state["verification"])
        if {finding.code for finding in verification.findings} == {"repeated_question"}:
            # El modelo insistió en la misma pregunta: mejor decirlo y ofrecer el paso que
            # sigue que soltarle a la persona la ficha entera.
            candidate = CandidateResponse.model_validate(graph_state["candidate"])
            following = next_step_hint(candidate.message, graph_state["tool_card"])
            message = "Ya tengo tu respuesta y no quiero repetirte la pregunta. " + (
                f"El paso que sigue en la ficha es: «{following}» ¿Seguimos con eso?"
                if following else "¿Con qué parte de la ficha quieres seguir?"
            )
            message = "\n\n".join([*self._opening(graph_state, handoff), message])
        elif preface := self._card_preface(handoff):
            # Pidieron explicar la ficha y la pregunta del modelo no pasó: la explicación
            # literal de la ficha sigue siendo válida y no depende del modelo. Cubre además las
            # fichas sin «Cómo se usa», que antes caían en el mensaje genérico.
            message = "\n\n".join([
                *self._opening(graph_state, handoff), preface,
                "¿Con qué parte de la ficha quieres que te acompañe?",
            ])
        elif steps:
            name = self.catalog.tool(handoff.active_tool).name
            message = (
                "No logré formular una orientación que pasara la verificación, así que te dejo "
                f"el paso a paso tal como está en la ficha **{name}**:\n\n{steps}\n\n"
                "¿En cuál de estos pasos quieres que te acompañe?"
            )
            message = "\n\n".join([*self._opening(graph_state, handoff), message])
        return {
            "result": TurnResult(
                message=message,
                handoff=graph_state["handoff"],
                verification=graph_state["verification"],
                attempts=2,
                degraded=True,
            ).model_dump(mode="json")
        }
