"""Reads a whole Slack thread. `conversations.replies` returns one page: the rest is behind a cursor."""

from __future__ import annotations

from typing import Any

PAGE_SIZE = 100
MAX_MESSAGES = 300


def read_thread(client: Any, channel: str, thread_ts: str, max_messages: int = MAX_MESSAGES) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    cursor = ""
    while True:
        page = client.conversations_replies(channel=channel, ts=thread_ts, limit=PAGE_SIZE, cursor=cursor or None)
        messages.extend(page["messages"])
        cursor = str((page.get("response_metadata") or {}).get("next_cursor") or "")
        if not page.get("has_more") or not cursor:
            return messages
        if len(messages) >= max_messages:
            return [*messages[:max_messages], {"text": f"(fio cortado em {max_messages} mensagens)"}]
