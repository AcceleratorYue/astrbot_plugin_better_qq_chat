from __future__ import annotations

import unittest
from dataclasses import dataclass

from core.events import parse_poke_notice, parse_reaction_notice


@dataclass
class MessageObj:
    raw_message: dict


class FakeEvent:
    def __init__(self, raw, self_id="999"):
        self.message_obj = MessageObj(raw)
        self._self = self_id

    def get_self_id(self):
        return self._self


class NoticeTests(unittest.TestCase):
    def test_standard_poke(self):
        event = FakeEvent(
            {
                "post_type": "notice",
                "notice_type": "notify",
                "sub_type": "poke",
                "user_id": 11,
                "target_id": 22,
                "group_id": 33,
                "self_id": 999,
            }
        )
        poke = parse_poke_notice(event)
        self.assertIsNotNone(poke)
        self.assertTrue(poke.is_other_poke)
        self.assertFalse(poke.is_bot_target)

    def test_alternate_poke(self):
        event = FakeEvent(
            {
                "post_type": "notice",
                "notice_type": "poke",
                "user_id": 11,
                "target_id": 999,
                "self_id": 999,
            }
        )
        poke = parse_poke_notice(event)
        self.assertTrue(poke.is_bot_target)
        self.assertFalse(poke.is_other_poke)

    def test_outgoing_poke(self):
        event = FakeEvent(
            {
                "post_type": "notice",
                "notice_type": "notify",
                "sub_type": "poke",
                "user_id": 999,
                "target_id": 22,
                "self_id": 999,
            }
        )
        poke = parse_poke_notice(event)
        self.assertTrue(poke.is_outgoing)

    def test_non_poke_notice(self):
        event = FakeEvent({"post_type": "notice", "notice_type": "group_upload"})
        self.assertIsNone(parse_poke_notice(event))

    def test_reaction(self):
        event = FakeEvent(
            {
                "post_type": "notice",
                "notice_type": "group_msg_emoji_like",
                "group_id": 33,
                "user_id": 11,
                "message_id": 55,
                "likes": [{"emoji_id": "66", "count": 1}],
                "self_id": 999,
            }
        )
        reaction = parse_reaction_notice(event)
        self.assertIsNotNone(reaction)
        self.assertEqual(reaction.emoji_ids, ("66",))
        self.assertEqual(reaction.message_id, "55")

    def test_reaction_cancel_ignored(self):
        event = FakeEvent(
            {
                "post_type": "notice",
                "notice_type": "group_msg_emoji_like",
                "group_id": 33,
                "user_id": 11,
                "message_id": 55,
                "likes": [{"emoji_id": "66", "count": 0}],
            }
        )
        self.assertIsNone(parse_reaction_notice(event))


if __name__ == "__main__":
    unittest.main()
