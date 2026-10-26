"""The checklist per ticket type (B.1): only the missing questions are asked,
and the first three are required before the ticket can be created."""

from __future__ import annotations

from tamy.chamados.checklist import (
    CHECKLISTS,
    NOT_INFORMED,
    REQUIRED_COUNT,
    answered,
    clean_answers,
    missing_required,
    questions_for,
)
from tamy.chamados.draft import TicketType


def test_every_type_has_a_checklist_of_at_least_three_questions() -> None:
    assert set(CHECKLISTS) == set(TicketType)
    assert all(len(questions) >= REQUIRED_COUNT for questions in CHECKLISTS.values())


def test_question_ids_are_unique_across_types() -> None:
    """Answers of the old type stay stored when the type changes; an id shared
    by two types would carry an answer to the wrong question."""
    ids = [q.id for questions in CHECKLISTS.values() for q in questions]

    assert len(ids) == len(set(ids))


def test_bug_checklist_follows_b1() -> None:
    texts = [q.text for q in questions_for(TicketType.BUG)]

    assert texts[0].startswith("Qual cliente")
    # Expected and obtained are two questions: two facts, two lines in Jira.
    assert texts[2:4] == ["O que esperava?", "O que aconteceu?"]
    assert len(texts) == 10


def test_most_types_require_their_first_three_questions() -> None:
    for ticket_type in (
        TicketType.IMPROVEMENT,
        TicketType.FEATURE,
        TicketType.SUPPORT,
        TicketType.INCIDENT,
        TicketType.TASK,
    ):
        required = [q.required for q in questions_for(ticket_type)]
        assert required[:3] == [True] * 3 and not any(required[3:])


def test_a_bug_also_requires_what_happened() -> None:
    required = [q.id for q in questions_for(TicketType.BUG) if q.required]

    assert required == ["bug_client", "bug_steps", "bug_expected", "bug_actual"]


def test_an_access_request_requires_who_approves_it() -> None:
    """A login given with no name behind it is a hole: the approver is required."""
    required = [q.id for q in questions_for(TicketType.ACCESS) if q.required]

    assert required == [
        "access_person",
        "access_org",
        "access_need",
        "access_approver",
    ]


def test_a_question_only_needs_the_question_and_who_asks() -> None:
    required = [q.id for q in questions_for(TicketType.QUESTION) if q.required]

    assert required == ["question_ask", "question_who"]


def test_missing_required_lists_only_what_has_no_answer() -> None:
    bug = questions_for(TicketType.BUG)
    answers = {bug[0].id: "Martita", bug[2].id: "  "}

    missing = missing_required(TicketType.BUG, answers)

    assert [q.id for q in missing] == [bug[1].id, bug[2].id, bug[3].id]


def test_complete_when_every_required_question_has_an_answer() -> None:
    bug = questions_for(TicketType.BUG)
    answers = {q.id: "x" for q in bug if q.required}

    assert missing_required(TicketType.BUG, answers) == []


def test_answered_marks_the_rest_as_not_informed() -> None:
    feature = questions_for(TicketType.FEATURE)

    pairs = answered(TicketType.FEATURE, {feature[0].id: "Fechamento mais rápido"})

    assert pairs[0] == (feature[0], "Fechamento mais rápido")
    assert all(text == NOT_INFORMED for _, text in pairs[1:])


def test_clean_answers_drops_unknown_ids_and_blank_text() -> None:
    bug = questions_for(TicketType.BUG)

    cleaned = clean_answers(
        {bug[0].id: " Martita ", "drop_table": "x", bug[1].id: "", "bug_when": 3}
    )

    assert cleaned == {bug[0].id: "Martita"}


def test_clean_answers_caps_the_length() -> None:
    bug = questions_for(TicketType.BUG)

    cleaned = clean_answers({bug[1].id: "a" * 5000})

    assert len(cleaned[bug[1].id]) <= 1000


def test_answers_of_type_keeps_only_that_type() -> None:
    from tamy.chamados.checklist import answers_of_type

    answers = {"bug_client": "a", "access_org": "b"}

    assert answers_of_type(TicketType.ACCESS, answers) == {"access_org": "b"}


def test_missing_optional_skips_answered_and_required() -> None:
    from tamy.chamados.checklist import missing_optional

    bug = questions_for(TicketType.BUG)
    answers = {bug[4].id: "ontem"}

    assert [q.id for q in missing_optional(TicketType.BUG, answers)] == [
        q.id for q in bug[5:]
    ]


def test_is_answered_ignores_blank_text() -> None:
    from tamy.chamados.checklist import is_answered

    assert is_answered({"bug_client": "x"}, "bug_client")
    assert not is_answered({"bug_client": "  "}, "bug_client")
    assert not is_answered({}, "bug_client")


def test_missing_text_numbers_the_questions() -> None:
    from tamy.chamados.checklist import missing_text

    bug = questions_for(TicketType.BUG)

    assert missing_text(list(bug[:2])) == f"1. {bug[0].text}\n2. {bug[1].text}"


def test_clean_answers_keeps_the_lines_of_a_step_by_step() -> None:
    bug = questions_for(TicketType.BUG)

    cleaned = clean_answers(
        {bug[1].id: "1. abriu   o Painel\n\n2. clicou em Notas  \n"}
    )

    assert cleaned[bug[1].id] == "1. abriu o Painel\n2. clicou em Notas"


def test_answers_from_cleans_and_keeps_only_the_type() -> None:
    from tamy.chamados.checklist import answers_from

    raw = {"access_org": " Martita ", "bug_client": "x", "access_person": "  "}

    assert answers_from(TicketType.ACCESS, raw) == {"access_org": "Martita"}
    assert answers_from(TicketType.ACCESS, ["not a dict"]) == {}


def test_has_open_questions() -> None:
    from tamy.chamados.checklist import has_open_questions

    every = {q.id: "x" for q in questions_for(TicketType.FEATURE)}

    assert has_open_questions(TicketType.FEATURE, {})
    assert not has_open_questions(TicketType.FEATURE, every)


def test_the_client_email_comes_only_from_the_client_question_of_the_type() -> None:
    from tamy.chamados.checklist import client_email

    answers = {
        "bug_steps": "tentou convidar ana@x.com",
        "improvement_who": "pedido da cs@tamy.ai",
        "bug_client": "Martita, dono@martita.com.br",
    }

    assert client_email(TicketType.BUG, answers) == "dono@martita.com.br"


def test_no_client_email_when_the_client_question_has_none() -> None:
    from tamy.chamados.checklist import client_email

    answers = {"bug_client": "Martita", "bug_steps": "ana@x.com"}

    assert client_email(TicketType.BUG, answers) is None


def test_client_questions_are_the_ones_that_name_a_client() -> None:
    named = {q.id for qs in CHECKLISTS.values() for q in qs if q.names_client}

    assert named == {"bug_client", "support_client", "access_person", "access_org"}


def test_the_classifier_notes_are_kept_but_never_asked() -> None:
    """The acceptance criteria and the reason of the priority come from the thread
    with the classifier. They fill the description; no question asks for them."""
    from tamy.chamados.checklist import EXTRA_ANSWER_IDS, answers_from

    raw = {
        "acceptance": "Dado X, quando Y, então Z",
        "priority_reason": "Bloqueia a loja",
    }

    assert answers_from(TicketType.BUG, raw) == raw
    assert not {q.id for qs in CHECKLISTS.values() for q in qs} & EXTRA_ANSWER_IDS


def test_the_modal_never_drops_the_classifier_notes() -> None:
    from tamy.chamados.checklist import answers_of_type

    answers = {"bug_client": "a", "acceptance": "Dado X", "access_org": "b"}

    assert answers_of_type(TicketType.BUG, answers) == {
        "bug_client": "a",
        "acceptance": "Dado X",
    }


def test_the_users_question_exists_where_a_user_is_affected_or_asked() -> None:
    from tamy.chamados.checklist import USER_QUESTION_IDS

    assert USER_QUESTION_IDS == {
        TicketType.BUG: "bug_users",
        TicketType.INCIDENT: "incident_users",
        TicketType.SUPPORT: "support_users",
        TicketType.IMPROVEMENT: "improvement_users",
        TicketType.FEATURE: "feature_users",
    }
    for ticket_type, question_id in USER_QUESTION_IDS.items():
        assert question_id in {q.id for q in questions_for(ticket_type)}
        assert not {q.id: q for q in questions_for(ticket_type)}[question_id].required


def test_the_emails_of_the_users_come_from_their_question_only() -> None:
    from tamy.chamados.checklist import affected_emails

    answers = {
        "bug_users": "ana@loja.com, Bia <bia@loja.com>\ncaio@loja.com e ana@loja.com",
        "bug_steps": "tentou convidar zé@x.com",
    }

    assert affected_emails(TicketType.BUG, answers) == [
        "ana@loja.com",
        "bia@loja.com",
        "caio@loja.com",
    ]
    assert affected_emails(TicketType.ACCESS, answers) == []
