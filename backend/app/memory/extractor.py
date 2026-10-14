"""事实抽取：一轮对话 → LLM → 结构化记忆条目（fact/preference/relation）"""

import json
import logging

from ..config import ROOT_DIR

logger = logging.getLogger(__name__)

_PROMPT_PATH = ROOT_DIR / "prompts" / "memory_extract.txt"


def _load_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _parse_array(raw: str) -> list[dict]:
    """从模型输出中稳健地解析 JSON 数组（容忍 ```json 代码块与前后废话）"""
    text = (raw or "").strip()
    if "```" in text:
        text = text.replace("```json", "```").replace("```", "")
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    return [d for d in data if isinstance(d, dict) and str(d.get("content", "")).strip()]


async def extract_memories(
    provider,
    model_cfg: dict,
    character_name: str,
    user_msg: str,
    assistant_msg: str,
) -> list[dict]:
    """调用 LLM 抽取值得长期记住的条目；失败时返回空列表，不阻塞主流程"""
    system = _load_prompt()
    if not system:
        return []
    user = f"角色名：{character_name}\n用户：{user_msg}\n角色：{assistant_msg}"

    parts: list[str] = []
    try:
        async for token in provider.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=model_cfg["model"],
            temperature=0.2,
            max_tokens=600,
        ):
            parts.append(token)
    except Exception as e:  # noqa: BLE001 后台任务不因单次失败中断
        logger.warning("记忆抽取调用失败：%s", e)
        return []

    items: list[dict] = []
    for raw in _parse_array("".join(parts)):
        try:
            importance = float(raw.get("importance", 5))
        except (TypeError, ValueError):
            importance = 5.0
        items.append(
            {
                "kind": str(raw.get("kind") or "fact"),
                "content": str(raw["content"]).strip(),
                "importance": max(1.0, min(importance, 10.0)),
            }
        )
    return items
