"""The conversation of a thread and the approvals waiting for a click."""

from __future__ import annotations

from tamy.slack_bot.state import Pending, Store


def test_a_thread_keeps_its_history() -> None:
    store = Store(ttl_seconds=60, clock=lambda: 0.0)
    store.set_history("C1", "1.0", [{"role": "user", "content": "oi"}])

    assert store.history("C1", "1.0") == [{"role": "user", "content": "oi"}]
    assert store.history("C1", "2.0") is None


def test_an_old_thread_is_forgotten() -> None:
    now = [0.0]
    store = Store(ttl_seconds=60, clock=lambda: now[0])
    store.set_history("C1", "1.0", [{"role": "user", "content": "oi"}])

    now[0] = 61.0

    assert store.history("C1", "1.0") is None


def test_an_approval_is_taken_once() -> None:
    store = Store(ttl_seconds=60, clock=lambda: 0.0)
    store.put_pending("r1", Pending("C1", "1.0", "U9", [{"role": "user"}], ["call-1"]))

    first = store.take_pending("r1")
    second = store.take_pending("r1")

    assert first is not None and first.requester == "U9"
    assert second is None, "two clicks must never run the write twice"


def test_an_unknown_or_expired_approval_is_none() -> None:
    now = [0.0]
    store = Store(ttl_seconds=60, clock=lambda: now[0])
    store.put_pending("r1", Pending("C1", "1.0", "U9", [], ["c"]))
    now[0] = 61.0

    assert store.take_pending("r1") is None
    assert store.take_pending("nope") is None
