"""QQ 头像 URL。"""

from __future__ import annotations

from .onebot import QQ_RE


def avatar_url(user_id: str, size: int = 640) -> str | None:
    """用户 QQ 头像；只接受纯数字 QQ 号。"""
    qq = str(user_id or "").strip()
    if not QQ_RE.match(qq):
        return None
    size = max(40, min(int(size), 640))
    return f"https://q1.qlogo.cn/g?b=qq&nk={qq}&s={size}"
