import pytest

from ruta_dia_agents.config import Settings
from ruta_dia_agents.contracts import (
    CandidateResponse,
    ExpertiseLevel,
    HandoffContract,
    TemplateUpdate,
    ToolRecommendation,
)
from ruta_dia_agents.guardrails import StructuralViolation, validate_candidate, validate_handoff
from ruta_dia_agents.knowledge import KnowledgeCatalog


@pytest.fixture
def catalog():
    return KnowledgeCatalog(Settings.from_env().route_path)


def _handoff(tool_id="pestel", stage=1):
    return HandoffContract(
        intent="orientacion",
        phase="Descubrimiento",
        stage=stage,
        expertise=ExpertiseLevel.NOVEL,
        recommendations=[ToolRecommendation(tool_id=tool_id, reason="prueba")],
        active_tool=tool_id,
        context_summary="prueba",
    )


def test_rejects_tool_from_another_stage(catalog):
    with pytest.raises(StructuralViolation):
        validate_handoff(_handoff(tool_id="mapa-empatia", stage=1), catalog)


def test_rejects_unknown_template_field(catalog):
    handoff = _handoff()
    candidate = CandidateResponse(
        message="Vamos a comenzar.",
        tool_id="pestel",
        next_step="Describe el factor político.",
        template_updates=[TemplateUpdate(field="inventado", value="dato")],
    )

    with pytest.raises(StructuralViolation):
        validate_candidate(candidate, handoff, catalog)


@pytest.mark.parametrize("section", ["Cómo se usa (paso a paso)", "## Cómo se usa (paso a paso)"])
def test_accepts_real_heading_and_empty_technical_updates(catalog, section):
    candidate = CandidateResponse(
        message="¿Qué aspecto del entorno observaste?",
        tool_id="pestel",
        next_step="Indicar un aspecto del entorno.",
        source_sections=[section],
        template_updates=[],
    )
    validate_candidate(candidate, _handoff(), catalog)


@pytest.mark.parametrize("sections", [[], ["Entrevistas obligatorias"], ["Cómo se usa"]])
def test_rejects_missing_or_invented_source_headings(catalog, sections):
    candidate = CandidateResponse(
        message="¿Qué aspecto del entorno observaste?",
        tool_id="pestel",
        next_step="Indicar un aspecto del entorno.",
        source_sections=sections,
    )
    with pytest.raises(StructuralViolation):
        validate_candidate(candidate, _handoff(), catalog)
