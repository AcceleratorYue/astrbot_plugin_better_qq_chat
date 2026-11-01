from __future__ import annotations

import unittest
from dataclasses import dataclass

from astrbot.api.message_components import At, Reply

from core.onebot import OneBotError, resolve_message, resolve_user


@dataclass
class MessageObj:
    raw_message: dict
    message_id: str = "100"


class FakeEvent:
    def __init__(self, messages=None, sender="20001", group="30001", self_id="999"):
        self._messages = messages or []
        self._sender = sender
        self._group = group
        self._self = self_id
        self.message_obj = MessageObj(raw_message={}, message_id="100")

    def get_platform_name(self):
        return "aiocqhttp"

    def get_messages(self):
        return self._messages

    def get_sender_id(self):
        return self._sender

    def get_group_id(self):
        return self._group

    def get_self_id(self):
        return self._self

    def is_admin(self):
        return False


class OneBotTargetTests(unittest.TestCase):
    def test_sender_and_qq(self):
        event = FakeEvent(sender="12345")
        self.assertEqual(resolve_user(event, "sender"), "12345")
        self.assertEqual(resolve_user(event, "67890"), "67890")

    def test_at(self):
        event = FakeEvent(messages=[At(qq=11111), At(qq=22222)])
        self.assertEqual(resolve_user(event, "at"), "11111")
        self.assertEqual(resolve_user(event, "at:2"), "22222")
        with self.assertRaises(OneBotError):
            resolve_user(event, "at:3")

    def test_quoted_sender(self):
        event = FakeEvent(messages=[Reply(id="55", sender_id=33333)])
        self.assertEqual(resolve_user(event, "quoted_sender"), "33333")

    def test_invalid_target(self):
        event = FakeEvent()
        with self.assertRaises(OneBotError):
            resolve_user(event, "not-a-number")

    def test_resolve_message(self):
        event = FakeEvent(messages=[Reply(id="55", sender_id=33333)])
        self.assertEqual(resolve_message(event, "quoted"), (55, "33333"))
        self.assertEqual(resolve_message(event, "current"), (100, "20001"))

    def test_quoted_without_reply(self):
        with self.assertRaises(OneBotError):
            resolve_message(FakeEvent(), "quoted")


if __name__ == "__main__":
    unittest.main()
