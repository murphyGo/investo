"""u55 Step 4 — Tests for the per-segment freshness gate."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from investo.briefing.freshness import evaluate_segment_freshness


def test_fresh_when_archive_matches_expected_today() -> None:
    now = datetime(2026, 5, 11, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    status, reason = evaluate_segment_freshness("domestic-equity", date(2026, 5, 11), now=now)
    assert status == "fresh"
    assert reason is None


def test_fresh_when_archive_is_yesterday_within_tolerance() -> None:
    # Saturday in KST — last trading day = Friday May 8.
    now = datetime(2026, 5, 9, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    status, reason = evaluate_segment_freshness("domestic-equity", date(2026, 5, 8), now=now)
    assert status == "fresh"
    assert reason is None


def test_stale_when_archive_is_too_old() -> None:
    now = datetime(2026, 5, 11, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    status, reason = evaluate_segment_freshness("domestic-equity", date(2026, 5, 4), now=now)
    assert status == "stale"
    assert reason is not None
    assert "지연" in reason


def test_stale_when_no_prior_archive() -> None:
    now = datetime(2026, 5, 11, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    status, reason = evaluate_segment_freshness("domestic-equity", None, now=now)
    assert status == "stale"
    assert reason is not None
    assert "없음" in reason


def test_us_equity_after_weekend_uses_friday_close() -> None:
    # Saturday afternoon NY — Friday's archive is fresh.
    now = datetime(2026, 5, 9, 14, 0, tzinfo=ZoneInfo("America/New_York"))
    status, _ = evaluate_segment_freshness("us-equity", date(2026, 5, 8), now=now)
    assert status == "fresh"


def test_crypto_fresh_with_today_archive() -> None:
    now = datetime(2026, 5, 11, 9, 0, tzinfo=ZoneInfo("UTC"))
    status, _ = evaluate_segment_freshness("crypto", date(2026, 5, 11), now=now)
    assert status == "fresh"


def test_crypto_stale_when_archive_two_days_old() -> None:
    now = datetime(2026, 5, 11, 9, 0, tzinfo=ZoneInfo("UTC"))
    status, reason = evaluate_segment_freshness("crypto", date(2026, 5, 9), now=now)
    assert status == "stale"
    assert reason is not None
    assert "암호화폐" in reason


def test_krx_holiday_does_not_make_segment_stale() -> None:
    # 2026-05-05 KST is 어린이날 (KRX closed). Expected = May 4 (Mon).
    # Latest archive = May 4 ⇒ fresh.
    now = datetime(2026, 5, 5, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    status, _ = evaluate_segment_freshness("domestic-equity", date(2026, 5, 4), now=now)
    assert status == "fresh"


def test_us_holiday_does_not_make_segment_stale() -> None:
    # 2026-07-03 NYSE closed (Independence Day observed). Latest = July 2.
    now = datetime(2026, 7, 3, 9, 0, tzinfo=ZoneInfo("America/New_York"))
    status, _ = evaluate_segment_freshness("us-equity", date(2026, 7, 2), now=now)
    assert status == "fresh"


def test_explicit_zero_tolerance_makes_yesterday_stale() -> None:
    now = datetime(2026, 5, 11, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    status, _ = evaluate_segment_freshness(
        "domestic-equity", date(2026, 5, 8), now=now, tolerance_days=0
    )
    assert status == "stale"
