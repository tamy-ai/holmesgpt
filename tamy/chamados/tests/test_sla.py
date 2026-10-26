"""Table A.10: the resolution SLA in working days, and the due date."""

from __future__ import annotations

import datetime

import pytest

from tamy.chamados.common import BUSINESS_TZ as SAO_PAULO
from tamy.chamados.draft import TicketPriority as P
from tamy.chamados.draft import TicketType as T
from tamy.chamados.sla import due_date, resolution_days, sla_label

FRIDAY = datetime.datetime(2026, 10, 23, 15, tzinfo=SAO_PAULO)


@pytest.mark.parametrize(
    "ticket_type, priority, days",
    [
        (T.BUG, P.P0, 1),
        (T.BUG, P.P1, 3),
        (T.BUG, P.P2, 5),
        (T.BUG, P.P3, None),
        (T.SUPPORT, P.P1, 2),
        (T.SUPPORT, P.P2, 3),
        (T.ACCESS, P.P1, 1),
        (T.ACCESS, P.P2, 2),
        (T.IMPROVEMENT, P.P1, 5),
        (T.IMPROVEMENT, P.P2, 10),
        (T.FEATURE, P.P1, None),
        (T.FEATURE, P.P2, None),
    ],
)
def test_table_a10(ticket_type: T, priority: P, days: int | None) -> None:
    assert resolution_days(ticket_type, priority) == days


def test_any_p0_is_one_working_day() -> None:
    """P0 is production broken: a hotfix, whatever the type."""
    assert {resolution_days(t, P.P0) for t in T} == {1}


def test_p3_has_no_due_date() -> None:
    assert {resolution_days(t, P.P3) for t in T if t is not T.BUG} == {None}


def test_due_date_counts_working_days() -> None:
    # Friday + 3 working days -> Wednesday 28/10.
    assert due_date(T.BUG, P.P1, FRIDAY) == datetime.date(2026, 10, 28)


def test_feature_has_no_due_date() -> None:
    assert due_date(T.FEATURE, P.P1, FRIDAY) is None


def test_sla_label() -> None:
    assert sla_label(P.P1) == "sla-p1"


def test_due_text_reads_like_the_team_speaks() -> None:
    from tamy.chamados.vocabulary import due_text

    assert due_text(datetime.date(2026, 10, 28)) == "prazo qua 28/10"
    assert due_text(None) == "sem prazo"
