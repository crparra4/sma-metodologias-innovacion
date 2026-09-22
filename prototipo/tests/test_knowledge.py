from ruta_dia_agents.config import Settings
from ruta_dia_agents.knowledge import KnowledgeCatalog


def test_route_references_only_existing_cards():
    catalog = KnowledgeCatalog(Settings.from_env().route_path)
    assert catalog.validate() == []
    assert len(catalog.route.stages) == 10
    assert len(catalog.route.tools) == 15


def test_agent_scopes_are_different():
    catalog = KnowledgeCatalog(Settings.from_env().route_path)
    index = catalog.route_index()
    card = catalog.tool_card("mapa-empatia")

    assert "mapa-empatia" in index
    assert "¿Qué piensa y siente?" not in index
    assert "¿Qué piensa y siente?" in card

