from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProblemTreeNode(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    text: str = Field(min_length=1, max_length=240, pattern=r"\S")
    source: str = Field(default="", max_length=500)


class ProblemTreeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    version: int = Field(ge=0)
    problem: str = Field(min_length=1, max_length=500, pattern=r"\S")
    problem_source: str = Field(default="", max_length=500)
    causes: list[ProblemTreeNode] = Field(default_factory=list, max_length=30)
    effects: list[ProblemTreeNode] = Field(default_factory=list, max_length=30)
