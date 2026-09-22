from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=100, pattern=r"\S")
    text: str = Field(min_length=1, max_length=3000, pattern=r"\S")
    color: Literal["yellow", "pink", "blue", "green", "purple", "orange"] = "yellow"
    category: Literal["idea", "prototipo", "observacion", "pregunta", "decision", "otro"] = "idea"
    source_text: str = Field(default="", max_length=3000)
    # Marca de la version que se edito. Si el registro cambio desde entonces, el
    # guardado se rechaza para no pisar en silencio el trabajo de otra persona.
    base_updated_at: str | None = Field(default=None, max_length=64)
