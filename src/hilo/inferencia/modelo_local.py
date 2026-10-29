"""Adaptador del servidor del modelo local (llama.cpp, API compatible con OpenAI).

Es el único lugar del acompañamiento que habla con el modelo local: recibe los mensajes y el
esquema que exige el contrato, y devuelve el JSON como texto y el uso de tokens. El respaldo con
Claude (`respaldo_claude.ConClaude`) reemplaza este mismo paso.
"""

from __future__ import annotations

from openai import OpenAI

from ..config import Settings


def cliente_local(settings: Settings) -> OpenAI:
    if not settings.base_url:
        raise ValueError("El runtime LangGraph requiere RUTA_DIA_BASE_URL para el servidor local.")
    return OpenAI(
        base_url=settings.base_url,
        api_key=settings.api_key or "local",
        timeout=settings.timeout,
        max_retries=0,
    )


def llamar_modelo_local(
    client: OpenAI, settings: Settings, *, role: str, messages: list[dict], schema_name: str,
    schema: dict, max_tokens: int, thinking: bool, retry: int,
) -> tuple[str, dict | None]:
    options = {
        "model": settings.model,
        "messages": messages,
        "temperature": settings.temperature,
        "max_tokens": max_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        },
        "extra_body": {
            "chat_template_kwargs": {"enable_thinking": thinking},
        },
    }
    if settings.top_p is not None:
        options["top_p"] = settings.top_p
    if settings.seed is not None:
        options["seed"] = settings.seed + retry
    response = client.chat.completions.create(**options)
    content = response.choices[0].message.content
    if not content:
        raise ValueError(f"{role} no devolvió contenido estructurado")
    return content, response.usage.model_dump() if response.usage else None
