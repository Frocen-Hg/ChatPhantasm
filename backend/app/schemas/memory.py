from pydantic import BaseModel, Field


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1)
    kind: str = "fact"  # fact | preference | relation | episode ...
    layer: str = "L3"  # L2 | L3 | L4
    importance: float = 5.0
    visibility: str = "public"  # public | private


class MemoryUpdate(BaseModel):
    content: str | None = None
    kind: str | None = None
    layer: str | None = None
    importance: float | None = None
    visibility: str | None = None
