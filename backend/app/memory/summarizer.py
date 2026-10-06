"""情节摘要：多轮消息 → 一段可注入上下文的摘要（L2）"""

import logging

from ..config import ROOT_DIR

logger = logging.getLogger(__name__)

_PROMPT_PATH = ROOT_DIR / "prompts" / "memory_summary.txt"


def _load_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


async def summarize(provider, model_cfg: dict, character_name: str, messages: list) -> str:
    """把给定消息压缩成摘要；失败返回空串"""
    system = _load_prompt()
    if not system:
        return ""
    lines = [f"{m.role}：{m.content}" for m in messages]
    user = f"角色名：{character_name}\n对话记录：\n" + "\n".join(lines)

    parts: list[str] = []
    try:
        async for token in provider.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=model_cfg["model"],
            temperature=0.3,
            max_tokens=500,
        ):
            parts.append(token)
    except Exception as e:  # noqa: BLE001
        logger.warning("摘要生成失败：%s", e)
        return ""
    return "".join(parts).strip()
