"""The Jira description a ticket born in Slack carries.

Written for a reader who was not in the thread and has ten minutes (Atlassian and New
Relic ticket guidance, researched 2026-10-25): the problem, the context, the steps or
the story, the acceptance criteria as Given/When/Then, and what is still unknown.
"""

from __future__ import annotations

import datetime
import json
from typing import Any

from tamy.chamados.draft import TicketDraft, TicketPriority, TicketType
from tamy.chamados.ticket_body import build_description


def _doc(draft: TicketDraft, **kwargs: Any) -> dict[str, Any]:
    params: dict[str, Any] = {
        "requester_name": "Ana",
        "thread_url": "https://tamy.slack.com/archives/C1/p170",
        "due_on": datetime.date(2026, 10, 28),
    }
    params.update(kwargs)
    return build_description(draft, **params)


def _text(node: Any) -> str:
    return json.dumps(node, ensure_ascii=False)


def _headings(doc: dict[str, Any]) -> list[str]:
    return [
        block["content"][0]["text"]
        for block in doc["content"]
        if block["type"] == "heading"
    ]


def _section(doc: dict[str, Any], heading: str) -> dict[str, Any]:
    """The block right after a heading."""
    blocks = doc["content"]
    for index, block in enumerate(blocks):
        if block["type"] == "heading" and block["content"][0]["text"] == heading:
            return blocks[index + 1]
    raise AssertionError(f"no section {heading!r} in {_headings(doc)}")


BUG = TicketDraft(
    ticket_type=TicketType.BUG,
    priority=TicketPriority.P1,
    summary="Painel de vendas: total diferente do PDV",
    client_hint="Martita",
    answers={
        "bug_client": "Martita, loja 3",
        "bug_steps": "1. Abrir Vendas\n2. Escolher ontem\n3. Comparar com o PDV",
        "bug_expected": "O mesmo total do PDV, R$ 1.300,00",
        "bug_actual": "O painel mostra R$ 1.210,00, R$ 90,00 a menos",
        "bug_reach": "Só essa loja",
    },
)


def test_every_description_opens_with_the_summary_then_the_context() -> None:
    doc = _doc(BUG)

    assert doc["type"] == "doc"
    assert _headings(doc)[:2] == ["Resumo", "Contexto"]
    assert "Painel de vendas: total diferente do PDV" in _text(_section(doc, "Resumo"))


def test_the_context_is_a_list_of_facts_with_the_thread_link() -> None:
    context = _text(_section(_doc(BUG), "Contexto"))

    assert "Tipo: Bug" in context
    assert "Prioridade: P1 (urgente), prazo qua 28/10" in context
    # The client the thread gave, in full: the name alone says less.
    assert "Cliente: Martita, loja 3" in context
    assert "Pedido por: Ana" in context
    assert "https://tamy.slack.com/archives/C1/p170" in context


def test_the_context_says_when_the_requester_and_the_link_are_missing() -> None:
    context = _text(
        _section(_doc(BUG, requester_name=None, thread_url=None), "Contexto")
    )

    assert "solicitante não identificado" in context
    assert "não foi obtido" in context


def test_the_steps_to_reproduce_are_an_ordered_list_one_step_each() -> None:
    steps = _section(_doc(BUG), "Passos para reproduzir")

    assert steps["type"] == "orderedList"
    assert len(steps["content"]) == 3
    assert "Escolher ontem" in _text(steps["content"][1])
    # The model numbered them: the list numbers them, so the text must not repeat it.
    assert "2." not in _text(steps["content"][1])


def test_expected_and_actual_are_two_sections_with_their_own_numbers() -> None:
    doc = _doc(BUG)

    assert "R$ 1.300,00" in _text(_section(doc, "Esperado"))
    assert "R$ 1.210,00" in _text(_section(doc, "Obtido"))
    assert "Esperado e obtido" not in _headings(doc)


def test_the_impact_lists_who_is_reached() -> None:
    impact = _text(_section(_doc(BUG), "Impacto"))

    assert "Só essa loja" in impact
    # The client is in the context; the same line twice is noise.
    assert "Martita" not in impact


def test_a_bug_has_acceptance_criteria_as_given_when_then() -> None:
    criteria = _section(_doc(BUG), "Critérios de aceite")

    assert criteria["type"] == "bulletList"
    text = _text(criteria)
    assert "Dado" in text and "quando" in text and "então" in text
    assert "teste automatizado" in text


def test_a_question_nobody_answered_is_listed_once_as_open() -> None:
    doc = _doc(BUG)
    open_items = _text(_section(doc, "Perguntas em aberto"))

    assert "Quando (dia e hora)?" in open_items
    assert "Tem contorno?" in open_items
    # Answered questions never show up as open.
    assert "Qual cliente" not in open_items
    # And "não informado" is not scattered through the rest of the ticket.
    assert "não informado" not in _text(_section(doc, "Impacto"))


def test_a_fully_answered_ticket_has_no_open_questions_section() -> None:
    answers = {
        "access_person": "ana@loja.com, Ana",
        "access_org": "Martita",
        "access_need": "convite",
        "access_approver": "dona da loja",
        "access_until": "sem prazo",
    }
    draft = TicketDraft(
        TicketType.ACCESS, TicketPriority.P2, "Convite para Ana", None, answers
    )

    assert "Perguntas em aberto" not in _headings(_doc(draft))


def test_a_feature_is_written_as_a_user_story_with_a_success_measure() -> None:
    draft = TicketDraft(
        TicketType.FEATURE,
        TicketPriority.P3,
        "Relatório de CMV por semana",
        None,
        {
            "feature_problem": "o dono não vê o CMV da semana",
            "feature_success": "o dono abre o CMV sozinho em menos de 1 minuto",
        },
    )
    doc = _doc(draft, due_on=None)

    story = _text(_section(doc, "História do usuário"))
    assert "Como dono de loja" in story
    assert "o dono não vê o CMV da semana" in story
    assert "em menos de 1 minuto" in story
    assert "sem prazo" in _text(_section(doc, "Contexto"))
    assert "Critérios de aceite" in _headings(doc)


def test_each_type_has_its_own_acceptance_criteria() -> None:
    def criteria(ticket_type: TicketType) -> str:
        draft = TicketDraft(ticket_type, TicketPriority.P2, "x", None)
        return _text(_section(_doc(draft), "Critérios de aceite"))

    assert "teste automatizado" in criteria(TicketType.BUG)
    assert "bate com a fonte" in criteria(TicketType.SUPPORT)
    assert "só o que o perfil permite" in criteria(TicketType.ACCESS)
    assert "Dado" in criteria(TicketType.IMPROVEMENT)
    assert "medido" in criteria(TicketType.FEATURE)


def test_the_text_of_an_answer_is_data_and_never_markup() -> None:
    draft = TicketDraft(
        TicketType.BUG,
        TicketPriority.P2,
        "x",
        None,
        {"bug_expected": "*negrito* [link](http://evil) {code}"},
    )

    text = _text(_section(_doc(draft), "Esperado"))
    # ADF text nodes carry no markup: it stays as literal characters.
    assert "*negrito* [link](http://evil) {code}" in text
    assert '"marks"' not in text


def test_the_date_of_the_request_anchors_every_relative_word() -> None:
    context = _text(
        _section(_doc(BUG, requested_on=datetime.date(2026, 10, 26)), "Contexto")
    )

    assert "Pedido em: seg 26/10/2026" in context


def test_the_files_of_the_thread_are_counted_never_named() -> None:
    """Decision 0667: no file name goes to Jira. The answer a person gave to
    "tem print?" can hold one, so the description does not repeat it."""
    draft = TicketDraft(
        TicketType.BUG,
        TicketPriority.P2,
        "x",
        None,
        {"bug_evidence": "Sim, print-da-martita.png e extrato-12345678900.pdf"},
    )

    doc = _doc(draft, thread_file_count=2)
    text = _text(_section(doc, "Evidências"))

    assert "2 arquivos" in text
    assert "anexados" in text and "comentário" in text
    assert "print-da-martita" not in _text(doc)
    assert "Tem print ou vídeo?" not in _text(_section(doc, "Perguntas em aberto"))


def test_a_bug_with_no_file_says_so() -> None:
    text = _text(_section(_doc(BUG, thread_file_count=0), "Evidências"))

    assert "Nenhum arquivo" in text


def test_the_acceptance_criteria_of_the_case_replace_the_generic_ones() -> None:
    draft = TicketDraft(
        TicketType.BUG,
        TicketPriority.P2,
        "x",
        None,
        {
            "acceptance": (
                "1. Dado a loja 3 em 25/10, quando abrir Vendas, então o total é R$ 1.300,00\n"
                "- O total do painel e o do PDV batem em outro dia"
            )
        },
    )

    criteria = _section(_doc(draft), "Critérios de aceite")

    assert len(criteria["content"]) == 2
    assert "R$ 1.300,00" in _text(criteria["content"][0])
    # The list mark the model wrote is gone: the bullet is the mark.
    assert criteria["content"][0]["content"][0]["content"][0]["text"].startswith("Dado")
    assert "teste automatizado" not in _text(criteria)


def test_the_reason_of_the_priority_sits_next_to_the_priority() -> None:
    draft = TicketDraft(
        TicketType.BUG,
        TicketPriority.P1,
        "x",
        None,
        {"priority_reason": "A loja fecha o caixa com esse total hoje à noite"},
    )

    context = _text(_section(_doc(draft), "Contexto"))

    assert "Motivo da prioridade: A loja fecha o caixa" in context


def test_the_users_hurt_by_the_bug_are_listed_one_per_line() -> None:
    draft = TicketDraft(
        TicketType.BUG,
        TicketPriority.P2,
        "x",
        None,
        {"bug_users": "ana@loja.com e Bia <bia@loja.com>"},
    )

    section = _section(_doc(draft), "Usuários afetados")

    assert section["type"] == "bulletList"
    assert [_text(item) for item in section["content"]] == [
        _text(_section(_doc(draft), "Usuários afetados")["content"][0]),
        _text(_section(_doc(draft), "Usuários afetados")["content"][1]),
    ]
    assert "ana@loja.com" in _text(section) and "bia@loja.com" in _text(section)


def test_the_users_who_asked_for_a_change_have_their_own_heading() -> None:
    draft = TicketDraft(
        TicketType.IMPROVEMENT,
        TicketPriority.P2,
        "x",
        None,
        {"improvement_users": "cs@loja.com"},
    )

    assert "Usuários que pediram" in _headings(_doc(draft))
    assert "Usuários afetados" not in _headings(_doc(draft))


def test_an_incident_leads_with_what_is_down_and_since_when() -> None:
    draft = TicketDraft(
        TicketType.INCIDENT,
        TicketPriority.P0,
        "Chat fora do ar",
        None,
        {
            "incident_impact": "Ninguém recebe resposta no chat",
            "incident_since": "26/10/2026, 08:10",
            "incident_reach": "Todos os clientes",
            "incident_data": "Não há dado errado",
        },
    )
    doc = _doc(draft)

    assert "Ninguém recebe resposta" in _text(_section(doc, "O que está acontecendo"))
    impact = _text(_section(doc, "Impacto"))
    assert "Desde: 26/10/2026, 08:10" in impact
    assert "Todos os clientes" in impact
    assert "Risco para o dado: Não há dado errado" in impact


def test_a_question_and_a_technical_task_have_their_own_sections() -> None:
    question = TicketDraft(
        TicketType.QUESTION,
        TicketPriority.P2,
        "Dúvida sobre CMV",
        None,
        {
            "question_ask": "O CMV conta a embalagem?",
            "question_who": "CS, cliente Martita",
        },
    )
    task = TicketDraft(
        TicketType.TASK,
        TicketPriority.P2,
        "Trocar a chave do Vertex",
        None,
        {
            "task_goal": "Reemitir a chave",
            "task_why": "A chave atual foi revogada",
            "task_done": "O chat local responde",
        },
    )

    assert "O CMV conta a embalagem?" in _text(_section(_doc(question), "Dúvida"))
    assert "A chave atual foi revogada" in _text(_section(_doc(task), "Por que agora"))
    assert "O chat local responde" in _text(
        _section(_doc(task), "Como saber que acabou")
    )


def test_the_channel_and_the_area_are_in_the_context() -> None:
    draft = TicketDraft(
        TicketType.BUG,
        TicketPriority.P2,
        "x",
        None,
        {"channel": "whatsapp", "area": "vendas"},
    )

    context = _text(_section(_doc(draft), "Contexto"))

    assert "Canal: WhatsApp" in context
    assert "Área: Vendas" in context


def test_the_first_places_to_look_are_the_code_of_the_area() -> None:
    draft = TicketDraft(TicketType.BUG, TicketPriority.P2, "x", None, {"area": "dre"})

    section = _section(_doc(draft), "Onde olhar primeiro")

    assert section["type"] == "bulletList"
    text = _text(section)
    assert "backend/onyx/server/features/tamy_dre" in text
    assert "web/src/views/painel/DreView.tsx" in text


def test_a_ticket_with_no_known_area_has_no_pointer_section() -> None:
    for answers in ({}, {"area": "outro"}):
        draft = TicketDraft(TicketType.BUG, TicketPriority.P2, "x", None, answers)

        assert "Onde olhar primeiro" not in _headings(_doc(draft))
