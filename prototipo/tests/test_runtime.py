import json

import pytest

from ruta_dia_agents.acompanamiento.runtime import explicit_tool_selection, sin_vocativo
from ruta_dia_agents.acompanamiento.sensitive import shows_distress
from ruta_dia_agents.config import Settings
from ruta_dia_agents.conocimiento.knowledge import KnowledgeCatalog


@pytest.mark.parametrize("texto,esperado", [
    ("Doña Gloria, ¿qué se podría combinar con WhatsApp?", "¿Qué se podría combinar con WhatsApp?"),
    ("Carolina, definamos sus necesidades.", "Definamos sus necesidades."),
    ("Doña Gloria: ¿cuál es la oportunidad?", "¿Cuál es la oportunidad?"),
    ("Perfecto, ¿cuál es la siguiente causa?", "Perfecto, ¿cuál es la siguiente causa?"),
    ("Sobre la letra pequeña, ¿por qué ocurre?", "Sobre la letra pequeña, ¿por qué ocurre?"),
    ("Pedro, ¿qué opinas?", "Pedro, ¿qué opinas?"),  # nombre que la persona no dio
])
def test_the_methodologist_does_not_address_the_archetype(texto, esperado):
    assert sin_vocativo(texto, "Nombre y rol: Gloria, afiliada. Carolina, 38 años.") == esperado


@pytest.mark.parametrize("texto", [
    "Estoy cansada, siento que este proyecto no avanza.",
    "Mi proyecto no va para ningún lado.",
])
def test_these_count_as_discouragement(texto):
    assert shows_distress(texto)


@pytest.mark.parametrize("mensaje,ficha", [
    ("Quiero usar la matriz de priorización con cuatro ideas.", "matriz-priorizacion"),
    ("Quiero hacer el mapa de empatía de los afiliados.", "mapa-empatia"),
    ("Quiero usar la ficha de trabajo de campo.", "trabajo-de-campo"),
    ("Quiero redactar la ficha de hipótesis del experimento.", "ficha-hipotesis"),
])
def test_a_tool_is_recognized_with_or_without_connecting_words(mensaje, ficha):
    route = json.loads(KnowledgeCatalog(Settings.from_env().route_path).route_index())
    assert explicit_tool_selection(mensaje, route, 4).endswith(f":{ficha}")
