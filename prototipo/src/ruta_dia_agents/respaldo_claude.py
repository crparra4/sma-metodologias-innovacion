"""Respaldo con Claude cuando el modelo local no responde.

Hilo usa el modelo local (Qwen en llama.cpp). Si no responde —por ejemplo, porque el computador
que lo sirve está apagado— y el respaldo está activo (`RUTA_DIA_RESPALDO_CLAUDE`), el turno lo
atiende Claude por la API. Cambia solo la llamada al modelo (`DirectOpenAIRuntime._llamar`): los
roles, el Planificador, el Verificador y los controles en código son los mismos.

El modelo se elige por agente: el Metodólogo redacta lo que lee la persona y es donde más pesa la
capacidad (Opus por defecto); el Orquestador clasifica y elige ficha, y el Cliente simulado hace
de personaje (Sonnet por defecto). Cada llamada se suma a un registro de gasto y, al llegar al
tope, el respaldo deja de usarse.

Lo que se envía a Claude sale del equipo: el consentimiento informado de las pruebas debe
decirlo.
"""

from __future__ import annotations

import copy
import json
import threading
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from .cliente_simulado import mensajes_entrevista
from .config import Settings

# USD por millón de tokens (entrada, salida). Un modelo que no esté aquí (por ejemplo, el que
# responde cuando el pedido se reenvía por una negativa) se cobra con la tarifa más alta.
PRECIOS = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0)}
PRECIO_DESCONOCIDO = (5.0, 25.0)
# Si el modelo declina un pedido, la API lo reintenta con el modelo de reserva que recomienda.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 8000  # incluye el razonamiento del modelo; con esfuerzo bajo usa muy poco

# Restricciones que la salida estructurada de la API no admite: se quitan del esquema y el
# contrato original de Hilo las valida después con Pydantic.
_SIN_SOPORTE = {"minLength", "maxLength", "maxItems", "minimum", "maximum", "multipleOf",
                "exclusiveMinimum", "exclusiveMaximum", "pattern", "default", "title"}


class ModeloNoDisponible(RuntimeError):
    """Ni el modelo local ni el respaldo pueden atender el turno."""


def esquema_para_claude(modelo) -> dict:
    """Esquema JSON del contrato, en la forma que acepta la salida estructurada de Claude."""

    def limpiar(nodo):
        if isinstance(nodo, list):
            return [limpiar(n) for n in nodo]
        if not isinstance(nodo, dict):
            return nodo
        nodo = {k: limpiar(v) for k, v in nodo.items() if k not in _SIN_SOPORTE}
        if nodo.get("minItems", 0) > 1:
            nodo.pop("minItems")
        if nodo.get("type") == "object" or "properties" in nodo:
            nodo["additionalProperties"] = False
            nodo.setdefault("properties", {})
            for nombre, propiedad in nodo["properties"].items():
                if not any(k in propiedad for k in ("type", "anyOf", "oneOf", "allOf", "$ref",
                                                    "enum", "const")):
                    nodo["properties"][nombre] = {"type": "string"}  # `Any` → texto
        return nodo

    return limpiar(copy.deepcopy(modelo.model_json_schema()))


def costo(modelo: str, uso) -> float:
    entrada, salida = PRECIOS.get(modelo, PRECIO_DESCONOCIDO)
    escritos = getattr(uso, "cache_creation_input_tokens", None) or 0
    leidos_cache = getattr(uso, "cache_read_input_tokens", None) or 0
    leidos = uso.input_tokens + escritos * 1.25 + leidos_cache * 0.1
    return (leidos * entrada + uso.output_tokens * salida) / 1_000_000


class Gasto:
    """Lo gastado en Claude, en un JSONL de la carpeta de datos, con un tope en dólares."""

    def __init__(self, ruta: Path, tope: float):
        self.ruta = ruta
        self.tope = tope
        self._candado = threading.Lock()
        self._total = 0.0
        if ruta.exists():
            for linea in ruta.read_text(encoding="utf-8").splitlines():
                try:
                    self._total += float(json.loads(linea)["usd"])
                except (ValueError, KeyError):
                    continue

    @property
    def total(self) -> float:
        return self._total

    def disponible(self) -> bool:
        return self._total < self.tope

    def registrar(self, rol: str, modelo: str, uso) -> float:
        usd = costo(modelo, uso)
        fila = {"t": datetime.now(UTC).isoformat(timespec="seconds"), "rol": rol,
                "modelo": modelo, "entrada": uso.input_tokens, "salida": uso.output_tokens,
                "usd": round(usd, 6)}
        with self._candado:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            with self.ruta.open("a", encoding="utf-8") as archivo:
                archivo.write(json.dumps(fila) + "\n")
            self._total += usd
        return usd


def _texto(respuesta) -> str:
    return next((b.text for b in respuesta.content if b.type == "text"), "")


class ConClaude:
    """Mezcla para cualquier runtime de `variantes.py`: Claude atiende la llamada al modelo."""

    claude = None  # cliente de la API (`anthropic.Anthropic`); lo pone `Respaldo.runtime`
    estilo_natural = True  # un modelo capaz reconoce lo dicho y sugiere sin inventar
    gasto: Gasto

    def modelo_de(self, role: str) -> str:
        if role == "methodologist":
            return self.settings.claude_metodologo
        return self.settings.claude_modelo

    def _pedir(self, role: str, modelo: str, sistema: str, mensajes: list[dict],
               output_config: dict):
        respuesta = self.claude.beta.messages.create(
            model=modelo, max_tokens=MAX_TOKENS, system=sistema, messages=mensajes,
            output_config=output_config, betas=[FALLBACK_BETA], fallbacks="default",
        )
        self.gasto.registrar(role, respuesta.model, respuesta.usage)
        if respuesta.stop_reason == "refusal":
            raise RuntimeError(f"{role}: Claude declinó responder")
        return respuesta

    def _llamar(self, role, description, output_model, schema_name, max_tokens, thinking,
                retry):
        mensajes = self._messages(role, description)
        sistema, resto = mensajes[0]["content"], mensajes[1:]
        config = {"effort": "low",
                  "format": {"type": "json_schema", "schema": esquema_para_claude(output_model)}}
        texto = ""
        for _ in range(2):  # un reintento si la salida no cumple el contrato original
            respuesta = self._pedir(role, self.modelo_de(role), sistema, resto, config)
            texto = _texto(respuesta)
            try:
                output_model.model_validate(json.loads(texto))
                break
            except (ValidationError, json.JSONDecodeError):
                continue
        uso = respuesta.usage
        leidos = (uso.input_tokens + (getattr(uso, "cache_read_input_tokens", None) or 0)
                  + (getattr(uso, "cache_creation_input_tokens", None) or 0))
        return texto, {"prompt_tokens": leidos, "completion_tokens": uso.output_tokens}

    def responder_cliente(self, persona: str, reto: str, turnos: list[dict],
                          pregunta: str) -> str:
        """El Cliente simulado con Claude: el mismo personaje y la misma entrevista."""
        mensajes = mensajes_entrevista(persona, reto, turnos, pregunta)
        respuesta = self._pedir("client", self.settings.claude_modelo, mensajes[0]["content"],
                                mensajes[1:], {"effort": "low"})
        texto = _texto(respuesta).strip()
        if not texto:
            raise ValueError("El cliente simulado no respondió")
        return texto


class Respaldo:
    """Crea runtimes que responden con Claude y lleva la cuenta del gasto."""

    def __init__(self, settings: Settings, cliente=None):
        if cliente is None:
            import anthropic  # la clave sale de ANTHROPIC_API_KEY

            cliente = anthropic.Anthropic(timeout=120, max_retries=2)
        self.cliente = cliente
        ruta = settings.claude_gasto_path or settings.memory_path.parent / "gasto-claude.jsonl"
        self.gasto = Gasto(ruta, settings.claude_tope_usd)
        self._clases: dict[type, type] = {}

    def disponible(self) -> bool:
        return self.gasto.disponible()

    def runtime(self, base: type, settings: Settings):
        clase = self._clases.get(base)
        if clase is None:
            clase = self._clases[base] = type(f"{base.__name__}ConClaude", (ConClaude, base), {})
        runtime = clase(settings)
        runtime.claude = self.cliente
        runtime.gasto = self.gasto
        return runtime
