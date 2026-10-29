from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from ..config import Settings
from ..inferencia.modelo_local import cliente_local, llamar_modelo_local
from .runtime import ContractRuntime, T

if TYPE_CHECKING:
    from openai import OpenAI

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
        self.client = client or cliente_local(settings)
        self.calls: list[dict] = []

    def _run(self, agent: object, description: str, output_model: type[T]) -> T:
        role = str(agent)
        thinking = role == "verifier" and self.settings.thinking
        max_tokens = 1536 if thinking else ROLE_MAX_TOKENS.get(
            role, min(self.settings.max_tokens or 384, 384)
        )
        schema_name = re.sub(r"[^a-zA-Z0-9_-]", "_", output_model.__name__)[:64]
        # El modelo pequeño a veces alarga un texto hasta agotar los tokens y el JSON queda
        # cortado. Se repite una vez con otra semilla: con la misma saldría el mismo texto.
        for retry in range(2):
            content, usage = self._llamar(
                role, description, output_model, schema_name, max_tokens, thinking, retry
            )
            try:
                parsed = output_model.model_validate(json.loads(content))
                self._remember(role, description, content)
                break
            except json.JSONDecodeError:
                if retry:
                    raise
        self.calls.append(
            {
                "role": role,
                "schema": schema_name,
                "output": parsed.model_dump(mode="json"),
                "usage": usage,
                "modelo": self.modelo_de(role),
            }
        )
        return parsed

    def _llamar(
        self, role: str, description: str, output_model: type[T], schema_name: str,
        max_tokens: int, thinking: bool, retry: int,
    ) -> tuple[str, dict | None]:
        """Una llamada al modelo local: devuelve el JSON como texto y el uso de tokens.

        `respaldo_claude.ConClaude` reemplaza solo este paso; todo lo demás del turno (roles,
        Planificador, controles en código) sigue igual con cualquier modelo.
        """
        return llamar_modelo_local(
            self.client, self.settings, role=role, messages=self._messages(role, description),
            schema_name=schema_name, schema=output_model.model_json_schema(),
            max_tokens=max_tokens, thinking=thinking, retry=retry,
        )

    def modelo_de(self, role: str) -> str:
        """Modelo que responde por este rol (con el modelo local, el mismo para todos)."""
        return self.settings.model

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

    def review_tree(self, description: str, output_model: type[T]) -> T:
        """Revisión de contenido del árbol; su salida pasa después por
        `herramientas.tree_diagnosis.grounded`."""
        return self._run("tree_reviewer", description, output_model)
