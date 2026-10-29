"""Error reporting for holmes and holmes-slack: our GlitchTip, never sentry.io.

Decision 0757 of tamy-consultant. The upstream init in server.py only runs with
ENABLE_TELEMETRY on an official release, which our image never is, so the Tamy
services start the SDK here whenever SENTRY_DSN is set.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _is_paid_sentry(dsn: str) -> bool:
    host = (urlparse(dsn).hostname or "").lower()
    return host == "sentry.io" or host.endswith(".sentry.io")


def init_error_reporting(service: str) -> None:
    dsn = os.environ.get("SENTRY_DSN", "")
    if not dsn:
        return
    if _is_paid_sentry(dsn):
        logger.error(
            "SENTRY_DSN points to sentry.io; errors go to our GlitchTip only. "
            "Error reporting not started."
        )
        return

    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        server_name=service,
        environment=os.environ.get("SENTRY_ENVIRONMENT"),
        traces_sample_rate=0.0,
        profiles_sample_rate=0.0,
        # A ticket and a Slack thread carry the customer's words.
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
    )
    logger.info("Error reporting started for %s", service)
