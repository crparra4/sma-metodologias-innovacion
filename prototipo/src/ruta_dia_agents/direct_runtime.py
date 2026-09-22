from __future__ import annotations

import json
import re

from openai import OpenAI

from .config import Settings
from .runtime import ContractRuntime, T

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
}


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
        max_tokens = 1536 if thinking else min(self.settings.max_tokens or 384, 384)
        schema_name = re.sub(r"[^a-zA-Z0-9_-]", "_", output_model.__name__)[:64]
        options = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": ROLE_INSTRUCTIONS[role]},
                {"role": "user", "content": description},
            ],
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
        if self.settings.seed is not None:
            options["seed"] = self.settings.seed
        if self.settings.top_p is not None:
            options["top_p"] = self.settings.top_p
        response = self.client.chat.completions.create(**options)
        content = response.choices[0].message.content
        if not content:
            raise ValueError(f"{role} no devolvió contenido estructurado")
        parsed = output_model.model_validate(json.loads(content))
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
