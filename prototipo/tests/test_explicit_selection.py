import json

import pytest

from ruta_dia_agents.config import Settings
from ruta_dia_agents.knowledge import KnowledgeCatalog
from ruta_dia_agents.runtime import explicit_tool_selection


@pytest.fixture
def route():
    return json.loads(KnowledgeCatalog(Settings.from_env().route_path).route_index())


def test_named_tool_overrides_the_previous_tool_in_the_notebook(route):
    assert explicit_tool_selection(
        "Quiero aplicar PESTEL para analizar el entorno de este proyecto.", route, 1
    ) == "1:pestel"


def test_tool_name_alias_supports_accents_and_word_boundaries(route):
    assert explicit_tool_selection("Quiero aplicar cinco porqués", route, 1) == "1:cinco-porques"
    assert explicit_tool_selection("Quiero aplicar PESTELizado", route, 1) is None


@pytest.mark.parametrize("message", [
    "No quiero usar PESTEL",
    "Quiero dejar de usar PESTEL",
    "Quiero comparar PESTEL y cinco porqués",
    "Quiero usar PESTEL y cinco porqués",
    "Ayer utilicé PESTEL, hoy no sé qué sigue",
])
def test_ambiguous_or_negated_tool_mentions_remain_with_the_orchestrator(message, route):
    assert explicit_tool_selection(message, route, 1) is None
