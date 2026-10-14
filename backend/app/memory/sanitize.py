"""不可信文本的注入防护。

信任边界：角色卡由作者编写（可信，不过滤）；记忆/摘要/内心状态由模型或用户
间接产生（不可信），注入 system 前需中和伪区块标题、控制字符与代码围栏，并限长。
"""

import re

# 与本项目 system 区块标题同名，防止记忆内容伪造结构
_RESERVED = ("[角色卡]", "[内心状态]", "[长期记忆]", "[会话摘要]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def neutralize(text: str, max_chars: int = 0) -> str:
    """中和不可信文本：控制字符、保留标题、代码围栏，并按 max_chars 截断"""
    if not text:
        return ""
    out = _CONTROL.sub("", text)
    for token in _RESERVED:
        out = out.replace(token, token.replace("[", "［").replace("]", "］"))
    out = out.replace("```", "｀｀｀")
    out = re.sub(r"\n{4,}", "\n\n\n", out)
    if max_chars and len(out) > max_chars:
        out = out[:max_chars].rstrip() + "…"
    return out.strip()
