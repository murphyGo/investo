"""Versioned 2026 source calendars; observation dates are never publish instants.

Evidence: NY Fed holiday_schedule.html and operating_policy_260618a;
Federal Reserve releases/h10; Treasury daily treasury rate FAQ.
Unsupported years deliberately return unknown. No NYSE calendar reuse.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from investo.models.insights import CalendarPolicy

NY = ZoneInfo("America/New_York")
_BASE = frozenset(
    date(2026, m, d)
    for m, d in (
        (1, 1),
        (1, 19),
        (2, 16),
        (5, 25),
        (6, 19),
        (9, 7),
        (10, 12),
        (11, 11),
        (11, 26),
        (12, 25),
    )
)
FEDERAL = _BASE | {date(2026, 7, 3)}
# Fed banks do not observe a Saturday holiday on the preceding Friday.
EFFR = _BASE
SOFR = FEDERAL | {date(2026, 4, 3)}
TREASURY = SOFR


def business_day(day: date, policy: CalendarPolicy) -> bool | None:
    if day.year != 2026 or policy == "none":
        return None
    holidays = (
        EFFR
        if policy == "effr"
        else SOFR
        if policy == "sofr"
        else TREASURY
        if policy == "treasury"
        else FEDERAL
    )
    return day.weekday() < 5 and day not in holidays


def previous_business_day(day: date, policy: CalendarPolicy) -> date | None:
    for _ in range(15):
        day -= timedelta(days=1)
        allowed = business_day(day, policy)
        if allowed is None:
            return None
        if allowed:
            return day
    return None


def business_lag(start: date, end: date, policy: CalendarPolicy) -> int | None:
    if start > end or start.year != 2026 or end.year != 2026 or policy == "none":
        return None
    count = 0
    while start < end:
        start += timedelta(days=1)
        count += bool(business_day(start, policy))
    return count


def expected_observation(now: datetime, policy: CalendarPolicy) -> date | None:
    local = now.astimezone(NY)
    if local.year != 2026 or policy in {"none", "federal"}:
        return None
    if policy == "h10":
        monday = local.date() - timedelta(days=local.weekday())
        for _ in range(3):
            release_day = monday
            while business_day(release_day, "federal") is False:
                release_day += timedelta(days=1)
            if business_day(release_day, "federal") is None:
                return None
            release_at = datetime.combine(release_day, time(16, 15), NY)
            if release_at <= local:
                return previous_business_day(monday, "federal")
            monday -= timedelta(days=7)
        return None
    publish_time = time(8) if policy == "sofr" else time(9) if policy == "effr" else time(18)
    publication_day: date | None = local.date()
    if not business_day(local.date(), policy) or local.time() < publish_time:
        publication_day = previous_business_day(local.date(), policy)
    if publication_day is None:
        return None
    return (
        publication_day if policy == "treasury" else previous_business_day(publication_day, policy)
    )
