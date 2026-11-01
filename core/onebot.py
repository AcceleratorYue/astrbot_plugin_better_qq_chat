"""OneBot v11 通用调用、目标解析与权限工具。"""

from __future__ import annotations

import re
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import At, Reply

QQ_RE = re.compile(r"^\d{4,12}$")


class OneBotError(RuntimeError):
    """可预期的 OneBot 调用失败。"""


def is_aiocqhttp(event: AstrMessageEvent) -> bool:
    try:
        return event.get_platform_name() == "aiocqhttp"
    except Exception:
        return False


async def call_action(event: AstrMessageEvent, action: str, **params: Any) -> Any:
    """调用当前事件所属协议端的 OneBot 动作。"""
    if not is_aiocqhttp(event):
        raise OneBotError("当前平台不是 aiocqhttp，此能力不可用。")
    bot = getattr(event, "bot", None)
    if bot is None:
        raise OneBotError("当前事件没有 bot 实例。")
    call = getattr(bot, "call_action", None)
    if not callable(call):
        api = getattr(bot, "api", None)
        call = getattr(api, "call_action", None)
    if not callable(call):
        raise OneBotError("当前协议端不支持 call_action。")
    self_id = event.get_self_id()
    if self_id:
        params.setdefault("self_id", self_id)
    try:
        return await call(action, **params)
    except Exception as exc:  # noqa: BLE001
        logger.debug("OneBot 动作失败 %s: %s", action, exc)
        raise OneBotError(f"{action} 调用失败：{exc}") from exc


def find_reply(event: AstrMessageEvent) -> Reply | None:
    try:
        messages = event.get_messages()
    except Exception:
        return None
    return next((c for c in messages if isinstance(c, Reply)), None)


def resolve_message(event: AstrMessageEvent, which: str) -> tuple[int | str, str]:
    """解析 current / quoted 消息，返回 (message_id, sender_id)。"""
    which = str(which or "").strip().lower()
    if which not in ("current", "quoted"):
        raise OneBotError("message 只能是 current 或 quoted。")
    if which == "current":
        message_id = getattr(event.message_obj, "message_id", None)
        sender_id = event.get_sender_id()
    else:
        reply = find_reply(event)
        if reply is None:
            raise OneBotError("用户没有引用任何消息，请先引用目标消息。")
        message_id = reply.id
        sender_id = reply.sender_id
    message_id = str(message_id or "")
    sender_id = str(sender_id or "")
    if not message_id or sender_id == "0":
        raise OneBotError("无法解析消息 ID 或发送者。")
    return (int(message_id) if message_id.isdecimal() else message_id, sender_id)


def resolve_user(event: AstrMessageEvent, user: Any) -> str:
    """把 sender / quoted_sender / at / at:N / QQ 号解析为 QQ 号。"""
    value = str(user or "").strip()
    if not value or value == "sender":
        return str(event.get_sender_id() or "")
    if value == "quoted_sender":
        reply = find_reply(event)
        if reply is None:
            raise OneBotError("用户没有引用消息。")
        sender_id = str(reply.sender_id or "")
        if not sender_id or sender_id == "0":
            raise OneBotError("无法确定被引用消息的作者。")
        return sender_id
    if value == "at" or value.startswith("at:"):
        suffix = value[3:] if value.startswith("at:") else "1"
        if suffix and not suffix.isdecimal():
            raise OneBotError("at 参数格式应为 at 或 at:N。")
        index = int(suffix or "1") - 1
        try:
            mentions = [c for c in event.get_messages() if isinstance(c, At)]
        except Exception:
            mentions = []
        if index < 0 or index >= len(mentions):
            raise OneBotError("没有找到对应的被 @ 用户。")
        qq = str(getattr(mentions[index], "qq", "") or "")
        if not QQ_RE.match(qq):
            raise OneBotError("@ 的目标不是有效 QQ 号。")
        return qq
    if QQ_RE.match(value):
        return value
    raise OneBotError("无法识别目标，请用 sender、quoted_sender、at、at:N 或 QQ 号。")


async def is_group_manager(event: AstrMessageEvent, user_id: str | None = None) -> bool:
    """AstrBot 管理员或当前群群主/管理员。"""
    try:
        if event.is_admin():
            return True
    except Exception:
        pass
    group_id = str(event.get_group_id() or "")
    target = str(user_id or event.get_sender_id() or "")
    if not group_id or not target:
        return False
    try:
        info = await call_action(
            event,
            "get_group_member_info",
            group_id=int(group_id),
            user_id=int(target),
            no_cache=True,
        )
        role = str((info or {}).get("role") or "").lower()
        return role in ("owner", "admin")
    except Exception:
        return False
