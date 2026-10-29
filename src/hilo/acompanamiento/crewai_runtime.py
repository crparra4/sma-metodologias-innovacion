"""Adaptador heredado: los tres agentes con CrewAI en lugar de llamadas directas al modelo.

La aplicación web no lo usa (corre `acompanamiento.direct_runtime` y sus variantes); queda para
la línea de comandos (`--runtime crewai`) y para `evaluacion.evaluation`. Va en su propio módulo
para que `runtime.py`, con los contratos y las reglas de los agentes, no dependa de CrewAI.
"""

from __future__ import annotations

import json

from crewai import LLM, Agent, Crew, Process, Task

from ..config import Settings
from .runtime import ContractRuntime, T


def build_llm(settings: Settings, *, thinking: bool | None = None, **overrides):
    thinking_enabled = settings.thinking if thinking is None else thinking
    options = {"model": settings.model, "temperature": settings.temperature}
    if settings.base_url:
        options.update(
            custom_openai=True,
            base_url=settings.base_url,
            api_key=settings.api_key or "local",
            timeout=settings.timeout,
            max_retries=0,
            additional_params={
                "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": thinking_enabled},
                }
            },
        )
    if settings.max_tokens is not None:
        options["max_tokens"] = settings.max_tokens
    if settings.seed is not None:
        options["seed"] = settings.seed
    if settings.top_p is not None:
        options["top_p"] = settings.top_p
    options.update(overrides)
    return LLM(**options)



class CrewAIRuntime(ContractRuntime):
    """Tres agentes CrewAI aislados; el servicio controla sus conexiones."""

    def __init__(self, settings: Settings, llm=None, verifier_llm=None):
        self.settings = settings
        self.llm = (
            llm
            if llm is not None
            else build_llm(
                settings,
                thinking=False,
                max_tokens=min(settings.max_tokens or 384, 384),
            )
        )
        self.verifier_llm = (
            verifier_llm
            if verifier_llm is not None
            else (
                llm
                if llm is not None
                else build_llm(
                    settings,
                    thinking=settings.thinking,
                    max_tokens=(
                        1536
                        if settings.thinking
                        else min(settings.max_tokens or 384, 384)
                    ),
                )
            )
        )
        common = {
            "allow_delegation": False,
            "verbose": settings.verbose,
            "max_retry_limit": settings.agent_max_retry_limit,
        }
        self.orchestrator = Agent(
            role="Orquestador de la ruta de innovación",
            goal=(
                "Determinar intención, etapa, experticia y hasta tres herramientas válidas "
                "sin explicar ni ejecutar ninguna herramienta."
            ),
            backstory=(
                "Eres un coordinador estricto. Solo utilizas el índice de ruta recibido y "
                "entregas decisiones pequeñas, trazables y aptas para usuarios no expertos."
            ),
            max_iter=3,
            llm=self.llm,
            **common,
        )
        self.methodologist = Agent(
            role="Metodólogo de innovación",
            goal=(
                "Guiar un único paso de la herramienta activa con lenguaje claro y "
                "divulgación progresiva, usando exclusivamente la ficha recibida."
            ),
            backstory=(
                "Eres facilitador metodológico. No inventas pasos, no mezclas herramientas "
                "y no expones al usuario a información que todavía no necesita."
            ),
            max_iter=4,
            llm=self.llm,
            **common,
        )
        self.verifier = Agent(
            role="Verificador metodológico",
            goal=(
                "Dictaminar si la respuesta candidata está respaldada por la ficha, sin "
                "corregir ni reescribir la respuesta."
            ),
            backstory=(
                "Evalúas únicamente la intervención actual. Comparas afirmaciones y pasos contra "
                "una sola fuente y describes hallazgos concretos."
            ),
            max_iter=3,
            llm=self.verifier_llm,
            **common,
        )

    def _run(self, agent: Agent, description: str, output_model: type[T]) -> T:
        task = Task(
            description=description,
            expected_output=(
                "Un objeto estructurado que cumpla exactamente el esquema solicitado, "
                "sin texto adicional."
            ),
            agent=agent,
            output_pydantic=output_model,
        )
        result = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=self.settings.verbose,
            memory=False,
        ).kickoff()
        if result.pydantic is not None:
            return output_model.model_validate(result.pydantic)
        if result.json_dict:
            return output_model.model_validate(result.json_dict)
        return output_model.model_validate(json.loads(result.raw))
