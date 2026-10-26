"""Reads the SSE stream of Holmes `/api/chat`: only the streaming mode can pause for an approval."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

END_EVENTS = {"ai_answer_end", "approval_required"}


class HolmesStreamError(Exception):
    pass


def final_message(lines: Iterable[str]) -> dict[str, Any]:
    """Returns the data of the closing event: the answer, or the pause for an approval."""
    event = ""
    for line in lines:
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data = json.loads(line[5:].strip() or "{}")
            if event == "error":
                raise HolmesStreamError(str(data.get("description") or data))
            if event in END_EVENTS:
                return data
    raise HolmesStreamError("the stream ended with no answer")
