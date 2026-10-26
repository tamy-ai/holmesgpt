"""The conversation of a Slack thread and the approvals waiting for a click.

In memory, with a time limit: an approval older than the limit is gone, and a click on
it says so. A restart forgets the threads, and the bot rebuilds the context from the
thread itself (`bot.thread_context`).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Pending:
    channel: str
    thread_ts: str
    requester: str
    history: list[dict[str, Any]]
    tool_call_ids: list[str]


class Store:
    def __init__(
        self, ttl_seconds: float = 24 * 3600, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._history: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}
        self._pending: dict[str, tuple[float, Pending]] = {}

    def set_history(self, channel: str, thread_ts: str, history: list[dict[str, Any]]) -> None:
        with self._lock:
            self._history[(channel, thread_ts)] = (self._clock(), history)

    def history(self, channel: str, thread_ts: str) -> list[dict[str, Any]] | None:
        with self._lock:
            entry = self._history.get((channel, thread_ts))
            if entry is None or self._clock() - entry[0] > self._ttl:
                self._history.pop((channel, thread_ts), None)
                return None
            return entry[1]

    def put_pending(self, request_id: str, pending: Pending) -> None:
        with self._lock:
            self._pending[request_id] = (self._clock(), pending)

    def take_pending(self, request_id: str) -> Pending | None:
        """The approval, once. A second click, or an expired one, gets None."""
        with self._lock:
            entry = self._pending.pop(request_id, None)
        if entry is None or self._clock() - entry[0] > self._ttl:
            return None
        return entry[1]
