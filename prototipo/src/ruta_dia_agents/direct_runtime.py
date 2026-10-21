from __future__ import annotations

import json
import re

from openai import OpenAI

from .config import Settings
from .runtime import ContractRuntime, T
from .tree_diagnosis import ModelReview

ROLE_INSTRUCTIONS = {
    "orchestrator": (
        "Eres el Orquestador de Ruta DIA. Clasificas la intención y seleccionas una opción "
        "autorizada. No ejecutas ni explicas herramientas."
    ),
    "methodologist": (
        "Eres el Metodólogo de Ruta DIA. Guías una sola acción usando exclusivamente la ficha "
        "recibida y nunca completas respuestas por el usuario."
    ),
    "verifier": (
        "Eres el Verificador de Ruta DIA. Auditas únicamente la orientación actual contra el "
        "mensaje y la ficha; no corriges ni reescribes la respuesta."
    ),
    "tree_reviewer": (
        "Eres el Revisor del árbol de problemas de Ruta DIA. Señalas errores de estructura "
        "usando solo la ficha y el árbol recibido; no reescribes tarjetas ni propones soluciones."
    ),
    "journey_extractor": (
        "Eres el Lector de notas de Ruta DIA. Copias frases textuales de las notas de una "
        "entrevista y dices a qué etapa y fila del recorrido pertenecen. No redactas, no "
        "resumes y no inventas."
    ),
}
# Fragmento citado más una frase de explicación: algo más que el límite corto por defecto.
# El lector de notas devuelve hasta ocho frases copiadas: necesita más salida.
ROLE_MAX_TOKENS = {"tree_reviewer": 512, "journey_extractor": 900}


class DirectOpenAIRuntime(ContractRuntime):
    """Reutiliza los contratos de Ruta DIA sin ejecutar agentes o crews de CrewAI."""

    def __init__(self, settings: Settings, client: OpenAI | None = None):
        if not settings.base_url:
            raise ValueError(
                "El runtime LangGraph requiere RUTA_DIA_BASE_URL para el servidor local."
            )
        super().__init__(settings)
        self.client = client or OpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key or "local",
            timeout=settings.timeout,
            max_retries=0,
        )
        self.calls: list[dict] = []

    def _run(self, agent: object, description: str, output_model: type[T]) -> T:
        role = str(agent)
        thinking = role == "verifier" and self.settings.thinking
        max_tokens = 1536 if thinking else ROLE_MAX_TOKENS.get(
            role, min(self.settings.max_tokens or 384, 384)
        )
        schema_name = re.sub(r"[^a-zA-Z0-9_-]", "_", output_model.__name__)[:64]
        options = {
            "model": self.settings.model,
            "messages": self._messages(role, description),
            "temperature": self.settings.temperature,
            "max_tokens": max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": output_model.model_json_schema(),
                },
            },
            "extra_body": {
                "chat_template_kwargs": {"enable_thinking": thinking},
            },
        }
        if self.settings.top_p is not None:
            options["top_p"] = self.settings.top_p
        # El modelo pequeño a veces alarga un texto hasta agotar los tokens y el JSON queda
        # cortado. Se repite una vez con otra semilla: con la misma saldría el mismo texto.
        for retry in range(2):
            if self.settings.seed is not None:
                options["seed"] = self.settings.seed + retry
            response = self.client.chat.completions.create(**options)
            content = response.choices[0].message.content
            if not content:
                raise ValueError(f"{role} no devolvió contenido estructurado")
            try:
                parsed = output_model.model_validate(json.loads(content))
                self._remember(role, description, content)
                break
            except json.JSONDecodeError:
                if retry:
                    raise
        usage = response.usage.model_dump() if response.usage else None
        self.calls.append(
            {
                "role": role,
                "schema": schema_name,
                "output": parsed.model_dump(mode="json"),
                "usage": usage,
            }
        )
        return parsed

    def _messages(self, role: str, description: str) -> list[dict]:
        """Cada rol empieza con un contexto limpio: solo su instrucción y su tarea."""
        return [
            {"role": "system", "content": ROLE_INSTRUCTIONS[role]},
            {"role": "user", "content": description},
        ]

    def _remember(self, role: str, description: str, content: str) -> None:
        """Los roles no guardan nada entre llamadas; `variantes.UnSoloAgente` sí."""

    def extract_journey(self, description: str, output_model: type[T]) -> T:
        """Frases de unas notas para el recorrido; `journey_extract.grounded_quotes` comprueba
        después que cada una esté literal en el texto."""
        return self._run("journey_extractor", description, output_model)

    def review_tree(self, description: str) -> ModelReview:
        """Revisión de contenido del árbol; su salida pasa después por `grounded`."""
        return self._run("tree_reviewer", description, ModelReview)
