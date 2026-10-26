import json

import pytest

from tamy.slack_bot.sse import HolmesStreamError, final_message


def sse(event: str, data: dict) -> list[str]:
    return [f"event: {event}", f"data: {json.dumps(data)}", ""]


def test_the_answer_end_is_the_result():
    lines = sse("start_tool_calling", {"tool_name": "x"}) + sse(
        "ai_answer_end", {"analysis": "pronto", "conversation_history": [{"role": "user"}]}
    )
    assert final_message(lines)["analysis"] == "pronto"


def test_an_approval_pause_is_the_result_and_carries_the_pending_calls():
    lines = sse("ai_message", {"content": "x"}) + sse(
        "approval_required",
        {"analysis": "", "requires_approval": True, "pending_approvals": [{"tool_call_id": "t1"}]},
    )
    assert final_message(lines)["pending_approvals"] == [{"tool_call_id": "t1"}]


def test_an_error_event_raises_instead_of_looking_like_an_empty_answer():
    with pytest.raises(HolmesStreamError):
        final_message(sse("error", {"description": "boom"}))


def test_a_stream_without_an_end_raises():
    with pytest.raises(HolmesStreamError):
        final_message(sse("start_tool_calling", {"tool_name": "x"}))
