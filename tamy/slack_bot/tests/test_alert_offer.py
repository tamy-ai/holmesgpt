"""Every alert in #alertas gets a "Criar ticket" button; a click asks Holmes to investigate and open it."""

from __future__ import annotations

from typing import Any

from tamy.slack_bot.app import (
    ALERT_ACTION,
    SUPPORT_ACTION,
    alert_offer_blocks,
    alert_ticket_handler,
    alert_ticket_request,
    offer_for,
)

ALERTS = "CALERTS"
SUPPORT = "CSUPPORT"


def _event(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"channel": ALERTS, "ts": "17.1", "bot_id": "B1", "subtype": "bot_message", "text": ""}
    base.update(kw)
    return base


def _offer(event: dict[str, Any]) -> str | None:
    return offer_for(event, support_channel=SUPPORT, alerts_channel=ALERTS)


def test_a_grafana_alert_gets_the_ticket_offer() -> None:
    event = _event(attachments=[{"title": "[FIRING:1] Sync com erro há mais de 1 h", "text": "conta 1164"}])

    assert _offer(event) == "alert"


def test_a_glitchtip_alert_with_text_only_gets_the_ticket_offer() -> None:
    assert _offer(_event(text="GlitchTip Alert: ValueError in sync_business_integration_account")) == "alert"


def test_a_resolved_alert_gets_no_offer() -> None:
    event = _event(attachments=[{"title": "[RESOLVED] Sync com erro há mais de 1 h"}])

    assert _offer(event) is None


def test_a_resolved_alert_in_the_text_gets_no_offer() -> None:
    assert _offer(_event(text="[RESOLVED] Worker do Celery parado")) is None


def test_a_reply_inside_an_alert_thread_gets_no_offer() -> None:
    assert _offer(_event(thread_ts="17.0", text="[FIRING:1] x")) is None


def test_a_person_writing_in_alertas_gets_no_offer() -> None:
    event = _event(text="alguém viu isso?", user="U1")
    del event["bot_id"]
    del event["subtype"]

    assert _offer(event) is None


def test_no_alerts_channel_configured_means_no_alert_offer() -> None:
    event = _event(text="[FIRING:1] x")

    assert offer_for(event, support_channel=SUPPORT, alerts_channel="") is None


def test_the_support_escalation_keeps_its_own_offer() -> None:
    assert _offer(_event(channel=SUPPORT, text="Escalação")) == "support"


def test_the_alert_offer_is_its_own_button_and_carries_the_thread() -> None:
    button = alert_offer_blocks(ALERTS, "17.1")[0]["elements"][0]

    assert button["action_id"] == ALERT_ACTION != SUPPORT_ACTION
    assert button["text"]["text"] == "Criar ticket"
    assert button["value"] == f"{ALERTS}|17.1"


def test_the_request_treats_the_alert_as_data_and_asks_for_a_duplicate_check() -> None:
    text = alert_ticket_request(ALERTS, "17.1")

    assert f"thread_ref={ALERTS}-17.1" in text
    assert "dado" in text
    assert "já existe" in text


class _Pool:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def submit(self, fn: Any, **kw: Any) -> None:
        self.calls.append((fn, kw))


def test_a_click_asks_holmes_in_the_thread_of_the_alert_as_the_person_who_clicked() -> None:
    pool = _Pool()
    ask = object()
    handler = alert_ticket_handler(ask, pool)

    handler(lambda: None, {"user": {"id": "U9"}}, {"value": f"{ALERTS}|17.1"})

    (fn, kw), = pool.calls
    assert fn is ask
    assert (kw["channel"], kw["thread_ts"], kw["user"]) == (ALERTS, "17.1", "U9")
    assert kw["text"] == alert_ticket_request(ALERTS, "17.1")
