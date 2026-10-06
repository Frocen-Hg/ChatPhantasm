from pydantic import BaseModel


class ProviderCreate(BaseModel):
    name: str
    type: str  # openai_compat | ollama
    base_url: str = ""
    api_key: str | None = None
    models: list[str] = []
    is_default: bool = False
    embedding_model: str | None = None  # 嵌入模型，独立于聊天模型
    is_embedding_default: bool = False


class ProviderUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    models: list[str] | None = None
    is_default: bool | None = None
    embedding_model: str | None = None
    is_embedding_default: bool | None = None


class ProviderTest(BaseModel):
    id: int | None = None
    name: str | None = None
    type: str = "openai_compat"
    base_url: str = ""
    api_key: str | None = None
    models: list[str] = []
    embedding_model: str | None = None
    capability: str = "chat"  # chat | embedding


class RouteUpsert(BaseModel):
    provider_id: int
    model: str | None = None
    params: dict = {}
    enabled: bool = True