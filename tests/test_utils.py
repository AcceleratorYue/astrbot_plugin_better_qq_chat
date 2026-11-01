from __future__ import annotations

import unittest

from core.avatar import avatar_url
from core.reaction import emoji_id, likes_to_emoji_ids
from core.recall import can_recall_quoted
from core.rules import Cooldown, follow_target, should_follow, split_set


class UtilityTests(unittest.TestCase):
    def test_avatar_url(self):
        self.assertEqual(
            avatar_url("12345"),
            "https://q1.qlogo.cn/g?b=qq&nk=12345&s=640",
        )
        self.assertIsNone(avatar_url("not-a-qq"))

    def test_emoji_id(self):
        self.assertEqual(emoji_id("heart"), "66")
        self.assertEqual(emoji_id("76"), "76")
        self.assertIsNone(emoji_id("not-emoji"))

    def test_likes_filter_cancel(self):
        ids = likes_to_emoji_ids(
            {
                "likes": [
                    {"emoji_id": "66", "count": 1},
                    {"emoji_id": "76", "count": 0},
                ]
            }
        )
        self.assertEqual(ids, ["66"])

    def test_recall_permissions(self):
        ok, _ = can_recall_quoted(
            quoted_sender_id="999", self_id="999", allow_others=False,
            requester_is_manager=False,
        )
        self.assertTrue(ok)
        ok, _ = can_recall_quoted(
            quoted_sender_id="123", self_id="999", allow_others=True,
            requester_is_manager=False,
        )
        self.assertFalse(ok)
        ok, _ = can_recall_quoted(
            quoted_sender_id="123", self_id="999", allow_others=True,
            requester_is_manager=True,
        )
        self.assertTrue(ok)

    def test_follow_target(self):
        self.assertEqual(follow_target("1", "2", "original"), "2")
        self.assertEqual(follow_target("1", "2", "sender"), "1")

    def test_probability_and_cooldown(self):
        class Rng:
            def __init__(self, value):
                self.value = value

            def random(self):
                return self.value

        cooldown = Cooldown(30)
        self.assertTrue(should_follow(1.0, cooldown, "g", Rng(0.0), now=100))
        self.assertFalse(should_follow(0.0, cooldown, "g", Rng(0.0), now=100))
        cooldown.mark("g", now=100)
        self.assertFalse(should_follow(1.0, cooldown, "g", Rng(0.0), now=110))
        self.assertTrue(should_follow(1.0, cooldown, "g", Rng(0.0), now=131))

    def test_split_set(self):
        self.assertEqual(split_set("1, 2，3"), {"1", "2", "3"})
        self.assertEqual(split_set(""), set())


if __name__ == "__main__":
    unittest.main()
