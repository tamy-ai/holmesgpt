"""Working days in São Paulo: Monday to Friday, without national holidays."""

from __future__ import annotations

import datetime

import pytest

from tamy.chamados.common import BUSINESS_TZ as SAO_PAULO
from tamy.chamados.working_days import (
    add_working_days,
    is_working_day,
    national_holidays,
    working_days_between,
)

D = datetime.date


def _sp(year: int, month: int, day: int, hour: int = 10) -> datetime.datetime:
    return datetime.datetime(year, month, day, hour, tzinfo=SAO_PAULO)


def test_national_holidays_of_2026() -> None:
    assert national_holidays(2026) == {
        D(2026, 1, 1),
        D(2026, 4, 3),  # Sexta-feira Santa (Easter on 5/4)
        D(2026, 4, 21),
        D(2026, 5, 1),
        D(2026, 9, 7),
        D(2026, 10, 12),
        D(2026, 11, 2),
        D(2026, 11, 15),
        D(2026, 11, 20),
        D(2026, 12, 25),
    }


@pytest.mark.parametrize(
    "year, good_friday",
    [(2025, D(2025, 4, 18)), (2027, D(2027, 3, 26)), (2028, D(2028, 4, 14))],
)
def test_good_friday_follows_easter(year: int, good_friday: datetime.date) -> None:
    assert good_friday in national_holidays(year)


def test_black_consciousness_day_is_national_only_from_2024() -> None:
    """Lei 14.759/2023."""
    assert D(2023, 11, 20) not in national_holidays(2023)
    assert D(2024, 11, 20) in national_holidays(2024)


def test_carnival_is_not_a_national_holiday() -> None:
    """Carnival is an optional day off (ponto facultativo), not a law holiday:
    the SLA skips it by a choice (SLA_DAYS_OFF), not by the law list."""
    assert D(2026, 2, 17) not in national_holidays(2026)


def test_weekend_and_holiday_are_not_working_days() -> None:
    assert not is_working_day(D(2026, 10, 24))  # Saturday
    assert not is_working_day(D(2026, 10, 25))  # Sunday
    assert not is_working_day(D(2026, 11, 2))  # Finados, Monday
    assert is_working_day(D(2026, 10, 26))


def test_one_working_day_from_friday_is_monday() -> None:
    assert add_working_days(_sp(2026, 10, 23), 1) == D(2026, 10, 26)


def test_holiday_is_skipped() -> None:
    # Friday 30/10 + 1 -> Monday 2/11 is Finados -> Tuesday 3/11.
    assert add_working_days(_sp(2026, 10, 30), 1) == D(2026, 11, 3)


def test_a_request_on_saturday_counts_from_monday() -> None:
    # Saturday 24/10: Monday 26 is day 1, so 3 days end on Wednesday 28, the
    # same as a request on Friday 23 (decision 0728).
    assert add_working_days(_sp(2026, 10, 24), 3) == D(2026, 10, 28)
    assert add_working_days(_sp(2026, 10, 23), 3) == D(2026, 10, 28)


def test_the_due_date_and_the_days_left_agree_on_a_weekend_request() -> None:
    saturday = _sp(2026, 10, 24)
    due = add_working_days(saturday, 1)

    assert working_days_between(saturday.date(), due) == 1


def test_the_date_is_the_sao_paulo_date_not_utc() -> None:
    """23:30 in São Paulo on Friday is already Saturday in UTC."""
    late_friday = datetime.datetime(2026, 10, 24, 2, 30, tzinfo=datetime.timezone.utc)

    assert add_working_days(late_friday, 1) == D(2026, 10, 26)


def test_crossing_new_year() -> None:
    # Thursday 31/12/2026 + 1 -> Friday 1/1 is a holiday -> Monday 4/1/2027.
    assert add_working_days(_sp(2026, 12, 31), 1) == D(2027, 1, 4)


def test_a_naive_datetime_is_refused() -> None:
    with pytest.raises(ValueError):
        add_working_days(datetime.datetime(2026, 10, 23, 10), 1)


def test_working_days_between_counts_only_working_days() -> None:
    from tamy.chamados.working_days import working_days_between

    # Friday 30/10 -> Tuesday 3/11 crosses a weekend and Finados (Monday 2/11).
    assert working_days_between(D(2026, 10, 30), D(2026, 11, 3)) == 1
    assert working_days_between(D(2026, 11, 3), D(2026, 10, 30)) == -1
    assert working_days_between(D(2026, 10, 26), D(2026, 10, 26)) == 0


def _walk_count(start: datetime.date, end: datetime.date) -> int:
    """The obvious day-by-day count, the reference for the closed form."""
    sign = 1
    if end < start:
        start, end, sign = end, start, -1
    count = 0
    day = start
    while day < end:
        day += datetime.timedelta(days=1)
        if is_working_day(day):
            count += 1
    return sign * count


def test_working_days_between_matches_the_day_by_day_count_over_years() -> None:
    import random

    rng = random.Random(1298)
    base = datetime.date(2023, 1, 1)
    for _ in range(400):
        start = base + datetime.timedelta(days=rng.randrange(0, 1500))
        end = base + datetime.timedelta(days=rng.randrange(0, 1500))
        assert working_days_between(start, end) == _walk_count(start, end), (
            start,
            end,
        )


def test_working_days_between_never_asks_day_by_day_if_it_is_a_working_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An overdue ticket can span years: the count is a closed form, flat in
    the length of the range, not one `is_working_day` call per day."""
    import tamy.chamados.working_days as module

    def walk(_day: datetime.date, *_args: object) -> bool:
        raise AssertionError("walked the range day by day")

    monkeypatch.setattr(module, "is_working_day", walk)

    assert working_days_between(D(2020, 1, 1), D(2026, 10, 23)) > 1600


def test_carnival_monday_and_tuesday_are_off_by_default() -> None:
    from tamy.chamados.working_days import SLA_DAYS_OFF, DayOff

    # Easter 2027 is 28/03: Carnival is 08/02 and 09/02, Ash Wednesday 10/02.
    assert SLA_DAYS_OFF == {DayOff.CARNIVAL_MONDAY, DayOff.CARNIVAL_TUESDAY}
    assert not is_working_day(D(2027, 2, 8))
    assert not is_working_day(D(2027, 2, 9))
    assert is_working_day(D(2027, 2, 10))
    # Friday before Carnival + 1 working day is Ash Wednesday.
    assert add_working_days(_sp(2027, 2, 5), 1) == D(2027, 2, 10)
    assert working_days_between(D(2027, 2, 5), D(2027, 2, 10)) == 1


def test_the_owner_can_flip_carnival_back_to_working_days() -> None:
    assert is_working_day(D(2027, 2, 8), extra=frozenset())
    assert is_working_day(D(2027, 2, 9), extra=frozenset())
