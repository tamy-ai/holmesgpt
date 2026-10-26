"""The words for ticket type and priority. One definition for Slack and Jira.

Priorities follow table A.9 of
docs/produto/pesquisa/2026-10-24-backoffice-operacional/slas-e-integracoes.md.
"""

from __future__ import annotations

import datetime

from tamy.chamados.common import WEEKDAY_NAMES
from tamy.chamados.draft import TicketPriority, TicketType

TYPE_LABEL: dict[TicketType, str] = {
    TicketType.BUG: "Bug",
    TicketType.IMPROVEMENT: "Melhoria",
    TicketType.FEATURE: "Funcionalidade nova",
    TicketType.SUPPORT: "Suporte ou correção de dado",
    TicketType.ACCESS: "Acesso",
    TicketType.INCIDENT: "Incidente",
    TicketType.QUESTION: "Dúvida",
    TicketType.TASK: "Tarefa técnica",
}

PRIORITY_WORDS: dict[TicketPriority, str] = {
    TicketPriority.P0: "produção quebrada",
    TicketPriority.P1: "urgente",
    TicketPriority.P2: "normal",
    TicketPriority.P3: "quando der",
}

# TA has no "Suporte", "Acesso", "Dúvida" or "Tarefa técnica" issue type (A.2): they
# are Tasks with a label. An incident is a Bug: production is broken.
JIRA_ISSUE_TYPE: dict[TicketType, str] = {
    TicketType.BUG: "Bug",
    TicketType.IMPROVEMENT: "Task",
    TicketType.FEATURE: "Story",
    TicketType.SUPPORT: "Task",
    TicketType.ACCESS: "Task",
    TicketType.INCIDENT: "Bug",
    TicketType.QUESTION: "Task",
    TicketType.TASK: "Task",
}

TYPE_LABEL_SLUG: dict[TicketType, str] = {
    TicketType.BUG: "tipo-bug",
    TicketType.IMPROVEMENT: "tipo-melhoria",
    TicketType.FEATURE: "tipo-feature",
    TicketType.SUPPORT: "tipo-suporte",
    TicketType.ACCESS: "tipo-acesso",
    TicketType.INCIDENT: "tipo-incidente",
    TicketType.QUESTION: "tipo-duvida",
    TicketType.TASK: "tipo-tarefa",
}

# Put on a ticket the team reopened from the "Resolveu?" question (TA-1316).
REOPEN_LABEL = "reaberto"
ORIGIN_LABEL = "origem-slack"


def priority_text(priority: TicketPriority) -> str:
    return f"{priority.value} ({PRIORITY_WORDS[priority]})"


def due_text(due_on: datetime.date | None) -> str:
    """The deadline as the team reads it: "prazo qua 29/10", or "sem prazo"."""
    if due_on is None:
        return "sem prazo"
    return f"prazo {WEEKDAY_NAMES[due_on.weekday()][:3]} {due_on:%d/%m}"
