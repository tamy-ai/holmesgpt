"""What the status job does with what it read from Jira (TA-1316). Pure: no
Slack, no Jira, no database."""

from __future__ import annotations

from tamy.chamados.status_sync import (
    MISSING_STATUS,
    JiraReading,
    SyncedTicket,
    plan_sync,
)


def _ticket(
    status: str | None = "A fazer", resolved: bool = False, key: str = "TA-1"
) -> SyncedTicket:
    return SyncedTicket(
        link_id=1,
        jira_key=key,
        last_status=status,
        resolved=resolved,
        slack_channel_id="C1",
        slack_thread_ts="1.0",
    )


def test_a_new_status_is_posted_and_recorded() -> None:
    plan = plan_sync([_ticket("A fazer")], [JiraReading("TA-1", "Fazendo")])

    [change] = plan.changes
    assert (change.before, change.after) == ("A fazer", "Fazendo")
    assert not plan.readings[0].delivered
    assert [r.status for r in plan.readings] == ["Fazendo"]


def test_the_same_status_is_recorded_but_not_posted() -> None:
    """Every read counts for the queue's "sem leitura", even with no change."""
    plan = plan_sync([_ticket("Fazendo")], [JiraReading("TA-1", "Fazendo")])

    assert plan.changes == []
    assert [r.link_id for r in plan.readings] == [1]


def test_em_dev_is_done_in_jira_but_not_a_delivery() -> None:
    plan = plan_sync([_ticket("Fazendo")], [JiraReading("TA-1", "Em Dev")])

    assert plan.changes[0].after == "Em Dev"
    assert not plan.readings[0].delivered


def test_the_first_entry_into_production_is_a_delivery_once() -> None:
    first = plan_sync([_ticket("Em Dev")], [JiraReading("TA-1", "Em produção")])
    again = plan_sync(
        [_ticket("A fazer", resolved=True)], [JiraReading("TA-1", "Em produção")]
    )

    assert first.readings[0].delivered
    # A reopened ticket that reaches production again: not a second SLA.
    assert not again.readings[0].delivered


def test_a_ticket_jira_no_longer_returns_is_missing_and_never_delivered() -> None:
    plan = plan_sync([_ticket("Fazendo")], [])

    [change] = plan.changes
    assert change.after == MISSING_STATUS
    assert not plan.readings[0].delivered
    # Said once: the next run reads the same absence and posts nothing.
    again = plan_sync([_ticket(MISSING_STATUS)], [])
    assert again.changes == []


def test_a_reading_for_a_key_the_bot_does_not_know_is_ignored() -> None:
    plan = plan_sync(
        [_ticket()],
        [JiraReading("TA-1", "A fazer"), JiraReading("XX-9", "Em produção")],
    )

    assert [r.link_id for r in plan.readings] == [1]
    assert plan.changes == []
