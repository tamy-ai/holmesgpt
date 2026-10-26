from typing import Any

from tamy.slack_bot.thread import read_thread


class Client:
    """Slack's conversations.replies: pages of `page_size`, with a cursor to the next page."""

    def __init__(self, total: int, page_size: int) -> None:
        self.total, self.page_size = total, page_size
        self.calls: list[dict[str, Any]] = []

    def conversations_replies(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        start = int(kwargs.get("cursor") or 0)
        end = min(start + self.page_size, self.total)
        more = end < self.total
        return {
            "messages": [{"text": f"m{n}"} for n in range(start, end)],
            "has_more": more,
            "response_metadata": {"next_cursor": str(end) if more else ""},
        }


def test_every_page_of_the_thread_is_read_not_only_the_first() -> None:
    messages = read_thread(Client(total=95, page_size=40), "C1", "1.0")

    assert [m["text"] for m in messages] == [f"m{n}" for n in range(95)]


def test_a_huge_thread_stops_at_the_cap_and_says_so() -> None:
    messages = read_thread(Client(total=1000, page_size=100), "C1", "1.0", max_messages=250)

    assert len(messages) == 251  # 250 messages and the marker
    assert "cortado" in messages[-1]["text"]


def test_a_short_thread_needs_one_call() -> None:
    client = Client(total=3, page_size=40)

    assert len(read_thread(client, "C1", "1.0")) == 3
    assert len(client.calls) == 1
