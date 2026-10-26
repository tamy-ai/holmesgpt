"""The Jira fields of a ticket born in Slack.

The description carries the request and the thread link. Client conversation
text never goes to Jira (decision 0667): only links that need a login.

The payload holds only the fields the create screen of the issue type lists
(createmeta): Jira refuses a create that sends any other field. TA's screens
have no priority, so the priority never goes as a field: it goes in the
`sla-pX` label and in the description, with the due date.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from dataclasses import dataclass

from tamy.chamados.jira_rest import AdfNode, JiraConfigError
from tamy.chamados.areas import area_by_slug, clean_channel
from tamy.chamados.draft import TicketDraft
from tamy.chamados.sla import sla_label
from tamy.chamados.ticket_body import build_description
from tamy.chamados.vocabulary import (
    JIRA_ISSUE_TYPE,
    ORIGIN_LABEL,
    TYPE_LABEL_SLUG,
)

JIRA_SUMMARY_MAX = 250


@dataclass(frozen=True)
class TicketRequest:
    thread_ref: str
    project_key: str
    draft: TicketDraft
    # None when Slack did not answer; the ticket says so instead of an empty name.
    requester_name: str | None
    thread_url: str | None
    # None when the type and priority have no SLA (P3, a feature).
    due_on: datetime.date | None
    # The day of the request in São Paulo: it anchors "ontem" and "hoje" in the text.
    requested_on: datetime.date | None = None
    # The files of the thread. The description counts them and never names them.
    thread_file_count: int = 0


def link_label(thread_ref: str) -> str:
    """The label that finds the issue of one Slack thread, so a retry never creates twice."""
    return f"slack-{thread_ref}"


def links_jql(project_key: str, thread_refs: Sequence[str]) -> str:
    """The issues of these threads, by their labels. A label search never fails
    on a deleted issue, where `key in (...)` would."""
    labels = ", ".join(link_label(ref) for ref in thread_refs)
    return f"project = {project_key} AND labels in ({labels})"


def where_labels(draft: TicketDraft) -> list[str]:
    """`canal-whatsapp` and `area-vendas`, only for values of the closed lists."""
    labels: list[str] = []
    channel = clean_channel(draft.answers.get("channel"))
    if channel is not None:
        labels.append(f"canal-{channel.value}")
    area = area_by_slug(draft.answers.get("area", ""))
    if area is not None:
        labels.append(f"area-{area.slug}")
    return labels


def description_of(request: TicketRequest) -> AdfNode:
    return build_description(
        request.draft,
        requester_name=request.requester_name,
        thread_url=request.thread_url,
        due_on=request.due_on,
        requested_on=request.requested_on,
        thread_file_count=request.thread_file_count,
    )


# Always sent: Jira needs them on every create screen.
_ALWAYS = frozenset({"project", "issuetype", "summary"})
# The bot refuses to create without them (see `build_issue_fields`).
_NEEDED = ("labels", "description")


def issue_type_name(request: TicketRequest) -> str:
    return JIRA_ISSUE_TYPE[request.draft.ticket_type]


def build_issue_fields(
    request: TicketRequest, create_fields: frozenset[str]
) -> dict[str, object]:
    """The create payload, cut to `create_fields` (the screen's createmeta)."""
    # A retry finds its issue by the `chamado-<id>` label, and the priority and
    # the due date live in the description: without either field the ticket
    # would be a duplicate or would lose them in silence.
    for needed in _NEEDED:
        if needed not in create_fields:
            raise JiraConfigError(
                f"a tela de criação do tipo {issue_type_name(request)} no Jira "
                f"não tem o campo {needed}, que o bot precisa"
            )
    draft = request.draft
    fields: dict[str, object] = {
        "project": {"key": request.project_key},
        "issuetype": {"name": issue_type_name(request)},
        "summary": " ".join(draft.summary.split())[:JIRA_SUMMARY_MAX],
        "description": description_of(request),
        "labels": [
            ORIGIN_LABEL,
            TYPE_LABEL_SLUG[draft.ticket_type],
            sla_label(draft.priority),
            link_label(request.thread_ref),
            *where_labels(draft),
        ],
    }
    if request.due_on is not None:
        fields["duedate"] = request.due_on.isoformat()
    return {
        name: value
        for name, value in fields.items()
        if name in _ALWAYS or name in create_fields
    }


def browse_url(base_url: str, jira_key: str) -> str:
    return f"{base_url.rstrip('/')}/browse/{jira_key}"
