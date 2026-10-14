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


class StateUpdate(BaseModel):
    mood: str | None = None
    arousal: float | None = None
    current_focus: str | None = None
    relationship: dict | None = None


class MemorySearchRequest(BaseModel):
    character_id: int
    query: str = ""
    top_k: int = 6
    half_life_days: float | None = None


class ContextPreviewRequest(BaseModel):
    character_id: int
    conversation_id: int | None = None
    query: str = ""
