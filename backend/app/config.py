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
    # True：启动 create_all 自动建表（SQLite 开发默认）；生产/切 Alembic 时设 false 并 alembic upgrade head
    db_auto_create: bool = True
    cors_origins: str = "http://localhost:5173"
    embedding_model: str = ""  # 全局嵌入模型兜底；为空则按 Provider 类型取默认
    # 分层记忆（P1；角色 ext.memory 可逐字段覆盖）
    context_budget_tokens: int = 3000  # L0 工作记忆 token 预算（system 各区块 + 历史）
    memory_query_recent: int = 4  # 检索 query 拼接最近 N 条消息
    memory_window: int = 20  # L1 最近 N 轮注入窗口
    memory_top_k: int = 6  # L3 长期记忆检索条数
    memory_half_life_days: float = 30.0  # 时间衰减半衰期
    memory_decay_min: float = 0.5  # 有效重要度低于此值则归档（decay_at）
    memory_dedupe_threshold: float = 0.6  # 记忆去重相似度阈值（关键词 Jaccard）
    memory_sanitize_enabled: bool = True  # 注入前中和不可信文本（伪区块标题/控制字符/代码围栏）
    memory_item_max_chars: int = 600  # 单条记忆注入 system 的最大字符数
    summarize_every: int = 10  # 每积累 N 条「未摘要」新消息触发一次滚动摘要
    # 向量层（P2，Chroma 服务模式；不可用时自动降级为纯 SQL 检索）
    chroma_enabled: bool = True
    chroma_url: str = "http://localhost:8001"  # docker 内为 http://chroma:8000
    chroma_auth_token: str = ""
    vector_weight: float = 0.4  # 混合检索中向量权重（0=纯关键词，1=纯向量）
    vector_top_k: int = 12  # 向量召回候选数
    # 记忆写入任务（outbox + worker）
    memory_jobs_enabled: bool = True
    memory_worker_interval: float = 2.0  # worker 空转轮询间隔（秒）
    memory_job_max_attempts: int = 3  # 失败重试上限，超过置 failed


settings = Settings()