"""What the bot adds to a ticket it just opened: the files of the thread and the places to look (TA-1315).

The bot does it, not the model: the model never chooses what goes to Jira from a thread. A ticket
only gets files when its label says it came from THIS thread.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from tamy.chamados.areas import area_by_slug
from tamy.chamados.jira_rest import MultipartFile

logger = logging.getLogger("tamy.slack_bot.enrich")

MAX_FILES = 10
MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_PREFIXES = ("image/", "text/", "application/pdf", "application/vnd.openxmlformats", "application/vnd.ms-excel", "application/json")


@dataclass(frozen=True)
class SlackFile:
    name: str
    mimetype: str
    url: str


@dataclass(frozen=True)
class Links:
    grafana: str
    langfuse: str
    langfuse_project: str


@dataclass(frozen=True)
class EnrichResult:
    attached: int = 0
    failed: int = 0
    links: int = 0
    skipped: bool = False


class EnrichJira(Protocol):
    def issue_labels(self, key: str) -> list[str]: ...

    def add_attachment(self, key: str, file: MultipartFile) -> None: ...

    def add_remote_link(self, key: str, url: str, title: str) -> None: ...

    def add_label(self, key: str, label: str) -> None: ...


ENRICHED_LABEL = "slack-enriquecido"


def files_of(messages: list[dict[str, Any]]) -> list[SlackFile]:
    found: list[SlackFile] = []
    for message in messages:
        if message.get("bot_id"):
            continue
        for item in message.get("files", []):
            mimetype = str(item.get("mimetype", ""))
            if int(item.get("size", 0)) > MAX_FILE_BYTES or not mimetype.startswith(ALLOWED_PREFIXES):
                continue
            found.append(SlackFile(str(item.get("name", "arquivo")), mimetype, str(item.get("url_private_download", ""))))
    return found[:MAX_FILES]


def attach_files(files: list[SlackFile], download: Callable[[str], bytes], jira: EnrichJira, key: str) -> tuple[int, int]:
    attached = failed = 0
    for file in files:
        try:
            jira.add_attachment(key, MultipartFile(file.name, download(file.url), file.mimetype))
            attached += 1
        except Exception:
            logger.exception("could not attach %s to %s", file.name, key)
            failed += 1
    return attached, failed


def links_for(area_slug: str, links: Links) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    area = area_by_slug(area_slug)
    if area is not None:
        result.append((f"Painel do Grafana: {area.label}", f"{links.grafana}/d/{area.dashboard_uid}"))
    expression = '{service=~"api-server|background", level=~"error|critical"}'
    query = urllib.parse.quote(
        json.dumps({"datasource": "loki", "queries": [{"refId": "A", "expr": expression}], "range": {"from": "now-2h", "to": "now"}})
    )
    result.append(("Logs de erro (Loki, últimas 2 horas)", f"{links.grafana}/explore?left={query}"))
    if links.langfuse_project:
        result.append(("Traces do chat (Langfuse)", f"{links.langfuse}/project/{links.langfuse_project}/traces"))
    return result


def enrich_ticket(
    key: str,
    channel: str,
    thread_ts: str,
    messages: list[dict[str, Any]],
    download: Callable[[str], bytes],
    jira: EnrichJira,
    area_slug: str,
    links: Links,
) -> EnrichResult:
    labels = jira.issue_labels(key)
    if f"slack-{channel}-{thread_ts}" not in labels or ENRICHED_LABEL in labels:
        return EnrichResult(skipped=True)
    # Marked first: a failure after this never repeats the files.
    jira.add_label(key, ENRICHED_LABEL)
    attached, failed = attach_files(files_of(messages), download, jira, key)
    added = 0
    for title, url in links_for(area_slug, links):
        try:
            jira.add_remote_link(key, url, title)
            added += 1
        except Exception:
            logger.exception("could not link %s to %s", title, key)
    return EnrichResult(attached=attached, failed=failed, links=added)


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def describe(result: EnrichResult) -> str:
    """What the bot says in the thread. A failure is said, never hidden."""
    if result.skipped:
        return ""
    parts = []
    if result.attached:
        parts.append(f"Anexei {_plural(result.attached, 'arquivo', 'arquivos')}")
    links = _plural(result.links, "link", "links") if result.links else ""
    if parts and links:
        text = f"{parts[0]} e {links} ao chamado."
    elif parts:
        text = f"{parts[0]} ao chamado."
    elif links:
        text = f"Deixei {links} no chamado."
    else:
        text = ""
    if result.failed:
        text += f" Mas não consegui anexar {result.failed}."
    return text.strip()


class FindJira(Protocol):
    def search(self, jql: str, **options: Any) -> list[dict[str, Any]]: ...


def find_ticket(
    jira: FindJira,
    channel: str,
    thread_ts: str,
    attempts: int = 5,
    wait_s: float = 3.0,
    sleep: Callable[[float], None] = time.sleep,
) -> str | None:
    """The ticket of one thread, by its label. Jira indexes a new ticket a few seconds late."""
    jql = f"project = TA AND labels = slack-{channel}-{thread_ts}"
    for attempt in range(attempts):
        found = jira.search(jql, fields=("summary",))
        if found:
            return str(found[0]["key"])
        if attempt < attempts - 1:
            sleep(wait_s)
    return None
