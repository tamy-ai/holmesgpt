"""The resolution SLA of a ticket. One definition of table A.10 (decision 0728).

`docs/produto/pesquisa/2026-10-24-backoffice-operacional/slas-e-integracoes.md`
has the measurements behind each number. "Resolution" is the ticket reaching
"Em produção". None means no due date: P3 goes to the roadmap window, and a
feature gets a roadmap date after triage, not an SLA.
"""

from __future__ import annotations

import datetime

from tamy.chamados.draft import TicketPriority, TicketType
from tamy.chamados.working_days import add_working_days

# P0 is production broken: a hotfix in 1 working day, whatever the type.
_P0_DAYS = 1

_RESOLUTION_DAYS: dict[tuple[TicketType, TicketPriority], int] = {
    (TicketType.BUG, TicketPriority.P1): 3,
    (TicketType.BUG, TicketPriority.P2): 5,
    (TicketType.SUPPORT, TicketPriority.P1): 2,
    (TicketType.SUPPORT, TicketPriority.P2): 3,
    (TicketType.ACCESS, TicketPriority.P1): 1,
    (TicketType.ACCESS, TicketPriority.P2): 2,
    (TicketType.IMPROVEMENT, TicketPriority.P1): 5,
    (TicketType.IMPROVEMENT, TicketPriority.P2): 10,
    # An incident is production hurting a client: next working day even at P1.
    (TicketType.INCIDENT, TicketPriority.P1): 1,
    (TicketType.INCIDENT, TicketPriority.P2): 3,
    (TicketType.QUESTION, TicketPriority.P1): 1,
    (TicketType.QUESTION, TicketPriority.P2): 2,
    (TicketType.TASK, TicketPriority.P1): 5,
    (TicketType.TASK, TicketPriority.P2): 10,
}


def resolution_days(ticket_type: TicketType, priority: TicketPriority) -> int | None:
    if priority is TicketPriority.P0:
        return _P0_DAYS
    return _RESOLUTION_DAYS.get((ticket_type, priority))


def due_date(
    ticket_type: TicketType, priority: TicketPriority, created_at: datetime.datetime
) -> datetime.date | None:
    days = resolution_days(ticket_type, priority)
    return None if days is None else add_working_days(created_at, days)


def sla_label(priority: TicketPriority) -> str:
    return f"sla-{priority.value.lower()}"
