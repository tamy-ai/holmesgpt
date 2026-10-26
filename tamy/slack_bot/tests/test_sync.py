"""The status of a ticket comes back to its Slack thread, once per status (TA-1316)."""

from __future__ import annotations

from typing import Any

from tamy.slack_bot.sync import (
    NOTIFIED_PREFIX,
    SyncJira,
    SyncSlack,
    notices_for,
    resolved_blocks,
    run_sync,
    thread_of,
)


def _issue(key: str, status: str, labels: list[str], summary: str = "Vendas: total diferente") -> dict[str, Any]:
    return {"key": key, "fields": {"status": {"name": status}, "labels": labels, "summary": summary}}


THREAD = "slack-C0CCVHJM35W-1793030059.240709"


def test_the_thread_comes_from_the_ticket_label() -> None:
    assert thread_of(["tipo-bug", THREAD]) == ("C0CCVHJM35W", "1793030059.240709")
    assert thread_of(["tipo-bug"]) is None
    assert thread_of(["slack-sem-fio"]) is None


def test_a_ticket_that_started_work_says_so_once() -> None:
    notices = notices_for([_issue("TA-1", "Fazendo", ["origem-slack", THREAD])])

    assert [(n.key, n.status, n.channel, n.thread_ts) for n in notices] == [
        ("TA-1", "Fazendo", "C0CCVHJM35W", "1793030059.240709")
    ]
    assert notices_for([_issue("TA-1", "Fazendo", ["origem-slack", THREAD, NOTIFIED_PREFIX + "fazendo"])]) == []


def test_only_fazendo_and_em_producao_are_said() -> None:
    for status in ("A fazer", "Em Dev"):
        assert notices_for([_issue("TA-1", status, ["origem-slack", THREAD])]) == []
    assert len(notices_for([_issue("TA-2", "Em produção", ["origem-slack", THREAD])])) == 1


def test_a_ticket_of_no_thread_or_not_opened_by_the_bot_is_never_said() -> None:
    assert notices_for([_issue("TA-1", "Fazendo", ["origem-slack"])]) == []
    assert notices_for([_issue("TA-1", "Fazendo", [THREAD])]) == []


def test_the_delivery_asks_resolveu_with_two_buttons_that_carry_the_key() -> None:
    blocks = resolved_blocks("TA-9")

    buttons = [e for b in blocks for e in b.get("elements", []) if e.get("type") == "button"]
    assert {b["action_id"] for b in buttons} == {"holmes_resolved_yes", "holmes_resolved_no"}
    assert {b["value"] for b in buttons} == {"TA-9"}


class FakeJira(SyncJira):
    def __init__(self, issues: list[dict[str, Any]]) -> None:
        self.issues, self.added, self.queries = issues, [], []

    def search(self, jql: str, **_: Any) -> list[dict[str, Any]]:
        self.queries.append(jql)
        return self.issues

    def add_label(self, key: str, label: str) -> None:
        self.added.append((key, label))


class FakeSlack(SyncSlack):
    def __init__(self) -> None:
        self.posts: list[dict[str, Any]] = []

    def post(self, **kwargs: Any) -> str:
        self.posts.append(kwargs)
        return "1.1"


def test_a_run_labels_before_it_posts_and_a_second_run_posts_nothing() -> None:
    jira = FakeJira([_issue("TA-2", "Em produção", ["origem-slack", THREAD])])
    slack = FakeSlack()

    assert run_sync(jira, slack) == 1
    assert jira.added == [("TA-2", NOTIFIED_PREFIX + "em-producao")]
    assert "TA-2" in slack.posts[0]["text"] and any(b["type"] == "actions" for b in slack.posts[0]["blocks"])

    jira.issues = [_issue("TA-2", "Em produção", ["origem-slack", THREAD, NOTIFIED_PREFIX + "em-producao"])]
    assert run_sync(jira, slack) == 0
    assert len(slack.posts) == 1


def test_a_failure_to_label_posts_nothing_so_the_thread_is_never_spammed() -> None:
    class BrokenJira(FakeJira):
        def add_label(self, key: str, label: str) -> None:
            raise RuntimeError("jira down")

    slack = FakeSlack()
    jira = BrokenJira([_issue("TA-2", "Fazendo", ["origem-slack", THREAD])])

    assert run_sync(jira, slack) == 0
    assert slack.posts == []


def test_the_search_only_asks_for_tickets_of_the_bot_that_changed_recently() -> None:
    jira = FakeJira([])

    run_sync(jira, FakeSlack())

    assert "origem-slack" in jira.queries[0] and "updated >= -" in jira.queries[0]


from tamy.slack_bot.sync import answer_resolved  # noqa: E402


class ResolveJira:
    def __init__(self, labels: list[str]) -> None:
        self.labels, self.comments, self.added, self.moved = labels, [], [], []

    def issue_labels(self, key: str) -> list[str]:
        return self.labels

    def add_comment(self, key: str, body: dict[str, Any]) -> None:
        self.comments.append((key, body))

    def add_label(self, key: str, label: str) -> None:
        self.added.append((key, label))

    def reopen(self, key: str) -> None:
        self.moved.append(key)


class ThreadReader:
    def __init__(self, root_user: str) -> None:
        self.root_user = root_user

    def replies(self, channel: str, thread_ts: str) -> list[dict[str, Any]]:
        return [{"user": self.root_user, "text": "abre um bug"}]

    def display_name(self, user: str) -> str:
        return "Matheus"


def test_the_one_who_opened_the_thread_confirms_and_the_ticket_gets_a_comment_and_a_label() -> None:
    jira = ResolveJira(["origem-slack", THREAD])

    said, changed = answer_resolved("TA-9", "U1", True, jira, ThreadReader("U1"))

    assert "Obrigado" in said and changed
    assert jira.added == [("TA-9", "confirmado-no-slack")] and len(jira.comments) == 1 and jira.moved == []


def test_ainda_nao_reopens_the_ticket_and_says_so() -> None:
    jira = ResolveJira(["origem-slack", THREAD])

    said, _ = answer_resolved("TA-9", "U1", False, jira, ThreadReader("U1"))

    assert "reabri" in said.lower()
    assert jira.moved == ["TA-9"] and len(jira.comments) == 1


def test_a_stranger_changes_nothing() -> None:
    jira = ResolveJira(["origem-slack", THREAD])

    said, changed = answer_resolved("TA-9", "U2", True, jira, ThreadReader("U1"))

    assert "quem pediu" in said and not changed
    assert jira.added == [] and jira.comments == [] and jira.moved == []


def test_a_ticket_the_bot_did_not_open_is_never_touched() -> None:
    jira = ResolveJira(["tipo-bug"])

    answer_resolved("TA-9", "U1", True, jira, ThreadReader("U1"))

    assert jira.added == [] and jira.comments == []
