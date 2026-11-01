from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

from astrbot.api.message_components import Reply
from core.events import PokeNotice
from core.rules import Cooldown

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import astrbot_plugin_better_qq_chat.main as plugin_main


class FakeBot:
    def __init__(self):
        self.calls = []

    async def call_action(self, action, **params):
        self.calls.append((action, params))
        return {"ok": True}


class FakeMessageObj:
    def __init__(self):
        self.message_id = "100"
        self.raw_message = {}


class FakeEvent:
    def __init__(self, *, group="30001", sender="20001", self_id="999", messages=None):
        self.bot = FakeBot()
        self.message_obj = FakeMessageObj()
        self._group = group
        self._sender = sender
        self._self = self_id
        self._messages = messages or []
        self.is_at_or_wake_command = False
        self.sent = []

    def get_platform_name(self):
        return "aiocqhttp"

    def get_messages(self):
        return self._messages

    def get_group_id(self):
        return self._group

    def get_sender_id(self):
        return self._sender

    def get_self_id(self):
        return self._self

    def is_admin(self):
        return False

    async def send(self, chain):
        self.sent.append(chain)

    def image_result(self, url):
        return url


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.plugin = object.__new__(plugin_main.BetterQQChatPlugin)
        self.plugin.config = {
            "enable": True,
            "poke_tool_enabled": True,
            "poke_allow_private": True,
            "poke_max_times": 2,
            "follow_poke_enabled": True,
            "follow_poke_probability": 1.0,
            "reaction_tool_enabled": True,
            "recall_tool_enabled": True,
            "recall_allow_others": True,
            "avatar_tool_enabled": True,
            "audit_enabled": False,
        }
        self.plugin.data_dir = Path(self.tmp.name)
        self.plugin.follow_cd = Cooldown(0)
        self.plugin.react_cd = Cooldown(0)
        self.plugin._reacted = {}
        self.plugin._last_poked = {}

    def tearDown(self):
        self.tmp.cleanup()

    def test_poke_tool(self):
        event = FakeEvent()
        result = asyncio.run(self.plugin.qq_poke(event, user="12345", times=1))
        self.assertIn("已戳", result)
        self.assertEqual(event.bot.calls[0][0], "group_poke")
        self.assertEqual(event.bot.calls[0][1]["user_id"], 12345)

    def test_react_tool(self):
        event = FakeEvent()
        result = asyncio.run(self.plugin.qq_react(event, emoji="heart", message="current"))
        self.assertIn("已贴上表情", result)
        self.assertEqual(event.bot.calls[0][0], "set_msg_emoji_like")
        self.assertEqual(event.bot.calls[0][1]["emoji_id"], "66")

    def test_recall_own_quoted(self):
        event = FakeEvent(messages=[Reply(id="555", sender_id=999)])
        result = asyncio.run(self.plugin.qq_recall(event))
        self.assertIn("已撤回", result)
        self.assertEqual(event.bot.calls[0][0], "delete_msg")
        self.assertEqual(event.bot.calls[0][1]["message_id"], 555)

    def test_recall_other_needs_manager(self):
        event = FakeEvent(messages=[Reply(id="555", sender_id=123)])
        result = asyncio.run(self.plugin.qq_recall(event))
        self.assertIn("权限", result)
        self.assertNotIn("delete_msg", [call[0] for call in event.bot.calls])

    def test_avatar_url(self):
        event = FakeEvent()
        result = asyncio.run(self.plugin.qq_avatar(event, user="12345"))
        self.assertIn("q1.qlogo.cn", result)
        self.assertFalse(event.sent)

    def test_follow_poke(self):
        event = FakeEvent()
        notice = PokeNotice(
            user_id="20001", target_id="20002", group_id="30001", self_id="999"
        )
        asyncio.run(self.plugin._handle_poke_notice(event, notice))
        self.assertEqual(event.bot.calls[0][0], "group_poke")
        self.assertEqual(event.bot.calls[0][1]["user_id"], 20002)

    def test_bot_poked_only_records(self):
        event = FakeEvent()
        notice = PokeNotice(
            user_id="20001", target_id="999", group_id="30001", self_id="999"
        )
        asyncio.run(self.plugin._handle_poke_notice(event, notice))
        self.assertFalse(event.bot.calls)
        self.assertTrue(self.plugin._last_poked)

    def test_wake_hint(self):
        class Req:
            system_prompt = ""

        event = FakeEvent()
        event.is_at_or_wake_command = True
        req = Req()
        asyncio.run(self.plugin.inject_poke_hint(event, req))
        self.assertIn("qq_poke", req.system_prompt)


if __name__ == "__main__":
    unittest.main()
