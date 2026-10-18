"""主动消息生成（P3b）：proactive 上下文 → LLM → 对用户开口的一句话 + 状态更新素材。

与内心独白共用输出解析（text_key="message"）；失败返回空字典，由调用方记录。
"""

import logging

from ..config import ROOT_DIR, settings
from .monologue import parse_output

logger = logging.getLogger(__name__)

_PROMPT_PATH = ROOT_DIR / "prompts" / "heartbeat_proactive.txt"

TEMPERATURE = 0.9  # 主动开口需要一点发散


def _load_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


async def generate(provider, model_cfg: dict, system: str, time_note: str) -> dict:
    """生成一次主动消息；返回解析后的字典（message 为空表示失败）"""
    instruction = _load_prompt()
    if not instruction:
        logger.warning("缺少主动消息提示词：%s", _PROMPT_PATH)
        return {}
    messages = [
        {"role": "system", "content": f"{system}\n\n{instruction}"},
        {"role": "user", "content": time_note},
    ]
    parts: list[str] = []
    try:
        async for token in provider.chat(
            messages,
            model=model_cfg["model"],
            temperature=TEMPERATURE,
            max_tokens=settings.heartbeat_max_tokens,
        ):
            parts.append(token)
    except Exception as e:  # noqa: BLE001 异常上抛给 heartbeat_service 记入运行记录
        logger.warning("主动消息调用失败：%s", e)
        raise
    parsed = parse_output("".join(parts), text_key="message")
    return parsed if parsed.get("message") else {}
