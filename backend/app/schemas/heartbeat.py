from pydantic import BaseModel, Field


class HeartbeatConfigUpdate(BaseModel):
    enabled: bool | None = None
    interval_min: int | None = Field(None, ge=1, le=10080)  # 1 分钟 - 7 天
    types: list[str] | None = None  # ["monologue"]（P3b 后含 proactive）
    quiet_hours: dict | None = None  # {"start": "23:00", "end": "08:00"}，空串表示不静默
    daily_limit: int | None = Field(None, ge=0, le=1000)  # 0 表示不运行
    jitter_ratio: float | None = Field(None, ge=0.0, le=1.0)
    show_monologue: bool | None = None


class HeartbeatRunRequest(BaseModel):
    type: str = "monologue"  # monologue（P3b 后含 proactive）
