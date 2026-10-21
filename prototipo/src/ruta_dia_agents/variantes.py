"""Variantes para el estudio de ablación: ¿hace falta repartir el trabajo en varios agentes?

La interfaz no las usa; solo la batería de `tesis/pruebas-ablacion-*`. Las tres corren el mismo
grafo, con las mismas fichas, las mismas reglas en código y el mismo modelo. Cambia quién llama
al modelo y con qué contexto:

- (a) `DirectOpenAIRuntime`: tres roles, cada uno con su instrucción y un contexto limpio. El
  Verificador es un modelo (con razonamiento si `RUTA_DIA_THINKING`) más los controles en código.
- (c) `SoloControlesEnCodigo`: Orquestador y Metodólogo iguales que en (a); el Verificador no
  llama al modelo y quedan solo los controles deterministas de `grounded_verdict`.
- (d) `UnSoloAgente`: un único agente, con una sola instrucción y una conversación que se
  acumula durante el turno: elige la ficha, la lee y responde viendo todo lo anterior, incluido
  su intento rechazado. Verificación solo en código, como en (c).

Intérprete (20 oct 2026), sobre (c). La evaluación exigente mostró que lo más débil es la
escucha: Hilo no respondía las dudas de la persona y, ante una duda puntual, pegaba la ficha
completa. Las dos variantes leen el turno (pregunta, datos dados, confusión), convierten la duda
puntual en una aclaración breve dentro del turno de trabajo y le pasan la lectura al Metodólogo:

- (e) `InterpreteAmpliado`: el Orquestador hace también de Intérprete (mismas llamadas).
- (f) `InterpreteAparte`: un agente Intérprete propio lee el turno antes del Orquestador
  (una llamada más).

Planificador (20 oct 2026), al estilo de KELE, StratL e IntelliCode: el avance de la ficha vive
fuera del modelo (`planificador.py`), el Planificador decide qué parte toca, el Metodólogo solo
redacta esa pregunta y el Verificador rechaza preguntar por partes ya respondidas:

- (g) `PlanificadorConControles`: sobre (c).
- (h) `PlanificadorUnSoloAgente`: el mismo avance, con un solo agente (comparación justa: separa
  el aporte de la información del aporte de los roles).
"""

from __future__ import annotations

import json
import re

from pydantic import Field, create_model

from .contracts import (
    CandidateResponse,
    HandoffContract,
    ProjectState,
    Severity,
    StrictModel,
    Verdict,
    VerificationAssessment,
    VerificationFinding,
    VerificationResult,
)
from .direct_runtime import DirectOpenAIRuntime
from .knowledge import KnowledgeCatalog
from .planificador import (
    antes_de_la_pregunta,
    bloque_para_metodologo,
    cierre,
    consejo_de_la_ficha,
    es_duda,
    partes_de,
    partes_repetidas,
    planear,
)
from .runtime import grounded_verdict, mentioned_tool

AGENTE_UNICO = (
    "Eres el asistente metodológico de Ruta DIA. En cada turno primero clasificas la intención "
    "y eliges una opción autorizada; después guías una sola acción usando exclusivamente la "
    "ficha elegida y nunca completas respuestas por el usuario."
)


class SoloControlesEnCodigo(DirectOpenAIRuntime):
    """(c) El Verificador no consulta al modelo: una evaluación vacía deja solo el código."""

    def verify(
        self,
        candidate: CandidateResponse,
        handoff: HandoffContract,
        tool_card: str,
        *,
        message: str = "",
        state: ProjectState | None = None,
    ) -> VerificationResult:
        return grounded_verdict(
            VerificationAssessment(), candidate, handoff, tool_card, message, state,
        )


class UnSoloAgente(SoloControlesEnCodigo):
    """(d) Una sola instrucción y un solo contexto por turno, en vez de un rol por llamada."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversation: list[dict] = []

    def orchestrate(self, message: str, state: ProjectState, route_index: str):
        # Cada turno empieza de cero, igual que en (a): lo anterior llega en el estado.
        self.conversation = []
        return super().orchestrate(message, state, route_index)

    def _messages(self, role: str, description: str) -> list[dict]:
        if role not in {self.orchestrator, self.methodologist}:
            return super()._messages(role, description)  # árbol y notas: su propio rol
        return [
            {"role": "system", "content": AGENTE_UNICO},
            *self.conversation,
            {"role": "user", "content": description},
        ]

    def _remember(self, role: str, description: str, content: str) -> None:
        if role not in {self.orchestrator, self.methodologist}:
            return
        self.conversation += [
            {"role": "user", "content": description},
            {"role": "assistant", "content": content},
        ]


# ------------------------------------------------------------------ Intérprete: (e) y (f)

class LecturaTurno(StrictModel):
    """Lo que la persona dijo en este turno, para que el Metodólogo la escuche."""

    pregunta_de_la_persona: str = ""
    datos_aportados: list[str] = Field(default_factory=list, max_length=6)
    confundida: bool = False


INSTRUCCION_INTERPRETE = (
    "Eres el Intérprete de Ruta DIA. Lees el mensaje de la persona y dices qué preguntó, qué "
    "datos dio y si está confundida. No respondes, no guías y no eliges herramientas."
)
REGLAS_LECTURA = """
Lectura del mensaje de la persona:
- pregunta_de_la_persona: copia la duda o pregunta concreta que hizo en este mensaje sobre su
  trabajo (por ejemplo «¿eso cuenta como político?» o «¿qué significa normativa?»). Escribe ""
  si no preguntó nada o si solo pide empezar o seguir.
- datos_aportados: datos concretos que dio en este mensaje, cada uno en pocas palabras y con sus
  términos; [] si no dio ninguno.
- confundida: true solo si dice que no entiende, que no sabe qué hacer o repite su duda.""".strip()
PALABRAS_ACLARACION = 45


def aclaracion_breve(texto: str) -> str:
    """Hasta dos frases y 45 palabras, sin preguntas: la única pregunta va en `message`."""
    frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+", texto.strip()) if f.strip()]
    frases = [f for f in frases if "?" not in f][:2]
    palabras = " ".join(frases).split()
    if len(palabras) > PALABRAS_ACLARACION:
        return " ".join(palabras[:PALABRAS_ACLARACION]).rstrip(",;:") + "…"
    return " ".join(palabras)


class _ConInterprete(SoloControlesEnCodigo):
    """Lectura del turno + aclaración breve. Las subclases deciden quién hace la lectura."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lectura: LecturaTurno | None = None
        self.aclaracion = ""

    def _leer_turno(self, message: str, state: ProjectState) -> None:
        """(f) llama aquí a su Intérprete; en (e) la lectura llega con el Orquestador."""

    def orchestrate(self, message: str, state: ProjectState, route_index: str):
        self.lectura = None
        self._leer_turno(message, state)
        handoff = super().orchestrate(message, state, route_index)
        pregunta = self.lectura.pregunta_de_la_persona if self.lectura else ""
        if (pregunta and handoff.kind == "explicacion" and handoff.active_tool
                and not mentioned_tool(message, json.loads(route_index))):
            # Una duda puntual dentro de la ficha no pide la ficha completa: se aclara y se sigue.
            return handoff.model_copy(update={
                "kind": "trabajo",
                "intent": "Aclarar la duda de la persona y seguir con la ficha.",
            })
        return handoff

    def guide(self, *args, **kwargs):
        # La aclaración se une después del filtro de relleno de `guide`, que la borraría por
        # no venir de la persona, y antes de los controles del Verificador, que la revisan.
        self.aclaracion = ""
        candidate = super().guide(*args, **kwargs)
        if not self.aclaracion:
            return candidate
        return candidate.model_copy(
            update={"message": f"{self.aclaracion}\n\n{candidate.message}"})

    def _run(self, agent, description, output_model):
        if str(agent) == self.methodologist and self.lectura is not None:
            return self._guiar_con_lectura(description, output_model)
        return super()._run(agent, description, output_model)

    def _guiar_con_lectura(self, description, output_model):
        lectura = self.lectura
        bloques = []
        if lectura.datos_aportados:
            bloques.append(
                "DATOS QUE LA PERSONA ACABA DE DAR (dalos por recibidos; no los vuelvas a "
                "pedir):\n" + "\n".join(f"- {dato}" for dato in lectura.datos_aportados))
        if lectura.confundida:
            bloques.append(
                "LA PERSONA ESTÁ CONFUNDIDA: usa palabras sencillas y pregúntale algo que pueda "
                "responder con lo que sabe.")
        pregunta = lectura.pregunta_de_la_persona
        modelo = output_model
        if pregunta:
            bloques.append(
                f"LA PERSONA PREGUNTÓ: «{pregunta}»\n"
                "- En aclaracion respóndele en una o dos frases cortas, con lo que dice la ficha o "
                "con lo que ella misma contó. Si la ficha no lo responde, dilo y sugiere cómo "
                "averiguarlo. No inventes leyes, cifras ni datos.\n"
                "- En message haz después tu única pregunta, como siempre.")
            modelo = create_model(output_model.__name__, __base__=output_model,
                                  aclaracion=(str, ...))
        texto = description + ("\n\n" + "\n\n".join(bloques) if bloques else "")
        salida = super()._run(self.methodologist, texto, modelo)
        if modelo is output_model:
            return salida
        datos = salida.model_dump()
        self.aclaracion = aclaracion_breve(datos.pop("aclaracion", ""))
        return output_model.model_validate(datos)


class InterpreteAmpliado(_ConInterprete):
    """(e) El Orquestador también lee a la persona: misma cantidad de llamadas que (c)."""

    def _run(self, agent, description, output_model):
        if str(agent) == self.orchestrator and output_model.__name__ == "RouteDecision":
            modelo = create_model(
                "RouteDecision", __base__=output_model,
                pregunta_de_la_persona=(str, ...), datos_aportados=(list[str], ...),
                confundida=(bool, ...),
            )
            salida = super()._run(agent, f"{description}\n\n{REGLAS_LECTURA}", modelo)
            self.lectura = LecturaTurno(
                pregunta_de_la_persona=salida.pregunta_de_la_persona,
                datos_aportados=salida.datos_aportados[:6],
                confundida=salida.confundida,
            )
            return salida
        return super()._run(agent, description, output_model)


class InterpreteAparte(_ConInterprete):
    """(f) Un agente Intérprete propio, con su instrucción y su contrato, antes del Orquestador."""

    interpreter = "interpreter"

    def _leer_turno(self, message: str, state: ProjectState) -> None:
        recientes = "\n".join(state.recent_turns[-4:]) or "Sin turnos anteriores."
        descripcion = (
            "Devuelve la lectura de este turno.\n\n"
            f"MENSAJE DE LA PERSONA:\n{message}\n\n"
            f"CONVERSACIÓN RECIENTE:\n{recientes}\n\n"
            f"FICHA EN CURSO: {state.active_tool or 'ninguna'}\n\n{REGLAS_LECTURA}"
        )
        try:
            self.lectura = super()._run(self.interpreter, descripcion, LecturaTurno)
        except Exception:
            self.lectura = None  # sin lectura, el turno sigue como en (c)

    def _messages(self, role: str, description: str) -> list[dict]:
        if role == self.interpreter:
            return [{"role": "system", "content": INSTRUCCION_INTERPRETE},
                    {"role": "user", "content": description}]
        return super()._messages(role, description)


# ------------------------------------------------------------------ Planificador: (g) y (h)

class _ConPlanificador:
    """El Planificador lleva el avance; el Metodólogo redacta solo la parte que toca."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plan = None
        self.progreso_turno: dict | None = None  # lo guarda el grafo con la respuesta

    def orchestrate(self, message: str, state: ProjectState, route_index: str):
        self.plan, self.progreso_turno = None, None
        return super().orchestrate(message, state, route_index)

    def planificar(self, message: str, state: ProjectState, handoff: HandoffContract,
                   route_index: str) -> HandoffContract:
        """Nodo «plan» del grafo: actualiza el avance y decide la parte que toca."""
        ficha = handoff.active_tool
        if state.locked_tool or not ficha or not partes_de(ficha):
            return handoff
        if (handoff.kind == "explicacion" and es_duda(message)
                and not mentioned_tool(message, json.loads(route_index))):
            # Una duda puntual dentro de la ficha se aclara con la ficha y se sigue.
            handoff = handoff.model_copy(update={
                "kind": "trabajo", "intent": "Aclarar la duda y seguir con la ficha."})
        if handoff.kind not in {"trabajo", "explicacion", "recomendacion"}:
            return handoff
        self.plan = planear(ficha, state.progreso.get(ficha), message, state.context.question)
        self.progreso_turno = {**state.progreso, ficha: self.plan.progreso}
        return handoff

    def guide(self, message, state, handoff, tool_card, retry_feedback=None,
              allowed_fields=None):
        plan = self.plan
        if plan is None:
            return super().guide(message, state, handoff, tool_card, retry_feedback,
                                 allowed_fields)
        if plan.intencion == "cerrar":
            titulo = re.search(r"^#\s+(.+)$", tool_card, re.MULTILINE)
            secciones = re.findall(r"^#{1,6}\s+(.+)$", tool_card, re.MULTILINE)
            return CandidateResponse(
                message=cierre(plan, titulo.group(1).strip() if titulo else handoff.active_tool,
                               self._siguiente_ficha(handoff.active_tool)),
                tool_id=handoff.active_tool,
                next_step="Revisar una parte o pasar a la siguiente ficha",
                source_sections=[secciones[0].strip()] if secciones else [],
            )
        candidate = super().guide(message, state, handoff, tool_card, retry_feedback,
                                  allowed_fields)
        # Textos del código (aclaración literal de la ficha, nota de «no sabe») antes de la
        # pregunta; se unen después del filtro de relleno de `guide`, que los borraría.
        mensaje = candidate.message
        anterior = (state.progreso.get(handoff.active_tool) or {}).get("en_curso")
        # Al llegar a una parte nueva, el consejo que la ficha da en ese paso (literal).
        if (plan.intencion == "preguntar" and plan.objetivo.id != anterior
                and (consejo := consejo_de_la_ficha(plan.objetivo, tool_card))):
            mensaje = antes_de_la_pregunta(mensaje, f"Un consejo de la ficha: «{consejo}»")
        previo = " ".join(texto for texto in (plan.aclaracion, plan.nota) if texto)
        if previo:
            mensaje = f"{previo}\n\n{mensaje}"
        if mensaje == candidate.message:
            return candidate
        return candidate.model_copy(update={"message": mensaje})

    def _siguiente_ficha(self, tool_id: str) -> str:
        """Nombre de la herramienta que sigue en la ruta (misma etapa o la siguiente)."""
        if not hasattr(self, "_orden_ruta"):
            ruta = KnowledgeCatalog(self.settings.route_path).route
            nombres = {tool.id: tool.name for tool in ruta.tools}
            self._orden_ruta = [(t, nombres.get(t, t)) for etapa in ruta.stages
                                for t in etapa.tools]
        ids = [t for t, _ in self._orden_ruta]
        if tool_id not in ids:
            return ""
        siguientes = self._orden_ruta[ids.index(tool_id) + 1:]
        return siguientes[0][1] if siguientes else ""

    def _run(self, agent, description, output_model):
        if str(agent) == self.methodologist and self.plan is not None and self.plan.objetivo:
            plan = bloque_para_metodologo(self.plan, self.estilo_natural)
            description = f"{description}\n\n{plan}"
        return super()._run(agent, description, output_model)

    def verify(self, candidate, handoff, tool_card, *, message="", state=None):
        result = super().verify(candidate, handoff, tool_card, message=message, state=state)
        plan = self.plan
        if plan is None or plan.intencion == "cerrar":
            return result
        repetidas = partes_repetidas(candidate.message, plan)
        if not repetidas:
            return result
        hallazgo = VerificationFinding(
            code="repeated_known_field",
            detail=(
                "La persona ya respondió (o dijo que no sabe) "
                + ", ".join(f"«{p.nombre}»" for p in repetidas)
                + f". Pregunta solo por «{plan.objetivo.nombre}»."
            ),
        )
        return result.model_copy(update={
            "verdict": Verdict.REJECTED, "severity": Severity.HIGH,
            "findings": [*result.findings, hallazgo],
        })


class PlanificadorConControles(_ConPlanificador, SoloControlesEnCodigo):
    """(g) Planificador + Metodólogo + Verificador en código, sobre (c)."""


class PlanificadorUnSoloAgente(_ConPlanificador, UnSoloAgente):
    """(h) El mismo avance con un solo agente: separa información de roles."""


VARIANTES = {
    "a": DirectOpenAIRuntime,
    "c": SoloControlesEnCodigo,
    "d": UnSoloAgente,
    "e": InterpreteAmpliado,
    "f": InterpreteAparte,
    "g": PlanificadorConControles,
    "h": PlanificadorUnSoloAgente,
}
