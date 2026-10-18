from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    title: str = "未命名文档"
    text: str = Field(min_length=1)
    scope: str = "world"  # world | self | relation | rule
    visibility: str = "public"  # public | private
    chunk_size: int | None = None
    chunk_overlap: int | None = None


class LoreCreate(BaseModel):
    content: str = Field(min_length=1)
    keys: list[str] = []
    constant: bool = False
    priority: int = 0
    scan_depth: int | None = None
    scope: str = "world"
    visibility: str = "public"
    enabled: bool = True


class LoreUpdate(BaseModel):
    content: str | None = None
    keys: list[str] | None = None
    constant: bool | None = None
    priority: int | None = None
    scan_depth: int | None = None
    scope: str | None = None
    visibility: str | None = None
    enabled: bool | None = None


class KbSearchRequest(BaseModel):
    character_id: int
    query: str = ""
    conversation_id: int | None = None
    budget_tokens: int | None = None
