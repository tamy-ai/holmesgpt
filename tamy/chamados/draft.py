"""The ticket draft and its vocabulary. One shape from the classifier to Jira.

The ORM row (`SupportTicketLink`) never leaves the query layer; readers get a
frozen `TicketLink` with typed enums.
"""

from __future__ import annotations

import datetime
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class TicketState(StrEnum):
    DRAFT = "DRAFT"
    CREATING = "CREATING"
    CREATED = "CREATED"
    CANCELLED = "CANCELLED"


class TicketType(StrEnum):
    BUG = "bug"
    IMPROVEMENT = "improvement"
    FEATURE = "feature"
    SUPPORT = "support"
    ACCESS = "access"
    INCIDENT = "incident"
    QUESTION = "question"
    TASK = "task"


class TicketPriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


@dataclass(frozen=True)
class TicketDraft:
    ticket_type: TicketType
    priority: TicketPriority
    summary: str
    # The client the thread names, as text. Never used as scope.
    client_hint: str | None
    # Checklist answers by question id (`checklist.py`).
    answers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TicketLink:
    id: int
    created_at: datetime.datetime
    state: TicketState
    slack_channel_id: str
    slack_thread_ts: str
    preview_message_ts: str | None
    created_by_slack_user: str
    draft: TicketDraft
    # False when the classifier failed and type and priority are defaults.
    classified: bool
    # Set after creation when the client was identified; never from Slack text alone.
    organization_id: int | None
    jira_key: str | None
    last_error: str | None
