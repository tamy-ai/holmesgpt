"""The three types added on 2026-10-26: incident, question and technical task.

Each one has a checklist, a label, a Jira issue type, an SLA and a description
section list, like the first five.
"""

from __future__ import annotations

import datetime

import pytest

from tamy.chamados.common import BUSINESS_TZ
from tamy.chamados.checklist import CHECKLISTS, questions_for
from tamy.chamados.classifier import parse_classification
from tamy.chamados.draft import TicketPriority as P
from tamy.chamados.draft import TicketType as T
from tamy.chamados.sla import due_date, resolution_days
from tamy.chamados.ticket_body import ACCEPTANCE_CRITERIA, SECTIONS
from tamy.chamados.vocabulary import JIRA_ISSUE_TYPE, TYPE_LABEL, TYPE_LABEL_SLUG

NEW_TYPES = (T.INCIDENT, T.QUESTION, T.TASK)


def test_the_new_types_have_a_value_a_label_and_a_slug() -> None:
    assert [t.value for t in NEW_TYPES] == ["incident", "question", "task"]
    assert [TYPE_LABEL[t] for t in NEW_TYPES] == [
        "Incidente",
        "Dúvida",
        "Tarefa técnica",
    ]
    assert [TYPE_LABEL_SLUG[t] for t in NEW_TYPES] == [
        "tipo-incidente",
        "tipo-duvida",
        "tipo-tarefa",
    ]


def test_every_type_maps_to_an_issue_type_that_TA_has() -> None:
    assert {JIRA_ISSUE_TYPE[t] for t in T} <= {"Bug", "Task", "Story"}
    assert JIRA_ISSUE_TYPE[T.INCIDENT] == "Bug"


def test_every_type_has_sections_criteria_and_a_checklist() -> None:
    for ticket_type in T:
        assert SECTIONS[ticket_type]
        assert ACCEPTANCE_CRITERIA[ticket_type]
        assert CHECKLISTS[ticket_type]


def test_every_checklist_question_has_a_place_in_the_description() -> None:
    """A question the bot asks and the ticket never shows is an answer thrown away."""
    from tamy.chamados.ticket_body import SHOWN_ELSEWHERE

    for ticket_type in T:
        in_sections = {
            qid for section in SECTIONS[ticket_type] for _, qid in section.items
        }
        asked = {q.id for q in questions_for(ticket_type)}
        assert asked <= in_sections | SHOWN_ELSEWHERE, asked - in_sections


@pytest.mark.parametrize(
    "ticket_type, priority, days",
    [
        (T.INCIDENT, P.P0, 1),
        (T.INCIDENT, P.P1, 1),
        (T.INCIDENT, P.P2, 3),
        (T.QUESTION, P.P1, 1),
        (T.QUESTION, P.P2, 2),
        (T.QUESTION, P.P3, None),
        (T.TASK, P.P1, 5),
        (T.TASK, P.P2, 10),
        (T.TASK, P.P3, None),
    ],
)
def test_the_sla_of_the_new_types(
    ticket_type: T, priority: P, days: int | None
) -> None:
    assert resolution_days(ticket_type, priority) == days


def test_an_incident_is_due_the_next_working_day() -> None:
    friday = datetime.datetime(2026, 10, 23, 15, tzinfo=BUSINESS_TZ)

    assert due_date(T.INCIDENT, P.P0, friday) == datetime.date(2026, 10, 26)


def test_the_classifier_accepts_the_new_types() -> None:
    raw = (
        '{"type": "incident", "priority": "P0", "client": "", '
        '"summary": "Chat fora do ar", "answers": {"incident_impact": "Ninguém conversa"}}'
    )

    draft = parse_classification(raw)

    assert draft.ticket_type is T.INCIDENT
    assert draft.answers == {"incident_impact": "Ninguém conversa"}
