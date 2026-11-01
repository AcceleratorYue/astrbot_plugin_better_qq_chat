"""冷却、概率、白名单与跟戳目标选择。"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any


def as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "启用", "开启"}
    return default


def as_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def as_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(1.0, number))


def split_set(value: Any) -> set[str]:
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip() for item in value if str(item).strip()}
    return {part.strip() for part in str(value or "").replace("，", ",").split(",") if part.strip()}


@dataclass
class Cooldown:
    seconds: float
    _last: dict[str, float] = field(default_factory=dict)

    def ready(self, key: str, now: float | None = None) -> bool:
        moment = time.time() if now is None else now
        last = self._last.get(key, 0.0)
        return moment - last >= self.seconds

    def mark(self, key: str, now: float | None = None) -> None:
        self._last[key] = time.time() if now is None else now

    def prune(self, now: float | None = None, keep: int = 2000) -> None:
        if len(self._last) <= keep:
            return
        moment = time.time() if now is None else now
        ordered = sorted(self._last.items(), key=lambda item: item[1])
        for key, _ in ordered[: len(self._last) - keep]:
            self._last.pop(key, None)


def should_follow(
    probability: float,
    cooldown: Cooldown,
    scope: str,
    rng: random.Random | None = None,
    now: float | None = None,
) -> bool:
    if probability <= 0:
        return False
    if not cooldown.ready(scope, now):
        return False
    rng = rng or random
    return rng.random() < probability


def follow_target(sender_id: str, target_id: str, mode: str) -> str:
    return sender_id if str(mode or "").strip().lower() == "sender" else target_id
