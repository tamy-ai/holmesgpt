"""A Slack thread inside a model prompt, as data that cannot close its tags.

Slack text is untrusted (`.claude/rules/untrusted-content.md`). Every prompt
that carries a thread uses these helpers.
"""

from __future__ import annotations

MAX_THREAD_CHARS = 6000
DATA_TAG = "slack_thread"


def as_data(text: str) -> str:
    """Slack text inside the data tags, unable to close them."""
    return text.replace(f"</{DATA_TAG}>", f"</ {DATA_TAG}>")


def thread_block(text: str) -> str:
    return f"<{DATA_TAG}>\n{as_data(text)}\n</{DATA_TAG}>"
