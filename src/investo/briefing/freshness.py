"""u55 Step 4 — Per-segment freshness evaluation.

The freshness gate answers: "given the latest archive date and today's
calendar expectation, should this segment publish?".

Decision rule:

* **Equity** (``domestic-equity`` / ``us-equity``): expected publish day
  is :func:`investo.models.market_calendar.next_expected_trading_day`.
  Latest archive ``>= expected_day - 1`` ⇒ ``fresh``; otherwise
  ``stale``. The 1-day tolerance absorbs the cron-vs-market-close gap
  (KRX cron fires at 07:00 KST for *yesterday's* US close).
* **Crypto** (``24/7``): expected publish day = today (UTC). Latest
  archive ``>= today - 1`` ⇒ ``fresh``; otherwise ``stale``. The crypto
  channel does not skip weekends.

Pure helper. No clock. Caller supplies ``now`` so test seams work.

Module boundary: imports only from :mod:`investo.models`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from investo.models.market_calendar import MarketSegment, next_expected_trading_day
from investo.models.segment_result import SegmentStatus


def evaluate_segment_freshness(
    segment: MarketSegment,
    latest_archive_date: date | None,
    *,
    now: datetime,
    tolerance_days: int = 1,
) -> tuple[SegmentStatus, str | None]:
    """Return ``(status, reason)`` for the segment.

    ``status == "fresh"`` ⇒ ``reason is None``; otherwise the human-
    readable Korean line for the quality page.

    Parameters
    ----------
    segment:
        Which calendar to consult.
    latest_archive_date:
        Most recent archive markdown date for this segment. ``None``
        when the segment has no prior archive (greenfield first-run);
        treated as stale.
    now:
        Reference clock — the caller passes ``target_date`` reified to
        a datetime, never reads system time inside this helper.
    tolerance_days:
        How many days behind ``next_expected_trading_day(...)`` we still
        accept as fresh. Default 1 (absorbs cron-vs-close gap).
    """
    expected = next_expected_trading_day(segment, now)
    if latest_archive_date is None:
        return "stale", _stale_reason(segment, expected, None)
    cutoff = expected - timedelta(days=tolerance_days)
    if latest_archive_date >= cutoff:
        return "fresh", None
    return "stale", _stale_reason(segment, expected, latest_archive_date)


def _stale_reason(segment: MarketSegment, expected: date, latest: date | None) -> str:
    label = {"domestic-equity": "국내", "us-equity": "미국", "crypto": "암호화폐"}[segment]
    if latest is None:
        return f"{label} 세그먼트 아카이브 없음 (기대일: {expected.isoformat()})"
    return (
        f"{label} 세그먼트 최신 아카이브 {latest.isoformat()} — "
        f"기대일 {expected.isoformat()} 대비 지연"
    )


__all__ = ["evaluate_segment_freshness"]
