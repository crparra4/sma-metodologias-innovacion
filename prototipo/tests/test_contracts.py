import pytest
from pydantic import ValidationError

from ruta_dia_agents.contracts import ExpertiseLevel, HandoffContract, ToolRecommendation


def test_handoff_rejects_more_than_three_recommendations():
    recommendations = [
        ToolRecommendation(tool_id=f"tool-{number}", reason="prueba")
        for number in range(4)
    ]

    with pytest.raises(ValidationError):
        HandoffContract(
            intent="orientacion",
            phase="Descubrimiento",
            stage=1,
            expertise=ExpertiseLevel.NOVEL,
            recommendations=recommendations,
            active_tool="tool-0",
            context_summary="prueba",
        )


def test_active_tool_must_be_recommended():
    with pytest.raises(ValidationError):
        HandoffContract(
            intent="orientacion",
            phase="Descubrimiento",
            stage=1,
            expertise=ExpertiseLevel.NOVEL,
            recommendations=[ToolRecommendation(tool_id="pestel", reason="prueba")],
            active_tool="arbol-problemas",
            context_summary="prueba",
        )


def test_empty_recommendations_require_empty_active_tool():
    contract = HandoffContract(
        intent="brecha_conocimiento",
        phase="Incubación",
        stage=7,
        expertise=ExpertiseLevel.NOVEL,
        recommendations=[],
        active_tool="",
        context_summary="Etapa aún sin fichas",
    )

    assert contract.active_tool == ""
