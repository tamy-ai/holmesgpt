"""Working days (dias úteis) in São Paulo. One definition.

This is not the restaurant business day of `tamy.chamados.common`, which is the day
a sale belongs to. A working day here is Monday to Friday, without national
holidays, the calendar the team's SLA counts in (decision 0728).

National holidays by law: Lei 662/1949 and 6.802/1980, Lei 14.759/2023 (20/11
since 2024), and Good Friday, which moves with Easter. Carnival Monday and
Tuesday are not law holidays, but the SLA skips them by the owner's choice
(`SLA_DAYS_OFF`). Corpus Christi counts as a working day.
"""

from __future__ import annotations

import datetime
from enum import StrEnum
from functools import cache

from dateutil.easter import easter

from tamy.chamados.common import business_date

_FIXED_HOLIDAYS: tuple[tuple[int, int], ...] = (
    (1, 1),  # Confraternização Universal
    (4, 21),  # Tiradentes
    (5, 1),  # Dia do Trabalho
    (9, 7),  # Independência
    (10, 12),  # Nossa Senhora Aparecida
    (11, 2),  # Finados
    (11, 15),  # Proclamação da República
    (12, 25),  # Natal
)
_BLACK_CONSCIOUSNESS_FIRST_YEAR = 2024


class DayOff(StrEnum):
    """A day off beyond the law, placed by its distance to Easter."""

    CARNIVAL_MONDAY = "carnival_monday"
    CARNIVAL_TUESDAY = "carnival_tuesday"


_DAYS_BEFORE_EASTER: dict[DayOff, int] = {
    DayOff.CARNIVAL_MONDAY: 48,
    DayOff.CARNIVAL_TUESDAY: 47,
}

# The days off beyond the law that the SLA calendar skips. ONE value, a choice
# the owner can flip (decision 0728): most Brazilian companies stop on
# Carnival Monday and Tuesday, though the law does not make them holidays.
SLA_DAYS_OFF: frozenset[DayOff] = frozenset(
    {DayOff.CARNIVAL_MONDAY, DayOff.CARNIVAL_TUESDAY}
)


@cache
def national_holidays(year: int) -> frozenset[datetime.date]:
    days = {datetime.date(year, month, day) for month, day in _FIXED_HOLIDAYS}
    days.add(easter(year) - datetime.timedelta(days=2))  # Sexta-feira Santa
    if year >= _BLACK_CONSCIOUSNESS_FIRST_YEAR:
        days.add(datetime.date(year, 11, 20))
    return frozenset(days)


@cache
def days_off(
    year: int, extra: frozenset[DayOff] = SLA_DAYS_OFF
) -> frozenset[datetime.date]:
    """The national holidays of `year`, plus the chosen days off beyond the law."""
    moving = {
        easter(year) - datetime.timedelta(days=_DAYS_BEFORE_EASTER[day])
        for day in extra
    }
    return national_holidays(year) | moving


def is_working_day(day: datetime.date, extra: frozenset[DayOff] = SLA_DAYS_OFF) -> bool:
    return day.weekday() < 5 and day not in days_off(day.year, extra)


def sao_paulo_date(moment: datetime.datetime) -> datetime.date:
    """`dates.business_date`, refusing a naive datetime: a deadline counted
    from the host's local time would be off by hours."""
    if moment.tzinfo is None:
        raise ValueError("a working-day count needs an aware datetime")
    return business_date(moment)


def add_working_days(start: datetime.datetime, days: int) -> datetime.date:
    """The date `days` working days after `start`, in São Paulo.

    A request on a weekend or a holiday counts the next working day as day 1,
    so it gets the same due date as one on the working day before it.
    """
    day = sao_paulo_date(start)
    remaining = days
    while remaining > 0:
        day += datetime.timedelta(days=1)
        if is_working_day(day):
            remaining -= 1
    return day


def _weekdays_after(start: datetime.date, end: datetime.date) -> int:
    """Monday to Friday after `start` up to and including `end` (`end >= start`)."""
    days = (end - start).days
    count = days // 7 * 5
    weekday = start.weekday()
    for _ in range(days % 7):
        weekday = (weekday + 1) % 7
        if weekday < 5:
            count += 1
    return count


def working_days_between(start: datetime.date, end: datetime.date) -> int:
    """Working days after `start` up to and including `end`; negative when
    `end` is before `start`. The queue reads it as "vence em N dias úteis".

    Closed form, flat in the length of the range: the queue calls it once per
    row, and an old overdue ticket spans years."""
    if end < start:
        return -working_days_between(end, start)
    holidays = sum(
        1
        for year in range(start.year, end.year + 1)
        for day in days_off(year)
        if start < day <= end and day.weekday() < 5
    )
    return _weekdays_after(start, end) - holidays
