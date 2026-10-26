"""The ticket logic the agent's tool calls. The model picks the fields; the code decides.

`preview` says what would be created and what is missing. `create` writes to Jira only
when the checklist is complete, no ticket exists for the same Slack thread, and no similar
open ticket exists unless the person said it is different. Every rule that is not
"understand the text" lives here: deadline, labels, description, checklist, duplicates.
"""

from __future__ import annotations

import datetime
import json
import re
import threading
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from tamy.chamados.adf_text import adf_to_mrkdwn
from tamy.chamados.checklist import EXTRA_ANSWER_IDS, clean_answers, missing_required
from tamy.chamados.common import backoffice_today
from tamy.chamados.draft import TicketDraft, TicketPriority, TicketType
from tamy.chamados.jira_ticket import (
    TicketRequest,
    build_issue_fields,
    description_of,
    issue_type_name,
    link_label,
)
from tamy.chamados.jira_rest import adf_blocks, adf_heading, adf_paragraph, adf_text
from tamy.chamados.sla import due_date

PROJECT_KEY = "TA"
SIMILAR_WINDOW_DAYS = 60
SIMILAR_WORDS = 4
MIN_WORD_CHARS = 4
MAX_SIMILAR = 5


class Jira(Protocol):
    def search(self, jql: str, **options: Any) -> list[dict[str, Any]]: ...

    def create_issue(self, fields: dict[str, Any]) -> str: ...


@dataclass(frozen=True)
class TicketInput:
    ticket_type: str
    priority: str
    summary: str
    client: str = ""
    answers: Mapping[str, str] = field(default_factory=dict)
    area: str = ""
    channel: str = ""
    thread_ref: str = ""
    requester: str = ""
    thread_url: str = ""
    priority_reason: str = ""
    acceptance: str = ""
    # The person looked at the similar tickets and said this one is different.
    not_a_duplicate: bool = False


@dataclass
class Result:
    ok: bool
    error: str = ""
    missing: list[dict[str, str]] = field(default_factory=list)
    issue_type: str = ""
    priority: str = ""
    due_on: datetime.date | None = None
    labels: list[str] = field(default_factory=list)
    summary: str = ""
    description_preview: str = ""
    key: str = ""
    duplicate_of: str = ""
    similar: list[dict[str, str]] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)


def _draft(item: TicketInput) -> TicketDraft | str:
    try:
        ticket_type = TicketType(item.ticket_type)
        priority = TicketPriority(item.priority)
    except ValueError:
        types = ", ".join(t.value for t in TicketType)
        priorities = ", ".join(p.value for p in TicketPriority)
        return f"Tipo ou prioridade inválido. Tipos: {types}. Prioridades: {priorities}."
    extras = {
        "area": item.area,
        "channel": item.channel,
        "priority_reason": item.priority_reason,
        "acceptance": item.acceptance,
    }
    answers = clean_answers({**dict(item.answers), **{k: v for k, v in extras.items() if v}})
    return TicketDraft(
        ticket_type=ticket_type,
        priority=priority,
        summary=" ".join(item.summary.split()),
        client_hint=item.client or None,
        answers=answers,
    )


def _request(item: TicketInput, draft: TicketDraft, now: datetime.datetime) -> TicketRequest:
    return TicketRequest(
        thread_ref=item.thread_ref or "sem-fio",
        project_key=PROJECT_KEY,
        draft=draft,
        requester_name=item.requester or None,
        thread_url=item.thread_url or None,
        due_on=due_date(draft.ticket_type, draft.priority, now),
        requested_on=now.date(),
    )


def preview(item: TicketInput, *, now: datetime.datetime | None = None) -> Result:
    """What would be created, and what is missing. Writes nothing."""
    now = now or datetime.datetime.combine(backoffice_today(), datetime.time(12, 0)).astimezone()
    draft = _draft(item)
    if isinstance(draft, str):
        return Result(ok=False, error=draft)
    missing = [
        {"id": q.id, "question": q.text}
        for q in missing_required(draft.ticket_type, draft.answers)
    ]
    request = _request(item, draft, now)
    fields = build_issue_fields(request, frozenset({"labels", "description", "duedate"}))
    return Result(
        ok=not missing,
        error="Faltam respostas obrigatórias." if missing else "",
        missing=missing,
        issue_type=issue_type_name(request),
        priority=draft.priority.value,
        due_on=request.due_on,
        labels=list(fields["labels"]),  # type: ignore[arg-type]
        summary=str(fields["summary"]),
        description_preview=adf_to_mrkdwn(description_of(request)),
    )


_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)


def similar(summary: str, jira: Jira) -> list[dict[str, str]]:
    """Open tickets of the last 60 days whose text shares the title's main words. The
    words are cleaned to letters and digits: a title can never add a clause to the query."""
    words = [w for w in _NON_WORD.sub(" ", summary).split() if len(w) >= MIN_WORD_CHARS]
    words = words[:SIMILAR_WORDS]
    if not words:
        return []
    jql = (
        f"project = {PROJECT_KEY} AND created >= -{SIMILAR_WINDOW_DAYS}d "
        f"AND statusCategory != Done AND text ~ \"{' '.join(words)}\" ORDER BY created DESC"
    )
    found = jira.search(jql, fields=("summary", "status"), max_pages=1)
    return [
        {
            "key": str(issue.get("key", "")),
            "summary": str((issue.get("fields") or {}).get("summary", "")),
        }
        for issue in found[:MAX_SIMILAR]
    ]


# What this process created, by Slack thread. Jira's search takes seconds to see a new
# ticket (seen live on 26/10/2026: a second call created a duplicate), so the thread label
# alone cannot be the only guard. The lock makes two simultaneous creates one.
_created: dict[str, str] = {}
_in_flight: set[str] = set()
_guard = threading.Lock()


def forget_created() -> None:
    with _guard:
        _created.clear()
        _in_flight.clear()


def _refuse_duplicate(result: Result, key: str) -> Result:
    result.ok = False
    result.duplicate_of = key
    result.error = f"Já existe o chamado {key} para este fio. Não criei outro."
    return result


def create(item: TicketInput, jira: Jira, *, now: datetime.datetime | None = None) -> Result:
    """Create the ticket, or say why not. Idempotent per Slack thread."""
    result = preview(item, now=now)
    if not result.ok:
        return result
    ref = item.thread_ref
    if ref:
        with _guard:
            if ref in _created:
                return _refuse_duplicate(result, _created[ref])
            if ref in _in_flight:
                return _refuse_duplicate(result, "em criação")
            _in_flight.add(ref)
    try:
        created = _create_checked(item, jira, result, now)
        if created.key and ref:
            with _guard:
                _created[ref] = created.key
        return created
    finally:
        if ref:
            with _guard:
                _in_flight.discard(ref)


def _create_checked(
    item: TicketInput, jira: Jira, result: Result, now: datetime.datetime | None
) -> Result:
    if item.thread_ref:
        same = jira.search(
            f"project = {PROJECT_KEY} AND labels = {link_label(item.thread_ref)}",
            fields=("summary",),
            max_pages=1,
        )
        if same:
            return _refuse_duplicate(result, str(same[0].get("key", "")))
    if not item.not_a_duplicate:
        near = similar(item.summary, jira)
        if near:
            result.ok = False
            result.similar = near
            result.error = (
                "Há chamados abertos parecidos. Mostre à pessoa e pergunte se é o mesmo "
                "problema. Se for diferente, chame de novo com not_a_duplicate=true."
            )
            return result
    draft = _draft(item)
    assert isinstance(draft, TicketDraft)
    request = _request(item, draft, now or datetime.datetime.now().astimezone())
    create_fields = getattr(jira, "create_fields", None)
    allowed = (
        create_fields(PROJECT_KEY, issue_type_name(request))
        if callable(create_fields)
        else frozenset({"labels", "description", "duedate"})
    )
    result.key = jira.create_issue(build_issue_fields(request, allowed))
    return result


_TICKET_KEY = re.compile(rf"^{PROJECT_KEY}-\d+$")
BOT_ORIGIN_LABEL = "origem-slack"
MAX_COMMENT_CHARS = 20000


class CommentJira(Protocol):
    def issue_labels(self, key: str) -> list[str]: ...

    def add_comment(self, key: str, body: dict[str, Any]) -> None: ...


def _comment_doc(text: str) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    for chunk in re.split(r"\n\s*\n", text.strip()):
        for line in chunk.splitlines():
            if not line.strip():
                continue
            heading = re.match(r"^h([1-6])\.\s*(.*)$", line.strip())
            if heading:
                blocks.append(adf_heading(heading.group(2), int(heading.group(1))))
            else:
                blocks.append(adf_paragraph([adf_text(line.strip())]))
    return adf_blocks(blocks)


def comment_investigation(key: str, text: str, jira: CommentJira) -> Result:
    """Adds the investigation to a ticket this bot opened. Never touches another ticket."""
    if not _TICKET_KEY.match(key):
        return Result(ok=False, error=f"A chave {key!r} não é de um chamado do projeto {PROJECT_KEY}.")
    if not text.strip():
        return Result(ok=False, error="O comentário está vazio.")
    if BOT_ORIGIN_LABEL not in jira.issue_labels(key):
        return Result(ok=False, error=f"{key} não foi aberto por este bot. Não comento em chamado alheio.")
    jira.add_comment(key, _comment_doc(text[:MAX_COMMENT_CHARS]))
    return Result(ok=True, key=key)


# Answer ids the model may send beyond the checklist of the type.
ALLOWED_EXTRA = EXTRA_ANSWER_IDS
