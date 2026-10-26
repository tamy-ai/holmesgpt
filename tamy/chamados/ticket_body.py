"""The Jira description of a ticket born in Slack.

Written for a reader who was not in the thread and has ten minutes: the problem, the
context, the facts of the type (steps, expected and obtained, the story), the
acceptance criteria as Given/When/Then, and what is still unknown. Researched on
2026-10-25 against Atlassian's INVEST and Given/When/Then guidance and New Relic's
ticket practice.

The answers are data. They go into text nodes with no marks, so a line of markup in an
answer stays literal characters. A question nobody answered is listed once under
"Perguntas em aberto" instead of "não informado" in each section, and a ticket with no
open question has no such section.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from tamy.chamados.common import WEEKDAY_NAMES
from tamy.chamados.jira_rest import (
    AdfNode,
    adf_blocks,
    adf_bullets,
    adf_heading,
    adf_link,
    adf_ordered,
    adf_paragraph,
    adf_text,
)
from tamy.chamados.areas import (
    area_by_slug,
    area_label,
    channel_label,
    clean_channel,
)
from tamy.chamados.checklist import (
    USER_QUESTION_IDS,
    affected_emails,
    questions_for,
)
from tamy.chamados.draft import TicketDraft, TicketType
from tamy.chamados.vocabulary import TYPE_LABEL, due_text, priority_text

UNKNOWN_REQUESTER = "solicitante não identificado"

SectionKind = Literal["facts", "steps", "text"]

_BULLET_MARKS = "-*\u2022"


def _strip_list_mark(line: str) -> str:
    """ "1. step", "2) step", "- step" -> "step": the list numbers the steps itself."""
    digits = len(line) - len(line.lstrip("0123456789"))
    if digits and line[digits : digits + 1] in (".", ")"):
        return line[digits + 1 :].strip()
    if line[:1] in _BULLET_MARKS:
        return line[1:].strip()
    return line


@dataclass(frozen=True)
class Section:
    heading: str
    kind: SectionKind
    # (label, question id). The label only matters to a "facts" section.
    items: tuple[tuple[str, str], ...]


def _text(heading: str, question_id: str) -> Section:
    return Section(heading, "text", (("", question_id),))


SECTIONS: dict[TicketType, tuple[Section, ...]] = {
    TicketType.BUG: (
        Section(
            "Impacto",
            "facts",
            (
                ("Alcance", "bug_reach"),
                ("Quando", "bug_when"),
                ("Canal", "bug_channel"),
            ),
        ),
        Section("Passos para reproduzir", "steps", (("", "bug_steps"),)),
        _text("Esperado", "bug_expected"),
        _text("Obtido", "bug_actual"),
        _text("Contorno", "bug_workaround"),
    ),
    TicketType.IMPROVEMENT: (
        _text("Tela ou fluxo", "improvement_screen"),
        _text("Problema hoje", "improvement_pain"),
        _text("Como deveria ser", "improvement_wish"),
        _text("Quem pediu e alcance", "improvement_who"),
        _text("Custo de não fazer", "improvement_cost"),
    ),
    TicketType.FEATURE: (
        _text("Como o dono resolve hoje", "feature_today"),
        _text("Quem pediu", "feature_who"),
        _text("Prazo de negócio", "feature_deadline"),
    ),
    TicketType.SUPPORT: (
        _text("Dado errado", "support_data"),
        _text("Valores e fonte", "support_values"),
        _text("O cliente já mexeu?", "support_touched"),
        _text("Como corrigir", "support_how"),
    ),
    TicketType.ACCESS: (
        Section(
            "Pedido de acesso",
            "facts",
            (
                ("Pessoa", "access_person"),
                ("Organização", "access_org"),
                ("O que falta", "access_need"),
                ("Quem autoriza", "access_approver"),
                ("Até quando", "access_until"),
            ),
        ),
    ),
    TicketType.INCIDENT: (
        _text("O que está acontecendo", "incident_impact"),
        Section(
            "Impacto",
            "facts",
            (
                ("Desde", "incident_since"),
                ("Alcance", "incident_reach"),
                ("Risco para o dado", "incident_data"),
            ),
        ),
        _text("Contorno", "incident_workaround"),
    ),
    TicketType.QUESTION: (
        _text("Dúvida", "question_ask"),
        _text("Quem pergunta", "question_who"),
        _text("Prazo da resposta", "question_deadline"),
    ),
    TicketType.TASK: (
        _text("Objetivo", "task_goal"),
        _text("Por que agora", "task_why"),
        _text("Como saber que acabou", "task_done"),
        _text("Fora do escopo", "task_scope"),
        _text("Prazo", "task_deadline"),
    ),
}

# Asked in the checklist and shown by a part of the description that is not a
# section of the type: the client in the context, the files and the users in
# their own sections, the problem and the success in the user story.
EVIDENCE_QUESTION_IDS = frozenset(
    {"bug_evidence", "improvement_evidence", "incident_evidence"}
)
SHOWN_ELSEWHERE = (
    frozenset({"bug_client", "support_client", "feature_problem", "feature_success"})
    | EVIDENCE_QUESTION_IDS
    | frozenset(USER_QUESTION_IDS.values())
)

# The heading of the users: who was hurt, or who asked for the change.
_USERS_HEADING: dict[TicketType, str] = {
    TicketType.IMPROVEMENT: "Usuários que pediram",
    TicketType.FEATURE: "Usuários que pediram",
}
_DEFAULT_USERS_HEADING = "Usuários afetados"

# Given/When/Then where the type has a scenario, plain outcomes where it does not. Each
# line is testable by a person who was not in the thread.
ACCEPTANCE_CRITERIA: dict[TicketType, tuple[str, ...]] = {
    TicketType.BUG: (
        "Dado o cenário dos passos acima, quando a pessoa repetir os passos, "
        "então o resultado é o esperado.",
        "Dado o conserto publicado, quando o cliente afetado usar de novo, "
        "então ele confirma que voltou ao normal.",
        "Existe um teste automatizado que falha sem o conserto e passa com ele.",
    ),
    TicketType.IMPROVEMENT: (
        "Dado o fluxo descrito, quando a pessoa o usar, "
        "então ele funciona como pedido em «Como deveria ser».",
        "O problema de «Problema hoje» deixa de acontecer, e quem pediu confirma.",
        "Existe um teste automatizado do novo comportamento.",
    ),
    TicketType.FEATURE: (
        "Dado o problema da história, quando o dono de loja usar a funcionalidade, "
        "então ele o resolve sem pedir ajuda.",
        "O sucesso é medido como a história descreve, e o número fica registrado.",
        "Existe um teste automatizado do fluxo principal e dos casos de borda.",
    ),
    TicketType.SUPPORT: (
        "O dado corrigido bate com a fonte informada (PDV, nota ou extrato).",
        "O cliente vê o valor certo no painel e confirma.",
        "A correção deixa registro de quem fez e por quê.",
    ),
    TicketType.ACCESS: (
        "A pessoa entra e vê só o que o perfil permite.",
        "Quem autorizou o acesso fica registrado no chamado.",
        "O acesso termina na data combinada, quando houver data.",
    ),
    TicketType.INCIDENT: (
        "Dado o cenário descrito, quando o conserto for publicado, "
        "então o Tamy volta a funcionar para todos os clientes afetados.",
        "Os usuários afetados são avisados de que voltou.",
        "A causa e o que evita a repetição ficam registrados no chamado.",
    ),
    TicketType.QUESTION: (
        "A dúvida recebe uma resposta escrita no fio do Slack.",
        "Quem perguntou confirma que entendeu.",
        "Se a resposta mostrar um problema, o chamado vira Bug ou Melhoria.",
    ),
    TicketType.TASK: (
        "O objetivo está cumprido como descrito em «Como saber que acabou».",
        "O que ficou fora do escopo está registrado.",
        "Existe um teste ou uma conferência que prova o resultado.",
    ),
}


def _lines(answer: str) -> list[str]:
    return [line.strip() for line in answer.splitlines() if line.strip()]


def _paragraphs(answer: str) -> list[AdfNode]:
    return [adf_paragraph([adf_text(line)]) for line in _lines(answer)]


def _section_blocks(section: Section, answers: dict[str, str]) -> list[AdfNode]:
    answered = [
        (label, answers[qid]) for label, qid in section.items if answers.get(qid)
    ]
    if not answered:
        return []
    heading = adf_heading(section.heading)
    if section.kind == "facts":
        facts = [
            [adf_text(f"{label}: {' '.join(_lines(text))}")] for label, text in answered
        ]
        return [heading, adf_bullets(facts)]
    text = answered[0][1]
    if section.kind == "steps":
        steps = [_strip_list_mark(line) for line in _lines(text)]
        return [heading, adf_ordered([[adf_text(step)] for step in steps if step])]
    return [heading, *_paragraphs(text)]


def _story(draft: TicketDraft) -> list[AdfNode]:
    """ "Como dono de loja, quero ..., para ...": only the clauses the thread gave."""
    problem = draft.answers.get("feature_problem", "").strip()
    success = draft.answers.get("feature_success", "").strip()
    if not problem and not success:
        return []
    parts = ["Como dono de loja"]
    if problem:
        parts.append(f"quero resolver este problema: {' '.join(_lines(problem))}")
    if success:
        parts.append(
            f"para que o sucesso seja medido assim: {' '.join(_lines(success))}"
        )
    return [
        adf_heading("História do usuário"),
        adf_paragraph([adf_text(", ".join(parts) + ".")]),
    ]


def _requested_text(requested_on: datetime.date) -> str:
    return f"{WEEKDAY_NAMES[requested_on.weekday()][:3]} {requested_on:%d/%m/%Y}"


def _client_text(draft: TicketDraft) -> str:
    """The client as the thread gave it in full, else the short name."""
    for question in questions_for(draft.ticket_type):
        answer = draft.answers.get(question.id, "").strip()
        if question.names_client and answer:
            return " ".join(answer.split())
    return draft.client_hint or "não informado"


def _context(
    draft: TicketDraft,
    requester_name: str | None,
    thread_url: str | None,
    due_on: datetime.date | None,
    requested_on: datetime.date | None,
) -> list[AdfNode]:
    facts: list[Sequence[AdfNode]] = [
        [adf_text(f"Tipo: {TYPE_LABEL[draft.ticket_type]}")],
        [adf_text(f"Prioridade: {priority_text(draft.priority)}, {due_text(due_on)}")],
    ]
    reason = " ".join(draft.answers.get("priority_reason", "").split())
    if reason:
        facts.append([adf_text(f"Motivo da prioridade: {reason}")])
    facts.append([adf_text(f"Cliente: {_client_text(draft)}")])
    channel = clean_channel(draft.answers.get("channel"))
    if channel is not None:
        facts.append([adf_text(f"Canal: {channel_label(channel)}")])
    area = area_by_slug(draft.answers.get("area", ""))
    if area is not None:
        facts.append([adf_text(f"Área: {area_label(area.slug)}")])
    if requested_on is not None:
        # "ontem" in the thread means nothing a day later: the date anchors it.
        facts.append([adf_text(f"Pedido em: {_requested_text(requested_on)}")])
    facts.append([adf_text(f"Pedido por: {requester_name or UNKNOWN_REQUESTER}")])
    facts.append(
        [adf_link("Fio no Slack", thread_url)]
        if thread_url
        else [adf_text("O link do fio no Slack não foi obtido.")]
    )
    return [adf_heading("Contexto"), adf_bullets(facts)]


def _where_to_look(draft: TicketDraft) -> list[AdfNode]:
    """The code of the area: the first files a developer opens. A hint, not a
    diagnosis; the person who reads it checks."""
    area = area_by_slug(draft.answers.get("area", ""))
    if area is None or not area.code_paths:
        return []
    return [
        adf_heading("Onde olhar primeiro"),
        adf_bullets([[adf_text(path)] for path in area.code_paths]),
    ]


def _users(draft: TicketDraft) -> list[AdfNode]:
    emails = affected_emails(draft.ticket_type, draft.answers)
    if not emails:
        return []
    heading = _USERS_HEADING.get(draft.ticket_type, _DEFAULT_USERS_HEADING)
    return [adf_heading(heading), adf_bullets([[adf_text(email)] for email in emails])]


def _evidence(draft: TicketDraft, file_count: int) -> list[AdfNode]:
    """The files of the thread, counted. The answer of the person can hold a file
    name, and decision 0667 keeps client text out of Jira, so it is not repeated."""
    asks_for_files = any(
        q.id in EVIDENCE_QUESTION_IDS for q in questions_for(draft.ticket_type)
    )
    if not file_count and not asks_for_files:
        return []
    if not file_count:
        text = "Nenhum arquivo no fio."
    else:
        unit = "arquivo" if file_count == 1 else "arquivos"
        text = (
            f"{file_count} {unit} no fio do Slack. Prints e vídeos ficam anexados "
            "ao chamado; os outros têm o link no primeiro comentário (abre com o "
            "login do Slack)."
        )
    return [adf_heading("Evidências"), adf_paragraph([adf_text(text)])]


def _criteria(draft: TicketDraft) -> list[AdfNode]:
    written = [
        _strip_list_mark(line) for line in _lines(draft.answers.get("acceptance", ""))
    ]
    lines = [line for line in written if line] or list(
        ACCEPTANCE_CRITERIA[draft.ticket_type]
    )
    return [
        adf_heading("Critérios de aceite"),
        adf_bullets([[adf_text(line)] for line in lines]),
    ]


def _open_questions(draft: TicketDraft, file_count: int) -> list[AdfNode]:
    missing = [
        [adf_text(question.text)]
        for question in questions_for(draft.ticket_type)
        if not draft.answers.get(question.id, "").strip()
        # The files are counted from the thread: asking for them again is noise.
        and not (file_count and question.id in EVIDENCE_QUESTION_IDS)
    ]
    return [adf_heading("Perguntas em aberto"), adf_bullets(missing)] if missing else []


def build_description(
    draft: TicketDraft,
    *,
    requester_name: str | None,
    thread_url: str | None,
    due_on: datetime.date | None,
    requested_on: datetime.date | None = None,
    thread_file_count: int = 0,
) -> AdfNode:
    answers = dict(draft.answers)
    blocks: list[AdfNode] = [
        adf_heading("Resumo"),
        adf_paragraph([adf_text(draft.summary)]),
        *_context(draft, requester_name, thread_url, due_on, requested_on),
    ]
    if draft.ticket_type is TicketType.FEATURE:
        blocks.extend(_story(draft))
    for section in SECTIONS[draft.ticket_type]:
        blocks.extend(_section_blocks(section, answers))
    blocks.extend(_users(draft))
    blocks.extend(_where_to_look(draft))
    blocks.extend(_evidence(draft, thread_file_count))
    blocks.extend(_criteria(draft))
    blocks.extend(_open_questions(draft, thread_file_count))
    return adf_blocks(blocks)
