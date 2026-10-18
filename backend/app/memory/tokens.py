"""token 估算与截断（记忆 / 知识库共用，避免模块间循环依赖）"""


def estimate_tokens(text: str) -> int:
    """粗略 token 估算：CJK 约 1 字 1 token，其余约 4 字符 1 token"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cjk + (len(text) - cjk + 3) // 4


def truncate_to_tokens(text: str, limit: int) -> str:
    """把文本截断到约 limit token（二分，尽量保留前部）"""
    if estimate_tokens(text) <= limit:
        return text
    if limit <= 0:
        return ""
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if estimate_tokens(text[:mid]) <= limit:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo]
