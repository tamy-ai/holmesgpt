"""The checklist of each ticket type, from B.1 of
`docs/produto/pesquisa/2026-10-24-backoffice-operacional/slas-e-integracoes.md`.

The bot asks only what is missing. The first `REQUIRED_COUNT` questions of a
type must have an answer before "Criar chamado" appears; the others go to Jira
as "não informado". Question ids are unique across types, so the answers of a
previous type stay stored and never answer another type's question.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from tamy.chamados.common import find_email, find_emails
from tamy.chamados.draft import TicketType

REQUIRED_COUNT = 3
MAX_ANSWER_CHARS = 1000
# Five criteria of up to 250 characters, one per line.
MAX_ACCEPTANCE_CHARS = 1500
NOT_INFORMED = "não informado"


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    required: bool
    # The answer names the client: only these can identify who the ticket is
    # about ("who asked" and "who approves" name the team or a manager).
    names_client: bool = False


_CLIENT_QUESTION_IDS = frozenset(
    {"bug_client", "support_client", "access_person", "access_org"}
)

# What the classifier writes about the draft beside the answers: the criteria, the
# reason of the priority, the channel and the area (`areas.py`). They fill the
# description and the labels, and no question asks for them, so the answers modal
# never shows them.
EXTRA_ANSWER_IDS = frozenset({"acceptance", "priority_reason", "channel", "area"})


def _checklist(
    *items: tuple[str, str], required: int = REQUIRED_COUNT
) -> tuple[Question, ...]:
    return tuple(
        Question(
            id=qid,
            text=text,
            required=index < required,
            names_client=qid in _CLIENT_QUESTION_IDS,
        )
        for index, (qid, text) in enumerate(items)
    )


CHECKLISTS: dict[TicketType, tuple[Question, ...]] = {
    TicketType.BUG: _checklist(
        ("bug_client", "Qual cliente (organização, loja ou e-mail)?"),
        ("bug_steps", "O que a pessoa fez, passo a passo?"),
        ("bug_expected", "O que esperava?"),
        ("bug_actual", "O que aconteceu?"),
        ("bug_when", "Quando (dia e hora)?"),
        ("bug_reach", "Afeta só ela ou mais clientes?"),
        ("bug_users", "Quais usuários foram afetados (e-mails)?"),
        ("bug_workaround", "Tem contorno?"),
        ("bug_evidence", "Tem print ou vídeo?"),
        ("bug_channel", "Canal: web, celular ou WhatsApp?"),
        required=4,
    ),
    TicketType.IMPROVEMENT: _checklist(
        ("improvement_screen", "Qual tela ou fluxo?"),
        ("improvement_pain", "O que incomoda hoje?"),
        ("improvement_wish", "Como deveria ser?"),
        ("improvement_who", "Quem pediu e quantos clientes?"),
        ("improvement_users", "Quais usuários pediram (e-mails)?"),
        ("improvement_cost", "Qual o custo de não fazer (tempo, dinheiro, churn)?"),
        ("improvement_evidence", "Tem print?"),
    ),
    TicketType.FEATURE: _checklist(
        ("feature_problem", "Qual problema do dono de loja resolve?"),
        ("feature_who", "Quem pediu (clientes, vendas, CS)?"),
        ("feature_today", "Como a pessoa resolve hoje?"),
        ("feature_users", "Quais usuários pediram (e-mails)?"),
        ("feature_deadline", "Tem prazo de negócio (contrato, evento)?"),
        ("feature_success", "Como saber que deu certo?"),
    ),
    TicketType.SUPPORT: _checklist(
        ("support_client", "Qual cliente e loja?"),
        (
            "support_data",
            "Qual dado está errado (venda, nota, estoque, despesa) e de qual dia?",
        ),
        (
            "support_values",
            "Valor que aparece e valor certo, com a fonte (PDV, nota, extrato)?",
        ),
        ("support_touched", "O cliente já mexeu nesse dado?"),
        ("support_how", "Pode corrigir pelo Backoffice ou precisa de script?"),
        ("support_users", "Quais usuários foram afetados (e-mails)?"),
    ),
    TicketType.ACCESS: _checklist(
        ("access_person", "E-mail e nome da pessoa."),
        ("access_org", "Organização."),
        (
            "access_need",
            "O que falta: login, convite, perfil, loja, recuperação de senha?",
        ),
        ("access_approver", "Quem autoriza (dono da organização)?"),
        ("access_until", "Até quando?"),
        required=4,
    ),
    TicketType.INCIDENT: _checklist(
        (
            "incident_impact",
            "O que está fora do ar ou errado, e quem não consegue usar?",
        ),
        ("incident_since", "Desde quando (dia e hora)?"),
        ("incident_reach", "Quantos clientes ou lojas?"),
        (
            "incident_data",
            "Há dado errado sendo salvo, ou dado de um cliente à mostra para outro?",
        ),
        ("incident_users", "Quais usuários foram afetados (e-mails)?"),
        ("incident_workaround", "Tem contorno?"),
        ("incident_evidence", "Tem print, vídeo ou link de log?"),
    ),
    TicketType.QUESTION: _checklist(
        ("question_ask", "Qual é a dúvida?"),
        ("question_who", "Quem pergunta, e sobre qual cliente ou tela?"),
        ("question_deadline", "Para quando precisa da resposta?"),
        required=2,
    ),
    TicketType.TASK: _checklist(
        ("task_goal", "Qual é o objetivo da tarefa?"),
        ("task_why", "Por que agora? O que acontece se ficar para depois?"),
        ("task_done", "Como saber que acabou?"),
        ("task_scope", "O que fica de fora?"),
        ("task_deadline", "Tem prazo?"),
    ),
}

# The question that names the users hurt by the problem, or who asked for the change.
# The e-mails go to the description, and the delivery notice reaches them.
USER_QUESTION_IDS: dict[TicketType, str] = {
    TicketType.BUG: "bug_users",
    TicketType.INCIDENT: "incident_users",
    TicketType.SUPPORT: "support_users",
    TicketType.IMPROVEMENT: "improvement_users",
    TicketType.FEATURE: "feature_users",
}

_KNOWN_IDS = EXTRA_ANSWER_IDS | frozenset(
    q.id for questions in CHECKLISTS.values() for q in questions
)


def questions_for(ticket_type: TicketType) -> tuple[Question, ...]:
    return CHECKLISTS[ticket_type]


def _tidy(text: str) -> str:
    """Single spaces inside each line, no blank lines: a step by step keeps its lines."""
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def clean_answers(raw: object) -> dict[str, str]:
    """Known question ids with non-blank text, capped. Anything else, including
    a value that is not a JSON object, is dropped."""
    items = cast(dict[object, object], raw).items() if isinstance(raw, dict) else ()
    return {
        qid: _tidy(value)[
            : MAX_ACCEPTANCE_CHARS if qid == "acceptance" else MAX_ANSWER_CHARS
        ]
        for qid, value in items
        if isinstance(qid, str)
        and qid in _KNOWN_IDS
        and isinstance(value, str)
        and value.strip()
    }


def is_answered(answers: Mapping[str, str], question_id: str) -> bool:
    return bool(answers.get(question_id, "").strip())


def answers_of_type(
    ticket_type: TicketType, answers: Mapping[str, str]
) -> dict[str, str]:
    ids = {q.id for q in questions_for(ticket_type)} | EXTRA_ANSWER_IDS
    return {qid: text for qid, text in answers.items() if qid in ids}


def answers_from(ticket_type: TicketType, raw: object) -> dict[str, str]:
    """The answers a model returned, cleaned and kept to one type."""
    return answers_of_type(ticket_type, clean_answers(raw))


def client_email(ticket_type: TicketType, answers: Mapping[str, str]) -> str | None:
    """The e-mail the client question of this type names, if any."""
    for question in questions_for(ticket_type):
        if question.names_client:
            email = find_email(answers.get(question.id, ""))
            if email:
                return email
    return None


def affected_emails(ticket_type: TicketType, answers: Mapping[str, str]) -> list[str]:
    """The e-mails the users question of this type holds, once each, in order."""
    question_id = USER_QUESTION_IDS.get(ticket_type)
    return find_emails(answers.get(question_id, "")) if question_id else []


def missing_required(
    ticket_type: TicketType, answers: Mapping[str, str]
) -> list[Question]:
    return [
        q
        for q in questions_for(ticket_type)
        if q.required and not is_answered(answers, q.id)
    ]


def missing_optional(
    ticket_type: TicketType, answers: Mapping[str, str]
) -> list[Question]:
    return [
        q
        for q in questions_for(ticket_type)
        if not q.required and not is_answered(answers, q.id)
    ]


def has_open_questions(ticket_type: TicketType, answers: Mapping[str, str]) -> bool:
    return any(not is_answered(answers, q.id) for q in questions_for(ticket_type))


def missing_text(questions: list[Question]) -> str:
    """The questions as a numbered list, one per line."""
    return "\n".join(f"{i}. {q.text}" for i, q in enumerate(questions, start=1))


def answered(
    ticket_type: TicketType, answers: Mapping[str, str]
) -> list[tuple[Question, str]]:
    """Every question of the type with its answer, or "não informado"."""
    return [
        (q, answers.get(q.id, "").strip() or NOT_INFORMED)
        for q in questions_for(ticket_type)
    ]
