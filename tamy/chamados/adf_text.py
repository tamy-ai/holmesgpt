"""An Atlassian document read back as Slack text.

The bot writes the description once, as a document for Jira, and posts the same
content in the thread. The converter handles the nodes `ticket_body` builds:
headings, paragraphs, bullet and ordered lists, links.

Every text node is data: `&`, `<` and `>` are escaped, so `<!channel>` or `<@U123>`
inside an answer stays literal characters and notifies nobody.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from tamy.chamados.jira_rest import AdfNode

# Slack shows about 4,000 characters of one message well. The rest is in Jira.
MAX_SLACK_CHARS = 3500


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _nodes(value: object) -> list[AdfNode]:
    """The child nodes of a node: the dicts of a list, and nothing else."""
    if not isinstance(value, list):
        return []
    return [cast(AdfNode, item) for item in value if isinstance(item, dict)]


def _href(node: AdfNode) -> str | None:
    for mark in _nodes(node.get("marks")):
        if mark.get("type") == "link":
            attrs = mark.get("attrs")
            href = attrs.get("href") if isinstance(attrs, dict) else None
            if isinstance(href, str):
                return href
    return None


def _inline(nodes: Sequence[AdfNode]) -> str:
    parts: list[str] = []
    for node in nodes:
        text = _escape(str(node.get("text", "")))
        href = _href(node)
        parts.append(f"<{href}|{text}>" if href else text)
    return "".join(parts)


def _item_text(item: AdfNode) -> str:
    return " ".join(
        _inline(_nodes(paragraph.get("content")))
        for paragraph in _nodes(item.get("content"))
    )


def _block(node: AdfNode) -> str:
    kind = node.get("type")
    children = _nodes(node.get("content"))
    if kind == "heading":
        return f"*{_inline(children)}*"
    if kind == "paragraph":
        return _inline(children)
    if kind == "bulletList":
        return "\n".join(f"• {_item_text(item)}" for item in children)
    if kind == "orderedList":
        return "\n".join(
            f"{number}. {_item_text(item)}" for number, item in enumerate(children, 1)
        )
    return ""


def adf_to_mrkdwn(doc: AdfNode, *, rest_url: str | None = None) -> str:
    """The document as Slack text. Cut at `MAX_SLACK_CHARS` on a block boundary,
    with a link to the rest when `rest_url` is given."""
    kept: list[str] = []
    size = 0
    for block in _nodes(doc.get("content")):
        text = _block(block)
        if not text:
            continue
        if kept and size + len(text) > MAX_SLACK_CHARS:
            kept.append(f"<{rest_url}|ver o resto no Jira>" if rest_url else "…")
            break
        kept.append(text)
        size += len(text) + 2
    return "\n\n".join(kept)
