"""What the bot shows in Slack: the answer as Slack text, and the approval preview."""

from __future__ import annotations

import json

from tamy.slack_bot.formatting import (
    MAX_MESSAGE_CHARS,
    approval_blocks,
    split_message,
    to_slack_mrkdwn,
)


def test_markdown_becomes_slack_text() -> None:
    text = to_slack_mrkdwn("## Causa\n**negrito** e [link](https://x.test/a) e `codigo`")

    assert text.splitlines()[0] == "*Causa*"
    assert "*negrito*" in text
    assert "<https://x.test/a|link>" in text
    assert "`codigo`" in text


def test_a_mention_inside_the_answer_never_pings_anyone() -> None:
    text = to_slack_mrkdwn("veja <!channel> e <@U123> e <#C1>")

    assert "<!channel>" not in text and "<@U123>" not in text and "<#C1>" not in text


def test_a_long_answer_is_split_on_line_breaks() -> None:
    answer = "\n".join(f"linha {n} " + "x" * 80 for n in range(200))

    parts = split_message(answer)

    assert len(parts) > 1
    assert all(len(part) <= MAX_MESSAGE_CHARS for part in parts)
    assert "\n".join(parts).count("linha") == 200


def test_a_short_answer_is_one_part() -> None:
    assert split_message("ok") == ["ok"]


def _create_issue(body: dict) -> dict:
    return {
        "tool_call_id": "call-1",
        "tool_name": "jira_write_request",
        "description": "HTTP POST https://api.atlassian.com/ex/jira/abc/rest/api/2/issue",
        "params": {
            "url": "https://api.atlassian.com/ex/jira/abc/rest/api/2/issue",
            "method": "POST",
            "body": json.dumps(body),
        },
    }


def test_the_preview_of_a_new_ticket_reads_like_a_ticket() -> None:
    blocks = approval_blocks(
        "req-1",
        [
            _create_issue(
                {
                    "fields": {
                        "project": {"key": "TA"},
                        "issuetype": {"name": "Bug"},
                        "summary": "DRE: CMV sem embalagem",
                        "labels": ["tipo-bug", "sla-p2"],
                        "description": "h3. Resumo\nO CMV não soma a embalagem",
                    }
                }
            )
        ],
        requester="U9",
    )

    text = json.dumps(blocks, ensure_ascii=False)
    assert "Criar chamado" in text
    assert "DRE: CMV sem embalagem" in text
    assert "Bug" in text and "tipo-bug" in text
    assert "O CMV não soma a embalagem" in text
    assert "Nada foi criado ainda" in text


def test_the_preview_of_a_comment_or_a_transition_says_which_ticket() -> None:
    comment = {
        "tool_call_id": "c2",
        "tool_name": "jira_write_request",
        "description": "x",
        "params": {
            "url": "https://api.atlassian.com/ex/jira/abc/rest/api/2/issue/TA-12/comment",
            "method": "POST",
            "body": json.dumps({"body": "Causa provável: ..."}),
        },
    }
    transition = {
        "tool_call_id": "c3",
        "tool_name": "jira_write_request",
        "description": "x",
        "params": {
            "url": "https://api.atlassian.com/ex/jira/abc/rest/api/2/issue/TA-12/transitions",
            "method": "POST",
            "body": json.dumps({"transition": {"id": "31"}}),
        },
    }

    text = json.dumps(approval_blocks("r", [comment, transition], requester="U1"), ensure_ascii=False)

    assert text.count("TA-12") >= 2
    assert "Comentar" in text and "Mudar" in text


def test_the_buttons_carry_the_request_id_and_only_that() -> None:
    blocks = approval_blocks("req-7", [_create_issue({"fields": {}})], requester="U9")

    buttons = [e for b in blocks for e in b.get("elements", []) if e.get("type") == "button"]
    assert {b["action_id"] for b in buttons} == {"holmes_approve", "holmes_deny"}
    assert {b["value"] for b in buttons} == {"req-7"}


def test_a_body_that_is_not_json_is_shown_as_it_is() -> None:
    odd = _create_issue({})
    odd["params"]["body"] = "not json at all"

    text = json.dumps(approval_blocks("r", [odd], requester="U1"), ensure_ascii=False)

    assert "not json at all" in text
