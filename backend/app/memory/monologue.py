"""内心独白生成（P3a）：introspect 上下文 → LLM → 独白文本 + 状态更新素材。

输出约定为 JSON（monologue/mood/current_focus/arousal）；解析失败时回退为
「整段文本即独白」，不更新状态字段。失败返回空字典，由调用方决定如何记录。
"""

import json
import logging

from ..config import ROOT_DIR, settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = ROOT_DIR / "prompts" / "heartbeat_monologue.txt"

TEMPERATURE = 0.9  # 独白需要一点发散


def _load_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _clamp_arousal(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(number, 1.0))


def parse_output(raw: str, text_key: str = "monologue") -> dict:
    """从模型输出中稳健解析（容忍 ```json 围栏与前后废话）。

    无 JSON 对象时按纯文本回退；JSON 已解析但缺字段则视为失败（返回 {}），
    避免把 JSON 原文当作独白/消息。text_key 供 P3b 主动消息（message）复用。
    """
    text = (raw or "").strip()
    if not text:
        return {}
    body = text
    if "```" in body:
        body = body.replace("```json", "```").replace("```", "")
    start, end = body.find("{"), body.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(body[start : end + 1])
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            content = str(data.get(text_key) or data.get("content") or "").strip()
            if not content:
                return {}
            return {
                text_key: content,
                "mood": str(data.get("mood") or "").strip()[:64],
                "current_focus": str(
                    data.get("current_focus") or data.get("focus") or ""
                ).strip()[:255],
                "arousal": _clamp_arousal(data.get("arousal")),
            }
    return {text_key: text, "mood": "", "current_focus": "", "arousal": None}


async def generate(provider, model_cfg: dict, system: str, time_note: str) -> dict:
    """生成一次独白；返回解析后的字典（monologue 为空表示失败）"""
    instruction = _load_prompt()
    if not instruction:
        logger.warning("缺少独白提示词：%s", _PROMPT_PATH)
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
        logger.warning("内心独白调用失败：%s", e)
        raise
    parsed = parse_output("".join(parts))
    return parsed if parsed.get("monologue") else {}
