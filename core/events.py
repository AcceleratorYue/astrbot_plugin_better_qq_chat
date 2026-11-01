"""解析 OneBot notice 事件（戳一戳 / 表情回应）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from astrbot.api.event import AstrMessageEvent


@dataclass(frozen=True)
class PokeNotice:
    user_id: str
    target_id: str
    group_id: str
    self_id: str

    @property
    def is_bot_target(self) -> bool:
        return bool(self.self_id and self.target_id == self.self_id)

    @property
    def is_outgoing(self) -> bool:
        return bool(self.self_id and self.user_id == self.self_id)

    @property
    def is_other_poke(self) -> bool:
        return bool(
            self.user_id
            and self.target_id
            and self.user_id != self.target_id
            and not self.is_bot_target
            and not self.is_outgoing
        )


@dataclass(frozen=True)
class ReactionNotice:
    group_id: str
    user_id: str
    message_id: str
    emoji_ids: tuple[str, ...]
    self_id: str

    @property
    def is_outgoing(self) -> bool:
        return bool(self.self_id and self.user_id == self.self_id)


def raw_notice(event: AstrMessageEvent) -> dict[str, Any] | None:
    raw = getattr(getattr(event, "message_obj", None), "raw_message", None)
    if not isinstance(raw, dict) or raw.get("post_type") != "notice":
        return None
    return raw


def parse_poke_notice(event: AstrMessageEvent) -> PokeNotice | None:
    raw = raw_notice(event)
    if raw is None:
        return None
    notice_type = str(raw.get("notice_type") or "")
    sub_type = str(raw.get("sub_type") or "")
    if sub_type != "poke" and notice_type != "poke":
        return None
    return PokeNotice(
        user_id=str(raw.get("user_id") or ""),
        target_id=str(raw.get("target_id") or ""),
        group_id=str(raw.get("group_id") or ""),
        self_id=str(raw.get("self_id") or getattr(event, "get_self_id", lambda: "")()),
    )


def parse_reaction_notice(event: AstrMessageEvent) -> ReactionNotice | None:
    raw = raw_notice(event)
    if raw is None or str(raw.get("notice_type") or "") != "group_msg_emoji_like":
        return None
    message_id = str(raw.get("message_id") or "")
    if not message_id:
        return None
    emoji_ids: list[str] = []
    likes = raw.get("likes")
    if isinstance(likes, list):
        for like in likes:
            if not isinstance(like, dict):
                continue
            try:
                count = int(like.get("count", 0))
            except (TypeError, ValueError):
                count = 0
            if count <= 0:
                continue
            emoji_id = str(like.get("emoji_id") or "").strip()
            if emoji_id and emoji_id not in emoji_ids:
                emoji_ids.append(emoji_id)
    if not emoji_ids:
        return None
    return ReactionNotice(
        group_id=str(raw.get("group_id") or ""),
        user_id=str(raw.get("user_id") or ""),
        message_id=message_id,
        emoji_ids=tuple(emoji_ids),
        self_id=str(raw.get("self_id") or getattr(event, "get_self_id", lambda: "")()),
    )
