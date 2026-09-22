from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TaskRequest(BaseModel):
    """Una entrada del calendario: tarea, recordatorio o reunion."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200, pattern=r"\S")
    kind: Literal["tarea", "recordatorio", "reunion"] = "tarea"
    due_at: datetime
    # Hora de fin opcional: si existe, la entrada ocupa un bloque de tiempo.
    ends_at: datetime | None = None
    priority: Literal["high", "medium", "low"] = "medium"
    notebook_id: str | None = Field(default=None, min_length=1, max_length=120)
    project_id: str | None = Field(default=None, min_length=32, max_length=32)
    completed: bool = False
    # Marca de la version que se edito. Si el registro cambio desde entonces, el
    # guardado se rechaza para no pisar en silencio el trabajo de otra persona.
    base_updated_at: str | None = Field(default=None, max_length=64)

    @field_validator("due_at", "ends_at")
    @classmethod
    def timezone_required(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("La fecha debe incluir una zona horaria.")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def ends_after_start(self) -> "TaskRequest":
        if self.ends_at is not None and self.ends_at <= self.due_at:
            raise ValueError("La hora de fin debe ser posterior a la de inicio.")
        return self
