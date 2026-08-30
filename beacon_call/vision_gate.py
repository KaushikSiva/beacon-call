"""Temporal confirmation gate for noisy per-frame browser detections."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from time import monotonic


@dataclass
class PresenceGate:
    required_hits: int = 3
    threshold: float = 0.66
    window_seconds: float = 4.0
    cooldown_seconds: float = 20.0
    _hits: deque[float] = field(default_factory=deque, init=False)
    _last_created: float | None = field(default=None, init=False)

    @property
    def streak(self) -> int:
        return len(self._hits)

    def observe(self, *, person_present: bool, confidence: float, now: float | None = None) -> bool:
        timestamp = monotonic() if now is None else now
        while self._hits and timestamp - self._hits[0] > self.window_seconds:
            self._hits.popleft()

        if not person_present or confidence < self.threshold:
            self._hits.clear()
            return False

        if (
            self._last_created is not None
            and timestamp - self._last_created < self.cooldown_seconds
        ):
            self._hits.clear()
            return False

        self._hits.append(timestamp)
        if len(self._hits) < self.required_hits:
            return False

        self._hits.clear()
        self._last_created = timestamp
        return True

    def reset(self) -> None:
        self._hits.clear()
        self._last_created = None
