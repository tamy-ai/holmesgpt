"""The bot: a question gets an answer, a write waits for the click of who asked."""

from __future__ import annotations

from typing import Any

from tamy.slack_bot.bot import Bot, SYSTEM_PROMPT
from tamy.slack_bot.state import Store


class FakeSlack:
    def __init__(self) -> None:
        self.posts: list[dict[str, Any]] = []
        self.updates: list[dict[str, Any]] = []
        self.thread: list[dict[str, Any]] = []

    def post(self, **kwargs: Any) -> str:
        self.posts.append(kwargs)
        return f"ts-{len(self.posts)}"

    def update(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)

    def replies(self, channel: str, thread_ts: str) -> list[dict[str, Any]]:
        return self.thread


class FakeHolmes:
    def __init__(self, answers: list[dict[str, Any]]) -> None:
        self.answers = list(answers)
        self.calls: list[dict[str, Any]] = []

    def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        return self.answers.pop(0)


def _answer(text: str = "ok", **extra: Any) -> dict[str, Any]:
    return {"analysis": text, "conversation_history": [{"role": "assistant", "content": text}], **extra}


def _pending() -> dict[str, Any]:
    return {
        "tool_call_id": "call-1",
        "tool_name": "jira_write_request",
        "description": "x",
        "params": {
            "url": "https://api.atlassian.com/ex/jira/a/rest/api/2/issue",
            "method": "POST",
            "body": '{"fields": {"summary": "S", "issuetype": {"name": "Bug"}}}',
        },
    }


def _bot(answers: list[dict[str, Any]]) -> tuple[Bot, FakeSlack, FakeHolmes, Store]:
    slack, holmes, store = FakeSlack(), FakeHolmes(answers), Store(clock=lambda: 0.0)
    return Bot(slack, holmes, store), slack, holmes, store


def test_a_question_gets_one_answer_in_the_thread() -> None:
    bot, slack, holmes, _ = _bot([_answer("O CMV está em 31%")])

    bot.ask(channel="C1", thread_ts="1.0", user="U1", text="qual o CMV?")

    assert "O CMV está em 31%" in slack.updates[-1]["text"]
    assert slack.posts[0]["thread_ts"] == "1.0"
    payload = holmes.calls[0]
    assert payload["ask"] == "qual o CMV?"
    assert payload["enable_tool_approval"] is True
    assert payload["additional_system_prompt"] == SYSTEM_PROMPT


def test_the_second_message_of_a_thread_carries_the_history() -> None:
    bot, _, holmes, _ = _bot([_answer("um"), _answer("dois")])

    bot.ask(channel="C1", thread_ts="1.0", user="U1", text="primeira")
    bot.ask(channel="C1", thread_ts="1.0", user="U1", text="segunda")

    assert holmes.calls[1]["conversation_history"] == [{"role": "assistant", "content": "um"}]


def test_a_thread_the_bot_forgot_is_rebuilt_from_slack() -> None:
    bot, slack, holmes, _ = _bot([_answer("ok")])
    slack.thread = [
        {"user": "U1", "text": "o painel de vendas está errado"},
        {"user": "UBOT", "text": "Qual loja?", "bot_id": "B1"},
    ]

    bot.ask(channel="C1", thread_ts="1.0", user="U1", text="a loja 3")

    ask = holmes.calls[0]["ask"]
    assert "o painel de vendas está errado" in ask and "a loja 3" in ask


def test_a_write_waits_for_the_click_and_runs_nothing() -> None:
    bot, slack, holmes, store = _bot([_answer("vou criar", pending_approvals=[_pending()])])

    bot.ask(channel="C1", thread_ts="1.0", user="U9", text="abre um bug")

    assert len(holmes.calls) == 1, "nothing ran yet"
    blocks = slack.posts[-1]["blocks"]
    assert any(e.get("action_id") == "holmes_approve" for b in blocks for e in b.get("elements", []))
    assert store.take_pending(blocks[1]["elements"][0]["value"]) is not None


def test_only_who_asked_can_approve() -> None:
    bot, slack, holmes, _ = _bot([_answer("vou criar", pending_approvals=[_pending()])])
    bot.ask(channel="C1", thread_ts="1.0", user="U9", text="abre um bug")
    request_id = slack.posts[-1]["blocks"][1]["elements"][0]["value"]

    result = bot.decide(request_id=request_id, user="U2", approved=True)

    assert "só" in result.lower()
    assert len(holmes.calls) == 1, "a stranger's click runs nothing"


def test_the_click_of_who_asked_resumes_with_the_decision() -> None:
    bot, slack, holmes, _ = _bot(
        [_answer("vou criar", pending_approvals=[_pending()]), _answer("Criei TA-1")]
    )
    bot.ask(channel="C1", thread_ts="1.0", user="U9", text="abre um bug")
    request_id = slack.posts[-1]["blocks"][1]["elements"][0]["value"]

    bot.decide(request_id=request_id, user="U9", approved=True)

    resume = holmes.calls[1]
    assert resume["tool_decisions"] == [{"tool_call_id": "call-1", "approved": True}]
    assert resume["enable_tool_approval"] is True
    assert "Criei TA-1" in slack.posts[-1]["text"] or "Criei TA-1" in slack.updates[-1]["text"]


def test_a_denial_goes_back_as_a_denial() -> None:
    bot, slack, holmes, _ = _bot(
        [_answer("vou criar", pending_approvals=[_pending()]), _answer("Tudo bem, não criei")]
    )
    bot.ask(channel="C1", thread_ts="1.0", user="U9", text="abre um bug")
    request_id = slack.posts[-1]["blocks"][1]["elements"][0]["value"]

    bot.decide(request_id=request_id, user="U9", approved=False)

    assert holmes.calls[1]["tool_decisions"][0]["approved"] is False


def test_a_second_click_runs_nothing() -> None:
    bot, slack, holmes, _ = _bot(
        [_answer("vou criar", pending_approvals=[_pending()]), _answer("Criei TA-1")]
    )
    bot.ask(channel="C1", thread_ts="1.0", user="U9", text="abre um bug")
    request_id = slack.posts[-1]["blocks"][1]["elements"][0]["value"]

    bot.decide(request_id=request_id, user="U9", approved=True)
    again = bot.decide(request_id=request_id, user="U9", approved=True)

    assert len(holmes.calls) == 2
    assert "expirou" in again.lower() or "já" in again.lower()


def test_when_holmes_fails_the_person_hears_it_and_nothing_hangs() -> None:
    class Broken(FakeHolmes):
        def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("holmes is down")

    slack, store = FakeSlack(), Store(clock=lambda: 0.0)
    bot = Bot(slack, Broken([]), store)

    bot.ask(channel="C1", thread_ts="1.0", user="U1", text="oi")

    assert "não consegui" in slack.updates[-1]["text"].lower()


def test_the_system_prompt_forbids_writing_without_the_click_and_client_text() -> None:
    assert "aprova" in SYSTEM_PROMPT.lower()
    assert "texto de cliente" in SYSTEM_PROMPT.lower()
    assert "chamado-regras" in SYSTEM_PROMPT


def test_a_pause_without_text_never_shows_the_word_none() -> None:
    answer = {"analysis": None, "conversation_history": [], "pending_approvals": [_pending()]}
    bot, slack, _, _ = _bot([answer])

    bot.ask(channel="C1", thread_ts="1.0", user="U9", text="abre um bug")

    assert "None" not in slack.updates[0]["text"]
