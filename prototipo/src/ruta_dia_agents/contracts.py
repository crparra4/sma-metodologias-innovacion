from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ExpertiseLevel(StrEnum):
    NOVEL = "novel"
    BASIC = "basic"
    INTERMEDIATE = "intermediate"


class Verdict(StrEnum):
    APPROVED = "approved"
    OBSERVED = "observed"
    REJECTED = "rejected"


class Severity(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class NotebookColor(StrEnum):
    BLUE = "blue"
    YELLOW = "yellow"
    GREEN = "green"
    ORANGE = "orange"
    PURPLE = "purple"
    GRAY = "gray"


class ProjectContext(StrictModel):
    """Declaraciones iniciales del usuario; no son resultados metodológicos verificados."""

    question: str = Field(default="", max_length=1500)
    environment: str = Field(default="", max_length=1500)
    objective: str = Field(default="", max_length=1500)
    hypothesis: str = Field(default="", max_length=1500)
    acceptance_criteria: str = Field(default="", max_length=1500)
    ambition: str = Field(default="", max_length=1500)

    def stated_context(self) -> str:
        # Los supuestos y metas experimentales nunca respaldan hechos o causas confirmadas.
        return "\n".join([self.question, self.environment, self.objective])


class ProjectState(StrictModel):
    notebook_id: str = "demo"
    phase: str = "Descubrimiento"
    stage: int = Field(default=1, ge=1, le=10)
    role: str = ""
    active_tool: str = ""
    completed_tools: list[str] = Field(default_factory=list)
    recent_turns: list[str] = Field(default_factory=list, max_length=8)
    shared_context: list[str] = Field(default_factory=list, max_length=40)
    validated_fields: dict[str, dict[str, Any]] = Field(default_factory=dict)
    context: ProjectContext = Field(default_factory=ProjectContext)
    color: NotebookColor = NotebookColor.BLUE


class ToolRecommendation(StrictModel):
    tool_id: str
    reason: str


class HandoffContract(StrictModel):
    intent: str
    phase: str
    stage: int = Field(ge=1, le=10)
    expertise: ExpertiseLevel
    recommendations: list[ToolRecommendation] = Field(default_factory=list, max_length=3)
    active_tool: str = ""
    context_summary: str

    @model_validator(mode="after")
    def active_tool_must_be_recommended(self) -> HandoffContract:
        ids = {item.tool_id for item in self.recommendations}
        if ids and self.active_tool not in ids:
            raise ValueError("active_tool debe estar dentro de recommendations")
        if not ids and self.active_tool:
            raise ValueError("active_tool debe estar vacío cuando no hay recomendaciones")
        return self


class TemplateUpdate(StrictModel):
    field: str
    value: Any


class CandidateResponse(StrictModel):
    message: str = Field(min_length=1)
    tool_id: str
    next_step: str = Field(min_length=1)
    source_sections: list[str] = Field(default_factory=list)
    template_updates: list[TemplateUpdate] = Field(default_factory=list)


class VerificationFinding(StrictModel):
    code: str
    detail: str


class VerificationResult(StrictModel):
    verdict: Verdict
    severity: Severity
    findings: list[VerificationFinding] = Field(default_factory=list)
    source_tool_id: str

    @model_validator(mode="after")
    def coherent_verdict(self) -> VerificationResult:
        if self.verdict == Verdict.APPROVED:
            if self.findings:
                raise ValueError("Un resultado aprobado no puede incluir hallazgos")
            if self.severity != Severity.NONE:
                raise ValueError("Un resultado aprobado debe tener severidad none")
        elif not self.findings:
            raise ValueError("Un resultado observado o rechazado debe explicar sus hallazgos")
        return self


class VerificationAssessment(StrictModel):
    unsupported_claims: list[str] = Field(default_factory=list, max_length=4)
    method_error: Literal["", "invented_step", "premature_or_conflicting_step"] = ""
    interaction_error: Literal["", "role_reversal", "multiple_or_conflicting_actions"] = ""


class TurnResult(StrictModel):
    message: str
    handoff: HandoffContract
    verification: VerificationResult
    attempts: int = Field(ge=1, le=2)
    degraded: bool = False
    accepted_updates: list[TemplateUpdate] = Field(default_factory=list)
