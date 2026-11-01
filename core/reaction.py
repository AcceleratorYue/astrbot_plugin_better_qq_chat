"""QQ 表情回应：白名单与事件辅助。

表情 ID 表参考 MIT 许可的 astrbot_plugin_napcat_tools（Dracowyn）。
这些 ID 仍需在目标协议端真机验证。
"""

from __future__ import annotations

from typing import Any

EMOJIS: dict[str, int] = {
    "thumbs_up": 76,
    "heart": 66,
    "ok": 124,
    "laugh_cry": 182,
    "facepalm": 264,
    "celebrate": 320,
    "applause": 99,
    "rose": 63,
    "hug": 49,
    "smile": 14,
    "cute": 21,
    "proud": 4,
    "tears": 5,
    "cry": 9,
    "awkward": 10,
    "sweat": 27,
    "cool": 16,
    "smirk": 101,
    "victory": 79,
    "angry": 326,
}

EMOJI_NAMES = ", ".join(EMOJIS)


def emoji_id(value: Any) -> str | None:
    """把语义名或数字 ID 转成协议端需要的字符串 ID。"""
    text = str(value or "").strip()
    if not text:
        return None
    if text in EMOJIS:
        return str(EMOJIS[text])
    if text.isdecimal():
        return text
    return None


def likes_to_emoji_ids(notice: dict[str, Any]) -> list[str]:
    likes = notice.get("likes")
    if not isinstance(likes, list):
        return []
    result: list[str] = []
    for like in likes:
        if not isinstance(like, dict):
            continue
        try:
            count = int(like.get("count", 0))
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            continue
        emoji = str(like.get("emoji_id") or "").strip()
        if emoji and emoji not in result:
            result.append(emoji)
    return result
