from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_root() -> Path:
    """向上查找包含 prompts 的目录作为仓库根（仓库本地与 Docker 内均有效）"""
    p = Path(__file__).resolve()
    for _ in range(6):
        if (p / "prompts").exists():
            return p
        parent = p.parent
        if parent == p:
            break
        p = parent
    return Path(__file__).resolve().parents[2]


ROOT_DIR = _find_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ChatPhantasm"
    deepseek_api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    default_model: str = "deepseek-chat"
    default_temperature: float = 1.3
    default_max_tokens: int = 2000
    ollama_base_url: str = "http://localhost:11434"
    database_url: str = f"sqlite+aiosqlite:///{ROOT_DIR / 'data.db'}"
    cors_origins: str = "http://localhost:5173"


settings = Settings()