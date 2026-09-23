from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_NODES = 30


class ProblemTreeNode(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    text: str = Field(min_length=1, max_length=240, pattern=r"\S")
    source: str = Field(default="", max_length=500)
    parent: str = Field(default="", max_length=64)


class ProblemTreeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    version: int = Field(ge=0)
    problem: str = Field(min_length=1, max_length=500, pattern=r"\S")
    problem_source: str = Field(default="", max_length=500)
    causes: list[ProblemTreeNode] = Field(default_factory=list, max_length=MAX_NODES)
    effects: list[ProblemTreeNode] = Field(default_factory=list, max_length=MAX_NODES)

    @model_validator(mode="after")
    def check_hierarchy(self) -> ProblemTreeUpdate:
        """El árbol admite dos niveles: una tarjeta raíz y sus tarjetas de fondo."""
        seen: set[str] = set()
        for lane in (self.causes, self.effects):
            for node in lane:
                if node.id in seen:
                    raise ValueError(f"Identificador repetido: {node.id}")
                seen.add(node.id)
        for label, lane in (("causas", self.causes), ("efectos", self.effects)):
            ids = {node.id for node in lane}
            nested = {node.id for node in lane if node.parent}
            for node in lane:
                if not node.parent:
                    continue
                if node.parent == node.id:
                    raise ValueError("Una tarjeta no puede depender de sí misma")
                if node.parent not in ids:
                    raise ValueError(
                        f"La tarjeta de la que depende no existe entre las {label}"
                    )
                if node.parent in nested:
                    raise ValueError(
                        "El árbol admite dos niveles: una tarjeta anidada "
                        "no puede tener otras debajo"
                    )
        return self
