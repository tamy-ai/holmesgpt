"""What the bot shows in Slack: the answer as Slack text, and the approval preview.

Every text that comes from a person or from the model is data. Slack treats `<!channel>`,
`<@U1>` and `<#C1>` as mentions, so the answer escapes them: nobody is pinged by a
sentence the model repeated from a thread.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

MAX_MESSAGE_CHARS = 3500
MAX_BODY_PREVIEW = 700

_HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_MENTION = re.compile(r"<([!@#][^>]*)>")


def to_slack_mrkdwn(text: str) -> str:
    escaped = _MENTION.sub(lambda m: f"&lt;{m.group(1)}&gt;", text)
    escaped = _HEADING.sub(lambda m: f"*{m.group(1).strip()}*", escaped)
    escaped = _BOLD.sub(r"*\1*", escaped)
    return _LINK.sub(r"<\2|\1>", escaped)


def split_message(text: str, limit: int = MAX_MESSAGE_CHARS) -> list[str]:
    """Parts of at most `limit` characters, cut on line breaks."""
    parts: list[str] = []
    current = ""
    for line in text.splitlines():
        line = line[:limit]
        if len(current) + len(line) + 1 > limit and current:
            parts.append(current)
            current = ""
        current = f"{current}\n{line}" if current else line
    if current:
        parts.append(current)
    return parts or [text[:limit]]


def _ticket_key(url: str) -> str:
    match = re.search(r"/issue/([A-Z][A-Z0-9]*-\d+)", url)
    return match.group(1) if match else ""


def _body(params: dict[str, Any]) -> Any:
    raw = params.get("body")
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _preview_of(approval: dict[str, Any]) -> str:
    params = approval.get("params", {})
    url = str(params.get("url", ""))
    method = str(params.get("method", "GET")).upper()
    body = _body(params)
    key = _ticket_key(url)
    if not isinstance(body, dict):
        return f"`{method} {url}`\n```{str(body or '')[:MAX_BODY_PREVIEW]}```"
    if url.rstrip("/").endswith("/issue") and method == "POST":
        fields = body.get("fields", {}) if isinstance(body.get("fields"), dict) else {}
        kind = (fields.get("issuetype") or {}).get("name", "?")
        labels = ", ".join(str(label) for label in fields.get("labels", []))
        description = str(fields.get("description", ""))[:MAX_BODY_PREVIEW]
        return (
            f"*Criar chamado* ({kind})\n*{fields.get('summary', '(sem título)')}*\n"
            f"Rótulos: {labels or 'nenhum'}"
            + (f"\nPrazo: {fields['duedate']}" if fields.get("duedate") else "")
            + (f"\n```{description}```" if description else "")
        )
    if url.endswith("/comment"):
        return f"*Comentar em {key}*\n```{str(body.get('body', ''))[:MAX_BODY_PREVIEW]}```"
    if url.endswith("/transitions"):
        transition = (body.get("transition") or {}).get("id", "?")
        return f"*Mudar o status de {key}* (transição {transition})"
    return f"*Editar {key or 'chamado'}* (`{method}`)\n```{json.dumps(body, ensure_ascii=False)[:MAX_BODY_PREVIEW]}```"


def approval_blocks(
    request_id: str, approvals: Sequence[dict[str, Any]], *, requester: str
) -> list[dict[str, Any]]:
    """The preview of what the bot will do in Jira, and the two buttons."""
    sections = "\n\n".join(_preview_of(a) for a in approvals)
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": to_slack_mrkdwn(sections)
                + "\n\n_Nada foi criado ainda. Confira e clique em Aprovar._",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": "holmes_approve",
                    "style": "primary",
                    "text": {"type": "plain_text", "text": "Aprovar"},
                    "value": request_id,
                },
                {
                    "type": "button",
                    "action_id": "holmes_deny",
                    "text": {"type": "plain_text", "text": "Negar"},
                    "value": request_id,
                },
            ],
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Só <@{requester}> aprova ou nega."}
            ],
        },
    ]
