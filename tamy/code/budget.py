"""A cap on code reads for each conversation, enforced by the tool and not by the prompt.

On 2026-10-26 a model with the code open made 93 searches for one bug and the Slack thread timed
out. A budget in the prompt did not stop it. The tool says no, and the model has to answer.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class Budget:
    def __init__(self, limit: int, window_s: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._limit = limit
        self._window_s = window_s
        self._clock = clock
        self._lock = threading.Lock()
        self._calls: dict[str, list[float]] = {}

    def spend(self, key: str) -> bool:
        """True while the conversation still has calls left. A refusal does not use up a call."""
        now = self._clock()
        with self._lock:
            recent = [t for t in self._calls.get(key, []) if now - t < self._window_s]
            if len(recent) >= self._limit:
                self._calls[key] = recent
                return False
            self._calls[key] = [*recent, now]
            return True
