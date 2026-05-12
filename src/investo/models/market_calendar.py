"""u55 Step 1 — Hand-rolled KRX + NYSE 2026 trading calendar.

The per-segment freshness gate (``briefing/freshness.py``) needs to
answer "is the latest archive stale for *this* segment?". That
requires knowing which calendar days were trading days vs holidays.

Free, deterministic, no-dependency approach:

* **Hand-rolled static lists** of 2026 holidays for KRX and NYSE.
  Source URLs are pinned in module-level comments. Annual maintenance
  task (DEBT-D55-B) refreshes for 2027.
* **No paid calendar lib**. ``pandas-market-calendars``,
  ``tradingeconomics``, and ``trading-calendars`` are all rejected
  (NFR-002 / R10 — operating cost = 0₩).
* **No clock**. All helpers are pure ``date`` predicates; the caller
  passes ``now`` so test seams work.
* **Crypto is 24/7**. Always trading; ``is_holiday("crypto", _)`` is
  ``False`` by definition.

Sources (verify annually):

* KRX 2026 휴장일 공지: https://open.krx.co.kr/contents/OPN/01/01010000/OPN01010000.jsp
* NYSE 2026 holiday calendar: https://www.nyse.com/markets/hours-calendars

Module boundary (project rule 2): foundation only — no imports from
``sources/`` / ``briefing/`` / ``publisher/``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Final, Literal
from zoneinfo import ZoneInfo

# Segment identifier matching ``briefing.segments.MarketSegment``.
# Re-declared as a Literal here (not imported) to preserve the
# foundation-layer rule — ``models/`` does not depend on ``briefing/``.
MarketSegment = Literal["domestic-equity", "us-equity", "crypto"]


# KRX 2026 휴장일 — Korea Exchange.
#
# Cross-reference: https://open.krx.co.kr/contents/OPN/01/01010000/OPN01010000.jsp
# Verified date: 2026-05-13. Refresh annually (DEBT-D55-B).
KRX_HOLIDAYS_2026: Final[frozenset[date]] = frozenset(
    {
        date(2026, 1, 1),  # 신정
        date(2026, 2, 16),  # 설날 연휴 (월)
        date(2026, 2, 17),  # 설날 (화)
        date(2026, 2, 18),  # 설날 연휴 (수)
        date(2026, 3, 1),  # 삼일절 (일요일 — 시장 영향 없음이지만 list 보존)
        date(2026, 3, 2),  # 삼일절 대체휴일 (월)
        date(2026, 5, 5),  # 어린이날
        date(2026, 5, 25),  # 부처님오신날
        date(2026, 6, 3),  # 지방선거일 (잠정)
        date(2026, 6, 6),  # 현충일 (토)
        date(2026, 8, 15),  # 광복절 (토)
        date(2026, 8, 17),  # 광복절 대체휴일 (월)
        date(2026, 9, 24),  # 추석 연휴 (목)
        date(2026, 9, 25),  # 추석 (금)
        date(2026, 10, 3),  # 개천절 (토)
        date(2026, 10, 5),  # 개천절 대체휴일 (월)
        date(2026, 10, 9),  # 한글날 (금)
        date(2026, 12, 25),  # 성탄절 (금)
        date(2026, 12, 31),  # 연말 휴장일
    }
)


# NYSE 2026 holidays.
#
# Cross-reference: https://www.nyse.com/markets/hours-calendars
# Verified date: 2026-05-13. Refresh annually (DEBT-D55-B).
NYSE_HOLIDAYS_2026: Final[frozenset[date]] = frozenset(
    {
        date(2026, 1, 1),  # New Year's Day
        date(2026, 1, 19),  # Martin Luther King Jr. Day
        date(2026, 2, 16),  # Presidents' Day
        date(2026, 4, 3),  # Good Friday
        date(2026, 5, 25),  # Memorial Day
        date(2026, 6, 19),  # Juneteenth
        date(2026, 7, 3),  # Independence Day observed (Friday)
        date(2026, 9, 7),  # Labor Day
        date(2026, 11, 26),  # Thanksgiving
        date(2026, 12, 25),  # Christmas
    }
)


_HOLIDAYS_BY_SEGMENT: Final[dict[MarketSegment, frozenset[date]]] = {
    "domestic-equity": KRX_HOLIDAYS_2026,
    "us-equity": NYSE_HOLIDAYS_2026,
    "crypto": frozenset(),
}


_KST: Final[ZoneInfo] = ZoneInfo("Asia/Seoul")
_NY: Final[ZoneInfo] = ZoneInfo("America/New_York")
_UTC: Final[ZoneInfo] = ZoneInfo("UTC")
_SEGMENT_TZ: Final[dict[MarketSegment, ZoneInfo]] = {
    "domestic-equity": _KST,
    "us-equity": _NY,
    "crypto": _UTC,
}


def is_holiday(segment: MarketSegment, day: date) -> bool:
    """Return ``True`` iff ``day`` is a non-trading day for ``segment``.

    * Saturday and Sunday count as holidays for ``domestic-equity`` and
      ``us-equity``; ``crypto`` ignores weekends (24/7).
    * Listed exchange holidays additionally count.
    * Crypto: always ``False``.
    """
    if segment == "crypto":
        return False
    if day.weekday() >= 5:  # 5 = Sat, 6 = Sun
        return True
    return day in _HOLIDAYS_BY_SEGMENT[segment]


def is_trading_day(segment: MarketSegment, day: date) -> bool:
    """Inverse of :func:`is_holiday`."""
    return not is_holiday(segment, day)


def previous_trading_day(segment: MarketSegment, day: date) -> date:
    """Most recent trading day strictly before ``day``.

    Walks backward at most 14 days — every exchange has at least one
    trading day per fortnight, so 14 is a safe upper bound.
    """
    cursor = day - timedelta(days=1)
    for _ in range(14):
        if is_trading_day(segment, cursor):
            return cursor
        cursor -= timedelta(days=1)
    # Defensive — should never trigger for a healthy calendar.
    return cursor


def next_expected_trading_day(segment: MarketSegment, now: datetime) -> date:
    """Latest trading day the segment *should* have published for.

    For an equity segment, returns the most recent calendar date (in
    the segment's local clock) that was a trading day on or before
    ``now``. Crypto is 24/7 — returns the calendar date of ``now`` in
    UTC.

    Used by freshness gate: ``latest_archive_date >=
    next_expected_trading_day(...) - 1`` ⇒ ``fresh``.
    """
    tz = _SEGMENT_TZ[segment]
    local_now = now.astimezone(tz)
    today = local_now.date()
    if segment == "crypto":
        return today
    if is_trading_day(segment, today):
        return today
    return previous_trading_day(segment, today)


__all__ = [
    "KRX_HOLIDAYS_2026",
    "NYSE_HOLIDAYS_2026",
    "MarketSegment",
    "is_holiday",
    "is_trading_day",
    "next_expected_trading_day",
    "previous_trading_day",
]
