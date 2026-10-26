"""The ticket tool the agent calls: the model picks the fields, the code decides.

`preview` says what would be created and what is missing; `create` writes to Jira only when
the checklist is complete and no ticket for the same thread or the same problem exists.
"""

from __future__ import annotations

import datetime
import json
from typing import Any

from tamy.chamados.cli import Result, TicketInput, create, preview, similar
from tamy.chamados.common import BUSINESS_TZ

NOW = datetime.datetime(2026, 10, 26, 10, 0, tzinfo=BUSINESS_TZ)

BUG = TicketInput(
    ticket_type="bug",
    priority="P2",
    summary="Vendas: total diferente do PDV",
    client="Martita",
    answers={
        "bug_client": "Martita, loja 3",
        "bug_steps": "Abrir Vendas\nEscolher ontem",
        "bug_expected": "O mesmo total do PDV, R$ 1.300,00",
        "bug_actual": "O painel mostra R$ 1.210,00",
    },
    area="vendas",
    channel="web",
    thread_ref="C1-1700.0",
    requester="Ana",
    thread_url="https://tamy.slack.com/archives/C1/p1700",
)


class FakeJira:
    def __init__(self, existing: list[dict[str, Any]] | None = None) -> None:
        self.existing = existing or []
        self.created: list[dict[str, Any]] = []
        self.queries: list[str] = []

    def search(self, jql: str, **_: Any) -> list[dict[str, Any]]:
        self.queries.append(jql)
        return self.existing

    def create_issue(self, fields: dict[str, Any]) -> str:
        self.created.append(fields)
        return "TA-1400"


def test_a_complete_bug_previews_with_deadline_labels_and_description() -> None:
    result = preview(BUG, now=NOW)

    assert result.ok and result.missing == []
    assert result.issue_type == "Bug"
    assert result.due_on == datetime.date(2026, 11, 3)  # 5 working days after Mon 26/10; 02/11 is Finados
    assert {"tipo-bug", "sla-p2", "area-vendas", "canal-web", "origem-slack"} <= set(result.labels)
    assert "*Resumo*" in result.description_preview
    assert "*Esperado*" in result.description_preview and "R$ 1.300,00" in result.description_preview


def test_a_bug_without_what_happened_asks_for_it_and_writes_nothing() -> None:
    incomplete = TicketInput(**{**BUG.__dict__, "answers": {k: v for k, v in BUG.answers.items() if k != "bug_actual"}})
    jira = FakeJira()

    result = create(incomplete, jira, now=NOW)

    assert not result.ok
    assert [q["id"] for q in result.missing] == ["bug_actual"]
    assert jira.created == []


def test_create_writes_one_issue_with_the_idempotency_label() -> None:
    jira = FakeJira()

    result = create(BUG, jira, now=NOW)

    assert result.ok and result.key == "TA-1400"
    (fields,) = jira.created
    assert fields["project"] == {"key": "TA"}
    assert fields["issuetype"] == {"name": "Bug"}
    assert "slack-C1-1700.0" in fields["labels"]
    assert fields["duedate"] == "2026-11-03"
    assert isinstance(fields["description"], dict), "the body is an Atlassian document"


def test_the_same_thread_never_creates_twice() -> None:
    jira = FakeJira([{"key": "TA-1300", "fields": {"summary": "Vendas: total diferente do PDV"}}])

    result = create(BUG, jira, now=NOW)

    assert not result.ok and result.duplicate_of == "TA-1300"
    assert "slack-C1-1700.0" in jira.queries[0]
    assert jira.created == []


def test_a_similar_open_ticket_stops_the_create_until_the_person_says_it_is_different() -> None:
    class SimilarOnly(FakeJira):
        def search(self, jql: str, **_: Any) -> list[dict[str, Any]]:
            self.queries.append(jql)
            return [] if "slack-" in jql else [
                {"key": "TA-1290", "fields": {"summary": "Vendas: total do painel difere do PDV", "status": {"name": "A fazer"}}}
            ]

    jira = SimilarOnly()

    first = create(BUG, jira, now=NOW)
    forced = create(TicketInput(**{**BUG.__dict__, "not_a_duplicate": True}), jira, now=NOW)

    assert not first.ok and [s["key"] for s in first.similar] == ["TA-1290"]
    assert jira.created and forced.ok, "with the person's word, it creates"


def test_the_similar_search_is_by_words_of_the_title_in_the_recent_window() -> None:
    jira = FakeJira([{"key": "TA-1", "fields": {"summary": "x"}}])

    found = similar("Vendas: total diferente do PDV", jira)

    assert [f["key"] for f in found] == ["TA-1"]
    jql = jira.queries[0]
    assert "project = TA" in jql and "created >= -60d" in jql and "Vendas" in jql


def test_a_title_with_quotes_cannot_break_out_of_the_query() -> None:
    jira = FakeJira()

    similar('x" OR project = SECRET OR text ~ "y', jira)

    assert 'project = SECRET' not in jira.queries[0].replace('\\"', "")


def test_the_result_is_json_the_agent_can_read() -> None:
    payload = json.loads(preview(BUG, now=NOW).to_json())

    assert payload["ok"] is True and payload["issue_type"] == "Bug"
    assert isinstance(Result(ok=False, error="x").to_json(), str)


def test_an_unknown_type_or_priority_is_refused_with_the_valid_ones() -> None:
    bad = TicketInput(**{**BUG.__dict__, "ticket_type": "hotfix"})

    result = preview(bad, now=NOW)

    assert not result.ok and "bug" in result.error and "incident" in result.error


def test_a_second_create_in_the_same_thread_is_refused_even_when_jira_search_is_stale() -> None:
    """Seen live on 26/10/2026: Jira's search took seconds to see a new ticket, and a second
    call in the same thread created TA-1357 as a duplicate of TA-1356. The process remembers
    what it created, whatever the search says."""
    from tamy.chamados import cli

    cli.forget_created()
    jira = FakeJira()  # search always answers "nothing": a stale index

    first = create(BUG, jira, now=NOW)
    second = create(BUG, jira, now=NOW)

    assert first.ok and first.key == "TA-1400"
    assert not second.ok and second.duplicate_of == "TA-1400"
    assert len(jira.created) == 1


def test_two_creates_at_the_same_time_in_one_thread_create_one() -> None:
    import threading

    from tamy.chamados import cli

    cli.forget_created()
    started = threading.Barrier(2)

    class Slow(FakeJira):
        def create_issue(self, fields: dict[str, Any]) -> str:
            import time

            time.sleep(0.05)
            return super().create_issue(fields)

    jira = Slow()
    results: list[Result] = []

    def go() -> None:
        started.wait()
        results.append(create(BUG, jira, now=NOW))

    threads = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert len(jira.created) == 1
    assert sorted(r.ok for r in results) == [False, True]


def test_a_failed_create_does_not_block_the_retry() -> None:
    from tamy.chamados import cli

    cli.forget_created()

    class Broken(FakeJira):
        def create_issue(self, fields: dict[str, Any]) -> str:
            raise RuntimeError("jira is down")

    try:
        create(BUG, Broken(), now=NOW)
    except RuntimeError:
        pass

    assert create(BUG, FakeJira(), now=NOW).ok
