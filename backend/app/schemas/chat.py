from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    character_id: int
    conversation_id: int | None = None
    content: str = Field(min_length=1)