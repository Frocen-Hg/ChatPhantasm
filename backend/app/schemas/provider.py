from pydantic import BaseModel


class ProviderCreate(BaseModel):
    name: str
    type: str  # openai_compat | ollama
    base_url: str = ""
    api_key: str | None = None
    models: list[str] = []
    is_default: bool = False


class ProviderUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    models: list[str] | None = None
    is_default: bool | None = None


class ProviderTest(BaseModel):
    id: int | None = None
    name: str | None = None
    type: str = "openai_compat"
    base_url: str = ""
    api_key: str | None = None
    models: list[str] = []