"""The description that went to Jira, read back in Slack.

The same document, turned into the text Slack shows. The thread then holds what the
ticket holds, so nobody opens Jira to check what the bot wrote.
"""

from __future__ import annotations

from tamy.chamados.jira_rest import (
    adf_blocks,
    adf_bullets,
    adf_heading,
    adf_link,
    adf_ordered,
    adf_paragraph,
    adf_text,
)
from tamy.chamados.adf_text import MAX_SLACK_CHARS, adf_to_mrkdwn


def test_headings_lists_and_links_read_as_slack_text() -> None:
    doc = adf_blocks(
        [
            adf_heading("Contexto"),
            adf_bullets(
                [
                    [adf_text("Tipo: Bug")],
                    [adf_link("Fio no Slack", "https://tamy.slack.com/p1")],
                ]
            ),
            adf_heading("Passos"),
            adf_ordered([[adf_text("Abrir Vendas")], [adf_text("Escolher ontem")]]),
            adf_paragraph([adf_text("Esperava o total do PDV")]),
        ]
    )

    text = adf_to_mrkdwn(doc)

    assert "*Contexto*" in text
    assert "• Tipo: Bug" in text
    assert "• <https://tamy.slack.com/p1|Fio no Slack>" in text
    assert "1. Abrir Vendas\n2. Escolher ontem" in text
    assert "Esperava o total do PDV" in text


def test_a_mention_inside_an_answer_never_pings_anyone() -> None:
    """The text is data. `<!channel>` and `<@U1>` would notify people in the thread."""
    doc = adf_blocks([adf_paragraph([adf_text("<!channel> <@U123> a & b")])])

    text = adf_to_mrkdwn(doc)

    assert "<!channel>" not in text and "<@U123>" not in text
    assert "&lt;!channel&gt; &lt;@U123&gt; a &amp; b" in text


def test_a_long_description_is_cut_and_says_where_the_rest_is() -> None:
    doc = adf_blocks(
        [adf_paragraph([adf_text("linha longa " * 100)]) for _ in range(20)]
    )

    text = adf_to_mrkdwn(doc, rest_url="https://jira.test/browse/TA-1")

    assert len(text) <= MAX_SLACK_CHARS + 200
    assert text.rstrip().endswith("<https://jira.test/browse/TA-1|ver o resto no Jira>")


def test_a_short_description_is_not_cut() -> None:
    doc = adf_blocks([adf_paragraph([adf_text("curta")])])

    assert adf_to_mrkdwn(doc, rest_url="https://jira.test/browse/TA-1") == "curta"
