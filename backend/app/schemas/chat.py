from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    character_id: int
    conversation_id: int | None = None
    content: str = Field(min_length=1)
    provider_id: int | None = None  # 临时覆盖 Provider（不落库）
    model: str | None = None  # 临时覆盖模型（不落库）