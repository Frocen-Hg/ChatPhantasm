"""记忆检索：P1 纯 SQL 关键词 + 重要性 × 时间衰减。

向量语义检索（VectorStore/ChromaDB）留待 P2 接入，此处保持纯函数、无外部依赖，
后续可在 rank_score 中叠加向量相似度而不改动调用方。
"""

import math
import re
from datetime import datetime

# 中英文分词辅助：按空白与标点切分，中文部分再补 2-gram
_SPLIT = re.compile(r"[\s,，。！？!?、;；:：\"'“”‘’（）()\[\]【】…·~～]+")
_CJK = re.compile(r"[\u4e00-\u9fff]+")


def _terms(text: str) -> set[str]:
    """从文本抽取候选关键词（拉丁词 + 中文 2-gram）"""
    text = (text or "").lower()
    terms: set[str] = {p for p in _SPLIT.split(text) if p}
    for block in _CJK.findall(text):
        terms.update(block[i : i + 2] for i in range(len(block) - 1))
    return terms


def keyword_score(query: str, content: str) -> float:
    """命中率：查询关键词在内容中出现的比例，0-1"""
    q = _terms(query)
    if not q:
        return 0.0
    c = (content or "").lower()
    hits = sum(1 for t in q if t in c)
    return hits / len(q)


def recency(created_at: datetime | None, half_life_days: float) -> float:
    """时间衰减：exp(-Δt / 半衰期)，越久越接近 0"""
    if created_at is None:
        return 1.0
    age_days = max((datetime.now() - created_at).total_seconds() / 86400, 0.0)
    return math.exp(-age_days / max(half_life_days, 1e-6))


def rank_score(query: str, memory, half_life_days: float) -> float:
    """综合排序分：关键词 × 重要性 × 新鲜度。查询无命中直接返回 0（过滤）"""
    kw = keyword_score(query, memory.content) if query else 1.0
    if query and kw <= 0:
        return 0.0
    importance = max(0.0, min(float(memory.importance or 0.0), 10.0)) / 10.0
    return (0.2 + 0.8 * kw) * importance * recency(memory.created_at, half_life_days)
