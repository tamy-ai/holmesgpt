"""The status of a ticket the bot opened comes back to its Slack thread (TA-1316).

No database: Jira is the memory. The label `slack-avisou-<status>` says "this status was already
told", and it is written BEFORE the message, so a failure never repeats a message every run.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger("tamy.slack_bot.sync")

BOT_LABEL = "origem-slack"
NOTIFIED_PREFIX = "slack-avisou-"
CONFIRMED_LABEL = "confirmado-no-slack"
WINDOW = "14d"
SAID = {"Fazendo": "fazendo", "Em produção": "em-producao"}
_THREAD_LABEL = re.compile(r"^slack-(C[A-Z0-9]+)-(\d+\.\d+)$")


class SyncJira(Protocol):
    def search(self, jql: str, **options: Any) -> list[dict[str, Any]]: ...

    def add_label(self, key: str, label: str) -> None: ...


class SyncSlack(Protocol):
    def post(self, **kwargs: Any) -> str: ...


@dataclass(frozen=True)
class Notice:
    key: str
    status: str
    summary: str
    channel: str
    thread_ts: str


def thread_of(labels: list[str]) -> tuple[str, str] | None:
    for label in labels:
        match = _THREAD_LABEL.match(label)
        if match:
            return match.group(1), match.group(2)
    return None


def notices_for(issues: list[dict[str, Any]]) -> list[Notice]:
    notices: list[Notice] = []
    for issue in issues:
        fields = issue.get("fields", {})
        labels = [str(label) for label in fields.get("labels", [])]
        status = str((fields.get("status") or {}).get("name", ""))
        thread = thread_of(labels)
        if BOT_LABEL not in labels or thread is None or status not in SAID:
            continue
        if NOTIFIED_PREFIX + SAID[status] in labels:
            continue
        notices.append(Notice(str(issue["key"]), status, str(fields.get("summary", "")), *thread))
    return notices


def resolved_blocks(key: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": "holmes_resolved_yes",
                    "style": "primary",
                    "text": {"type": "plain_text", "text": "Resolveu"},
                    "value": key,
                },
                {
                    "type": "button",
                    "action_id": "holmes_resolved_no",
                    "text": {"type": "plain_text", "text": "Ainda não"},
                    "value": key,
                },
            ],
        }
    ]


def _message(notice: Notice) -> str:
    link = f"<https://tamy-ai.atlassian.net/browse/{notice.key}|{notice.key}>"
    if notice.status == "Fazendo":
        return f"Começaram a trabalhar no chamado {link}: {notice.summary}"
    return f"O chamado {link} foi para produção: {notice.summary}\nResolveu para você?"


def run_sync(jira: SyncJira, slack: SyncSlack) -> int:
    """One pass. Returns how many messages went out."""
    jql = (
        f"project = TA AND labels = {BOT_LABEL} AND updated >= -{WINDOW} "
        'AND status in ("Fazendo", "Em produção")'
    )
    sent = 0
    for notice in notices_for(jira.search(jql, fields=("status", "labels", "summary"))):
        try:
            jira.add_label(notice.key, NOTIFIED_PREFIX + SAID[notice.status])
        except Exception:
            logger.exception("could not label %s; nothing is said", notice.key)
            continue
        blocks = resolved_blocks(notice.key) if notice.status == "Em produção" else None
        extra = {"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": _message(notice)}}, *blocks]} if blocks else {}
        slack.post(channel=notice.channel, thread_ts=notice.thread_ts, text=_message(notice), **extra)
        sent += 1
    return sent


class ResolveJira(Protocol):
    def issue_labels(self, key: str) -> list[str]: ...

    def add_comment(self, key: str, body: dict[str, Any]) -> None: ...

    def add_label(self, key: str, label: str) -> None: ...

    def reopen(self, key: str) -> None: ...


class ThreadReader(Protocol):
    def replies(self, channel: str, thread_ts: str) -> list[dict[str, Any]]: ...

    def display_name(self, user: str) -> str: ...


def _doc(text: str) -> dict[str, Any]:
    return {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


def answer_resolved(key: str, user: str, resolved: bool, jira: ResolveJira, slack: ThreadReader) -> tuple[str, bool]:
    """The click on Resolveu or Ainda não. Only who opened the thread answers, and only for a
    ticket this bot opened. Returns what to say, and whether the ticket changed."""
    labels = jira.issue_labels(key)
    thread = thread_of(labels)
    if BOT_LABEL not in labels or thread is None:
        return "Esse chamado não foi aberto por mim. Não mexo nele.", False
    messages = slack.replies(*thread)
    if not messages or messages[0].get("user") != user:
        return "Só quem pediu o chamado responde isso.", False
    name = slack.display_name(user)
    if resolved:
        jira.add_comment(key, _doc(f"{name} confirmou no Slack que o problema está resolvido."))
        jira.add_label(key, CONFIRMED_LABEL)
        return f"Obrigado! Registrei no {key} que está resolvido.", True
    jira.add_comment(key, _doc(f"{name} disse no Slack que o problema ainda não está resolvido."))
    jira.reopen(key)
    return f"Entendi, reabri o {key} para o time olhar de novo.", True
