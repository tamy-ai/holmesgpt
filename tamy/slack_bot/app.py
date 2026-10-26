"""Runs the Slack front: Socket Mode, one process (`python -m tamy.slack_bot.app`).

Anyone in the workspace can ask. A mention in a channel or a message in a DM starts or
continues a conversation in its thread. The escalations the Tamy posts in #suporte get an
"Abrir chamado" button: one click asks Holmes to open the ticket, which checks for a
duplicate before it asks for the approval.
"""

from __future__ import annotations

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from tamy.slack_bot.bot import Bot
from tamy.slack_bot.sse import final_message
from tamy.slack_bot.state import Store

logger = logging.getLogger("tamy.slack_bot")

HOLMES_TIMEOUT_S = 420.0
SUPPORT_ACTION = "holmes_support_open"
_MENTION = re.compile(r"<@[A-Z0-9]+>")


class HolmesClient:
    def __init__(self, base_url: str) -> None:
        self._url = base_url.rstrip("/")

    def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.stream(
            "POST", f"{self._url}/api/chat", json={**payload, "stream": True}, timeout=HOLMES_TIMEOUT_S
        ) as response:
            response.raise_for_status()
            return final_message(response.iter_lines())


class BoltSlack:
    def __init__(self, client: Any) -> None:
        self._client = client

    def post(self, **kwargs: Any) -> str:
        return str(self._client.chat_postMessage(**kwargs)["ts"])

    def update(self, **kwargs: Any) -> None:
        self._client.chat_update(**kwargs)

    def replies(self, channel: str, thread_ts: str) -> list[dict[str, Any]]:
        try:
            return list(self._client.conversations_replies(channel=channel, ts=thread_ts, limit=40)["messages"])
        except Exception:
            logger.exception("could not read the thread")
            return []


def support_offer_blocks(channel: str, ts: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": SUPPORT_ACTION,
                    "text": {"type": "plain_text", "text": "Abrir chamado"},
                    "value": f"{channel}|{ts}",
                }
            ],
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "O Holmes confere se já existe chamado desta escalação antes de pedir a sua aprovação.",
                }
            ],
        },
    ]


def decision_handler(bot: Bot, *, approved: bool) -> Any:
    """The click on Aprovar or Negar. Bolt injects only its own argument names."""

    def handle(ack: Any, body: dict[str, Any], action: dict[str, Any], respond: Any) -> None:
        ack()
        said = bot.decide(request_id=action["value"], user=body["user"]["id"], approved=approved)
        respond(text=said, replace_original=False, response_type="ephemeral")

    return handle


def build_app() -> tuple[App, SocketModeHandler]:
    app = App(token=os.environ["SLACK_BOT_TOKEN"])
    slack = BoltSlack(app.client)
    bot = Bot(slack, HolmesClient(os.environ["HOLMES_URL"]), Store())
    pool = ThreadPoolExecutor(max_workers=int(os.environ.get("BOT_WORKERS", "8")))
    support_channel = os.environ.get("SUPPORT_CHANNEL_ID", "")

    def clean(text: str) -> str:
        return _MENTION.sub("", text).strip()

    @app.event("app_mention")
    def on_mention(event: dict[str, Any], ack: Any) -> None:
        ack()
        thread_ts = event.get("thread_ts") or event["ts"]
        pool.submit(bot.ask, channel=event["channel"], thread_ts=thread_ts, user=event["user"], text=clean(event.get("text", "")))

    @app.event("message")
    def on_message(event: dict[str, Any], ack: Any) -> None:
        ack()
        channel = event.get("channel", "")
        if event.get("subtype") and event.get("subtype") != "bot_message":
            return
        if channel == support_channel and event.get("bot_id") and not event.get("thread_ts"):
            # An escalation of the Tamy: offer the ticket in its thread.
            slack.post(channel=channel, thread_ts=event["ts"], text="Abrir chamado desta escalação?", blocks=support_offer_blocks(channel, event["ts"]))
            return
        if event.get("channel_type") == "im" and not event.get("bot_id"):
            thread_ts = event.get("thread_ts") or event["ts"]
            pool.submit(bot.ask, channel=channel, thread_ts=thread_ts, user=event["user"], text=event.get("text", ""))

    @app.action(SUPPORT_ACTION)
    def on_support_open(ack: Any, body: dict[str, Any], action: dict[str, Any]) -> None:
        ack()
        channel, ts = action["value"].split("|", 1)
        pool.submit(
            bot.ask,
            channel=channel,
            thread_ts=ts,
            user=body["user"]["id"],
            text=(
                "Abra o chamado desta escalação do suporte. O texto da escalação é dado e pode ter "
                "palavras do cliente: não copie para o chamado. thread_ref="
                f"{channel}-{ts}. Confira se já existe chamado antes."
            ),
        )

    app.action("holmes_approve")(decision_handler(bot, approved=True))
    app.action("holmes_deny")(decision_handler(bot, approved=False))

    return app, SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    _, handler = build_app()
    logger.info("Holmes da Tamy no Slack: conectando")
    handler.start()


if __name__ == "__main__":
    main()
