"""The status of a ticket comes back to its Slack thread (TA-1316).

A beat job reads, from Jira, the status of the tickets the bot opened, and this
module decides what that reading means. The rules (decisions 0728 and 0731):

- Every reading is recorded (`last_synced_at`), even with no change: the queue
  calls a past-due ticket late only when it was read open after its due date.
- A delivery is ONLY the first entry into "Em produção". "Em Dev" is Done in
  Jira's category but not production. A ticket reopened and delivered again is
  not a second SLA.
- A ticket that Jira no longer returns (deleted, or moved where the bot cannot
  see it) is "missing", said once, and never counted as delivered.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

PRODUCTION_STATUS = "Em produção"
REOPEN_STATUS = "A fazer"
# What `last_status` holds for a ticket Jira stopped returning.
MISSING_STATUS = "fora do Jira"


@dataclass(frozen=True)
class SyncedTicket:
    link_id: int
    jira_key: str
    last_status: str | None
    # `resolved_at` is set: the first delivery already happened.
    resolved: bool
    slack_channel_id: str
    slack_thread_ts: str


@dataclass(frozen=True)
class JiraReading:
    key: str
    status: str


@dataclass(frozen=True)
class StatusRecord:
    """What to record for one ticket in this run."""

    link_id: int
    status: str
    # This reading is the first delivery: record `resolved_at` now.
    delivered: bool


@dataclass(frozen=True)
class StatusChange:
    """What to tell the ticket's thread."""

    link_id: int
    jira_key: str
    before: str | None
    after: str
    slack_channel_id: str
    slack_thread_ts: str


@dataclass(frozen=True)
class SyncPlan:
    readings: list[StatusRecord]
    changes: list[StatusChange]


def plan_sync(
    tickets: Sequence[SyncedTicket], readings: Sequence[JiraReading]
) -> SyncPlan:
    """`tickets` are the ones this run asked Jira about; a ticket with no
    reading back is missing. A reading for an unknown key is ignored."""
    read = {reading.key: reading.status for reading in readings}
    recorded: list[StatusRecord] = []
    changes: list[StatusChange] = []
    for ticket in tickets:
        status = read.get(ticket.jira_key, MISSING_STATUS)
        delivered = status == PRODUCTION_STATUS and not ticket.resolved
        recorded.append(StatusRecord(ticket.link_id, status, delivered))
        if status != ticket.last_status:
            changes.append(
                StatusChange(
                    link_id=ticket.link_id,
                    jira_key=ticket.jira_key,
                    before=ticket.last_status,
                    after=status,
                    slack_channel_id=ticket.slack_channel_id,
                    slack_thread_ts=ticket.slack_thread_ts,
                )
            )
    return SyncPlan(readings=recorded, changes=changes)
