"""The small pieces the ticket logic shares: São Paulo days and e-mail search.

Ported from the Tamy Consultant (`onyx.tamy.dates` and `onyx.tamy.pii_mask`), the only
parts the bot used. The restaurant business day is NOT here: a ticket counts in São
Paulo calendar days.
"""

from __future__ import annotations

import datetime
import re
from zoneinfo import ZoneInfo

BUSINESS_TZ = ZoneInfo("America/Sao_Paulo")

#: The weekday names a person reads, indexed by `date.weekday()`.
WEEKDAY_NAMES = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.ASCII)


def _utc_now() -> datetime.datetime:
    """The clock, in one place, so a test can freeze it."""
    return datetime.datetime.now(datetime.timezone.utc)


def business_date(moment: datetime.datetime) -> datetime.date:
    """The calendar day of `moment` in São Paulo."""
    return moment.astimezone(BUSINESS_TZ).date()


def backoffice_today() -> datetime.date:
    return business_date(_utc_now())


def find_email(text: str) -> str | None:
    """The first e-mail in `text`, lowercased."""
    found = _EMAIL.search(text)
    return found.group(0).lower() if found else None


def find_emails(text: str) -> list[str]:
    """Every e-mail in `text`, lowercased, in order, once each."""
    found: list[str] = []
    for match in _EMAIL.finditer(text):
        email = match.group(0).lower()
        if email not in found:
            found.append(email)
    return found
