from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    title: str = "未命名文档"
    text: str = Field(min_length=1)
    scope: str = "world"  # world | self | relation | rule
    visibility: str = "public"  # public | private
    chunk_size: int | None = None
    chunk_overlap: int | None = None
