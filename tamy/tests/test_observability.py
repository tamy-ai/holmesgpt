"""Errors of holmes and holmes-slack go to our GlitchTip, never to sentry.io (decision 0757)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tamy.observability import init_error_reporting

GLITCHTIP_DSN = "https://abc@glitchtip-production-8e27.up.railway.app/3"


def _start(env: dict[str, str]) -> MagicMock:
    with (
        patch.dict("os.environ", env, clear=True),
        patch("sentry_sdk.init") as sdk_init,
    ):
        init_error_reporting("holmes-slack")
    return sdk_init


def test_the_glitchtip_dsn_starts_the_sdk_with_no_telemetry_flag() -> None:
    sdk_init = _start({"SENTRY_DSN": GLITCHTIP_DSN})

    sdk_init.assert_called_once()
    kwargs = sdk_init.call_args.kwargs
    assert kwargs["dsn"] == GLITCHTIP_DSN
    assert kwargs["server_name"] == "holmes-slack"


def test_nothing_personal_leaves_in_an_event() -> None:
    kwargs = _start({"SENTRY_DSN": GLITCHTIP_DSN}).call_args.kwargs

    assert kwargs["send_default_pii"] is False
    assert kwargs["include_local_variables"] is False
    assert kwargs["max_request_body_size"] == "never"


def test_the_environment_comes_from_the_variable() -> None:
    kwargs = _start(
        {"SENTRY_DSN": GLITCHTIP_DSN, "SENTRY_ENVIRONMENT": "production"}
    ).call_args.kwargs

    assert kwargs["environment"] == "production"


@pytest.mark.parametrize(
    "dsn",
    [
        "https://abc@o4508991047925760.ingest.us.sentry.io/1",
        "https://abc@sentry.io/1",
        "https://abc@O1.INGEST.SENTRY.IO/2",
    ],
)
def test_a_sentry_io_dsn_never_starts_the_sdk(dsn: str) -> None:
    assert not _start({"SENTRY_DSN": dsn}).called


def test_no_dsn_starts_nothing() -> None:
    assert not _start({}).called
