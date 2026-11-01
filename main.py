"""更好的QQ聊天交互：戳一戳、表情回应、撤回与头像。

只支持 aiocqhttp（OneBot v11 / NapCat / Lagrange）。
所有主动互动都由 LLM 工具或可配置的事件规则触发，不修改消息链。
"""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.message_components import Image
from astrbot.api.star import Context, Star, StarTools

from .core.avatar import avatar_url
from .core.events import (
    PokeNotice,
    ReactionNotice,
    parse_poke_notice,
    parse_reaction_notice,
)
from .core.onebot import (
    OneBotError,
    call_action,
    is_aiocqhttp,
    is_group_manager,
    resolve_message,
    resolve_user,
)
from .core.reaction import EMOJI_NAMES, emoji_id
from .core.recall import can_recall_quoted
from .core.rules import (
    Cooldown,
    as_bool,
    as_float,
    as_int,
    follow_target,
    should_follow,
    split_set,
)

PLUGIN_NAME = "astrbot_plugin_better_qq_chat"
DISPLAY_NAME = "更好的QQ聊天交互"
VERSION = "0.1.1"
LOG = f"[{PLUGIN_NAME}]"
WAKE_HINT = (
    "[互动提示] 如果当前语气和氛围合适，可以考虑用 qq_poke 戳一下唤醒你的人；"
    "不要强行使用，也不要连续戳。"
)
ACTIVE_REPLY_HINT = (
    "[互动提示] 这是一次群聊主动回复。如果当前语气和氛围合适，"
    "可以考虑用 qq_poke 戳一下发言人，或用 qq_react 给当前消息贴一个小表情；"
    "不要强行使用，也不要连续互动。"
)
DEDUP_LIMIT = 2000


class BetterQQChatPlugin(Star):
    """QQ 互动工具与事件响应。"""

    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.config = config or {}
        self.data_dir = Path(StarTools.get_data_dir(PLUGIN_NAME))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.follow_cd = Cooldown(as_float(self._cfg("follow_poke_cooldown", 30), 30))
        self.react_cd = Cooldown(
            as_float(self._cfg("reaction_follow_cooldown", 30), 30)
        )
        self._reacted: OrderedDict[tuple[str, str, str], float] = OrderedDict()
        self._last_poked: dict[str, float] = {}
        logger.info(
            "%s v%s 已加载 | 群跟戳概率 %.2f | 表情跟贴 %s",
            LOG,
            VERSION,
            self._follow_probability(),
            "开" if self._bool("reaction_follow_enabled", False) else "关",
        )

    # ------------------------------------------------------------------ #
    # LLM 工具
    # ------------------------------------------------------------------ #

    @filter.llm_tool(name="qq_poke")
    async def qq_poke(
        self,
        event: AstrMessageEvent,
        user: str = "sender",
        times: int = 1,
    ) -> str:
        """戳一戳 QQ 用户。

        只在当前对话氛围合适时调用；不要连续、频繁地戳同一个人。
        群聊默认戳当前发言人，也可以先让用户 @ 或引用目标。

        Args:
            user(string): 目标，支持 sender、quoted_sender、at、at:1、QQ 号。
            times(int): 次数，1 到插件配置的上限。
        """
        if not self._enabled() or not self._bool("poke_tool_enabled", True):
            return "戳一戳工具当前已关闭。"
        if not is_aiocqhttp(event):
            return "当前平台不是 aiocqhttp，无法戳一戳。"
        try:
            qq = resolve_user(event, user)
        except OneBotError as exc:
            return f"戳一戳失败：{exc}"
        if not qq or qq == str(event.get_self_id() or ""):
            return "不能戳机器人自己。"
        group_id = str(event.get_group_id() or "")
        if not group_id and not self._bool("poke_allow_private", True):
            return "当前配置只在群聊中允许戳一戳。"
        count = as_int(times, 1, 1, self._int("poke_max_times", 2, 1, 3))
        last_error = ""
        for _ in range(count):
            try:
                if group_id:
                    await call_action(
                        event,
                        "group_poke",
                        group_id=int(group_id),
                        user_id=int(qq),
                    )
                else:
                    await call_action(event, "friend_poke", user_id=int(qq))
            except OneBotError as first:
                last_error = str(first)
                try:
                    params = {"user_id": int(qq)}
                    if group_id:
                        params["group_id"] = int(group_id)
                    await call_action(event, "send_poke", **params)
                except OneBotError as second:
                    return f"戳一戳失败：{last_error}；send_poke：{second}"
        self._audit("poke", {"target": qq, "times": count, "group": group_id})
        return f"已戳 {qq}{' ' + str(count) + ' 次' if count > 1 else ''}。"

    @filter.llm_tool(name="qq_react")
    async def qq_react(
        self,
        event: AstrMessageEvent,
        emoji: str,
        message: str = "quoted",
    ) -> str:
        """给 QQ 消息贴一个小表情回应。

        适合“看到了、笑死、点赞、抱抱”等不需要文字回复的场景。
        一次只贴一个表情；不要对同一条消息反复贴。

        Args:
            emoji(string): 表情名，例如 heart、thumbs_up、laugh_cry、rose；也可传数字 ID。
            message(string): quoted 表示被引用的消息，current 表示当前消息。
        """
        if not self._enabled() or not self._bool("reaction_tool_enabled", True):
            return "表情回应工具当前已关闭。"
        if not is_aiocqhttp(event):
            return "当前平台不是 aiocqhttp，无法贴表情。"
        target_emoji = emoji_id(emoji)
        if target_emoji is None:
            return f"不认识这个表情。可选：{EMOJI_NAMES}，或数字 ID。"
        try:
            message_id, _ = resolve_message(event, message)
        except OneBotError as exc:
            return f"贴表情失败：{exc}"
        try:
            await call_action(
                event,
                "set_msg_emoji_like",
                message_id=message_id,
                emoji_id=target_emoji,
            )
        except OneBotError as exc:
            return f"贴表情失败：{exc}"
        self._audit("react", {"emoji": target_emoji, "message_id": str(message_id)})
        return "已贴上表情。"

    @filter.llm_tool(name="qq_recall")
    async def qq_recall(
        self,
        event: AstrMessageEvent,
        message: str = "quoted",
    ) -> str:
        """撤回一条被引用的 QQ 消息。

        只支持 quoted：需要用户先引用目标消息。
        撤回机器人自己的消息任何人都可以请求；撤回他人消息需要管理员或群管理员。

        Args:
            message(string): 目前只支持 quoted，必须引用目标消息。
        """
        if not self._enabled() or not self._bool("recall_tool_enabled", True):
            return "撤回工具当前已关闭。"
        if not is_aiocqhttp(event):
            return "当前平台不是 aiocqhttp，无法撤回。"
        if str(message or "").strip().lower() != "quoted":
            return "目前只支持撤回被引用的消息，请让用户先引用目标消息。"
        try:
            message_id, sender_id = resolve_message(event, "quoted")
        except OneBotError as exc:
            return f"撤回失败：{exc}"
        manager = False
        if sender_id != str(event.get_self_id() or ""):
            manager = await is_group_manager(event)
        allowed, reason = can_recall_quoted(
            quoted_sender_id=sender_id,
            self_id=str(event.get_self_id() or ""),
            allow_others=self._bool("recall_allow_others", True),
            requester_is_manager=manager,
        )
        if not allowed:
            return f"撤回失败：{reason}"
        try:
            await call_action(event, "delete_msg", message_id=message_id)
        except OneBotError as exc:
            return f"撤回失败：{exc}"
        self._audit("recall", {"message_id": str(message_id), "sender": sender_id})
        return "已撤回被引用的消息。"

    @filter.llm_tool(name="qq_avatar")
    async def qq_avatar(
        self,
        event: AstrMessageEvent,
        user: str = "sender",
        send_to_chat: bool = False,
    ) -> str:
        """获取 QQ 用户头像。

        默认返回高清头像 URL；send_to_chat=true 时直接把头像图片发到当前会话。

        Args:
            user(string): 目标，支持 sender、quoted_sender、at、at:1、QQ 号。
            send_to_chat(bool): 是否把头像图片直接发到聊天。
        """
        if not self._enabled() or not self._bool("avatar_tool_enabled", True):
            return "头像工具当前已关闭。"
        try:
            qq = resolve_user(event, user)
        except OneBotError as exc:
            return f"获取头像失败：{exc}"
        url = avatar_url(qq)
        if not url:
            return "获取头像失败：目标不是有效 QQ 号。"
        if send_to_chat:
            try:
                await event.send(MessageChain([Image.fromURL(url)]))
            except Exception as exc:  # noqa: BLE001
                logger.warning("%s 发送头像失败: %s", LOG, exc)
                return f"头像链接：{url}（发送图片失败：{exc}）"
        self._audit("avatar", {"target": qq, "sent": bool(send_to_chat)})
        return f"头像链接：{url}" + ("，已发送到聊天。" if send_to_chat else "")

    # ------------------------------------------------------------------ #
    # 唤醒提示
    # ------------------------------------------------------------------ #

    @filter.on_llm_request(priority=-50)
    async def inject_poke_hint(self, event: AstrMessageEvent, req) -> None:
        if not self._enabled() or not is_aiocqhttp(event):
            return
        wake = False
        try:
            wake = bool(event.is_at_or_wake_command)
        except Exception:
            pass
        active_reply = False
        try:
            active_reply = bool(event.get_extra("active_reply_triggered", False))
        except Exception:
            pass
        wake_allowed = wake and self._bool("poke_wake_hint_enabled", True)
        active_allowed = active_reply and self._bool(
            "active_reply_hint_enabled", True
        )
        if not wake_allowed and not active_allowed:
            return
        prompt = str(getattr(req, "system_prompt", "") or "")
        if "qq_poke" in prompt:
            return
        hint = WAKE_HINT if wake_allowed else ACTIVE_REPLY_HINT
        req.system_prompt = prompt + ("\n\n" if prompt else "") + hint

    # ------------------------------------------------------------------ #
    # 戳一戳 / 表情回应 notice
    # ------------------------------------------------------------------ #

    @filter.event_message_type(filter.EventMessageType.ALL)
    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    async def on_notice(self, event: AstrMessageEvent) -> None:
        if not self._enabled() or not is_aiocqhttp(event):
            return
        poke = parse_poke_notice(event)
        if poke is not None:
            await self._handle_poke_notice(event, poke)
            return
        reaction = parse_reaction_notice(event)
        if reaction is not None:
            await self._handle_reaction_notice(event, reaction)

    async def _handle_poke_notice(
        self, event: AstrMessageEvent, poke: PokeNotice
    ) -> None:
        if poke.is_outgoing:
            return
        if poke.is_bot_target:
            # 按产品决策：默认只记录，不主动发起 LLM。
            self._last_poked[poke.group_id or "_private"] = time.time()
            logger.info(
                "%s 被戳 | user=%s | group=%s",
                LOG,
                poke.user_id,
                poke.group_id or "私聊",
            )
            self._audit("poked", {"user": poke.user_id, "group": poke.group_id})
            return
        if not poke.is_other_poke or not poke.group_id:
            return
        if not self._bool("follow_poke_enabled", True):
            return
        if not self._group_allowed(poke.group_id) or self._user_blocked(poke.user_id):
            return
        probability = self._follow_probability()
        if not should_follow(probability, self.follow_cd, poke.group_id):
            return
        target = follow_target(
            poke.user_id,
            poke.target_id,
            self._str("follow_poke_target", "original"),
        )
        if not target or target == str(event.get_self_id() or ""):
            return
        try:
            await call_action(
                event,
                "group_poke",
                group_id=int(poke.group_id),
                user_id=int(target),
            )
        except OneBotError:
            try:
                await call_action(
                    event,
                    "send_poke",
                    group_id=int(poke.group_id),
                    user_id=int(target),
                )
            except OneBotError as exc:
                logger.debug("%s 跟戳失败: %s", LOG, exc)
                return
        self.follow_cd.mark(poke.group_id)
        self._audit(
            "follow_poke",
            {"group": poke.group_id, "sender": poke.user_id, "target": target},
        )
        logger.debug(
            "%s 跟戳 group=%s target=%s", LOG, poke.group_id, target
        )

    async def _handle_reaction_notice(
        self, event: AstrMessageEvent, reaction: ReactionNotice
    ) -> None:
        if reaction.is_outgoing or not self._bool("reaction_follow_enabled", False):
            return
        if not reaction.group_id or not self._group_allowed(reaction.group_id):
            return
        key = (reaction.group_id, reaction.message_id)
        if not self.react_cd.ready(reaction.group_id):
            return
        probability = as_float(self._cfg("reaction_follow_probability", 0.1), 0.1)
        if not should_follow(probability, self.react_cd, reaction.group_id):
            return
        emoji = reaction.emoji_ids[0]
        applied = False
        for emoji in reaction.emoji_ids[: self._int("reaction_max_faces", 1, 1, 3)]:
            dedupe = (reaction.group_id, reaction.message_id, emoji)
            if dedupe in self._reacted:
                continue
            try:
                await call_action(
                    event,
                    "set_msg_emoji_like",
                    message_id=int(reaction.message_id)
                    if reaction.message_id.isdecimal()
                    else reaction.message_id,
                    emoji_id=emoji,
                )
            except OneBotError as exc:
                logger.debug("%s 跟贴表情失败: %s", LOG, exc)
                continue
            self._reacted[dedupe] = time.time()
            applied = True
        if applied:
            self.react_cd.mark(reaction.group_id)
            self._audit(
                "follow_reaction",
                {"group": reaction.group_id, "message_id": reaction.message_id},
            )
            self._prune_reacted()

    # ------------------------------------------------------------------ #
    # 帮助与配置
    # ------------------------------------------------------------------ #

    @filter.command("qq交互", alias=["betterqq", "qqchat"])
    async def help_command(self, event: AstrMessageEvent):
        event.should_call_llm(False)
        yield event.plain_result(
            "更好的QQ聊天交互\n"
            "工具：qq_poke / qq_react / qq_recall / qq_avatar\n"
            "撤回：先引用目标消息，再让 Bot 撤回。\n"
            "仅支持 aiocqhttp（NapCat / Lagrange）。"
        )

    def _enabled(self) -> bool:
        return self._bool("enable", True)

    def _cfg(self, key: str, default: Any = None) -> Any:
        try:
            value = self.config.get(key, default)
        except Exception:
            return default
        return default if value is None else value

    def _bool(self, key: str, default: bool) -> bool:
        return as_bool(self._cfg(key, default), default)

    def _int(self, key: str, default: int, minimum: int, maximum: int) -> int:
        return as_int(self._cfg(key, default), default, minimum, maximum)

    def _str(self, key: str, default: str) -> str:
        return str(self._cfg(key, default) or default).strip()

    def _follow_probability(self) -> float:
        return as_float(self._cfg("follow_poke_probability", 0.15), 0.15)

    def _group_allowed(self, group_id: str) -> bool:
        if str(group_id) in split_set(self._cfg("blocked_groups", "")):
            return False
        groups = split_set(self._cfg("follow_poke_groups", ""))
        return not groups or str(group_id) in groups

    def _user_blocked(self, user_id: str) -> bool:
        return str(user_id) in split_set(self._cfg("blocked_users", ""))

    def _prune_reacted(self) -> None:
        while len(self._reacted) > DEDUP_LIMIT:
            self._reacted.popitem(last=False)

    def _audit(self, action: str, detail: dict[str, Any]) -> None:
        if not self._bool("audit_enabled", True):
            return
        try:
            record = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "action": action,
                "detail": detail,
            }
            with (self.data_dir / "audit.log").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:  # noqa: BLE001
            logger.debug("%s 审计日志写入失败: %s", LOG, exc)
