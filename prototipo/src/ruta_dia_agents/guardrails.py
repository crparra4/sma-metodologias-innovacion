from __future__ import annotations

import re

from .contracts import CandidateResponse, HandoffContract
from .knowledge import KnowledgeCatalog


class StructuralViolation(ValueError):
    """Una salida rompe un contrato verificable sin usar otro LLM."""


def validate_handoff(contract: HandoffContract, catalog: KnowledgeCatalog) -> None:
    stage = catalog.stage(contract.stage)
    if contract.phase != stage.phase:
        raise StructuralViolation(
            f"La fase {contract.phase!r} no corresponde a la etapa {contract.stage}"
        )
    if not contract.recommendations and stage.tools:
        raise StructuralViolation(
            f"La etapa {contract.stage} tiene herramientas disponibles, pero no se eligió ninguna"
        )
    for recommendation in contract.recommendations:
        if not catalog.tool_allowed_in_stage(recommendation.tool_id, contract.stage):
            raise StructuralViolation(
                f"{recommendation.tool_id!r} no está habilitada en la etapa {contract.stage}"
            )


def validate_candidate(
    candidate: CandidateResponse,
    contract: HandoffContract,
    catalog: KnowledgeCatalog,
) -> None:
    if candidate.tool_id != contract.active_tool:
        raise StructuralViolation(
            "La respuesta del metodólogo no corresponde a la herramienta activa"
        )
    tool = catalog.tool(candidate.tool_id)
    allowed_fields = set(tool.template_fields)
    update_fields = {update.field for update in candidate.template_updates}
    unknown_fields = update_fields - allowed_fields
    if unknown_fields:
        unknown = ", ".join(sorted(unknown_fields))
        raise StructuralViolation(f"Campos de plantilla no declarados: {unknown}")
    headings = {
        match.strip().casefold()
        for match in re.findall(
            r"^#{1,6}\s+(.+)$", catalog.tool_card(candidate.tool_id), re.MULTILINE
        )
    }
    if not candidate.source_sections:
        raise StructuralViolation("La respuesta debe citar al menos un encabezado de la ficha")
    for section in candidate.source_sections:
        normalized = re.sub(r"^#{1,6}\s*", "", section.strip()).casefold()
        if normalized not in headings:
            raise StructuralViolation(f"Encabezado no existente en la ficha: {section!r}")
