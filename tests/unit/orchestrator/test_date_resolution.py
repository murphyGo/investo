"""Tests for ``investo.orchestrator.date_resolution.resolve_target_date``.

Pins AC-005-1 (KST 평일 cron → previous US trading day), AC-005-2
(KST Saturday cron → Friday), and AC-005-3 (no US trading calendar
consultation — holidays surface via empty-collect).

Plus a ≥100-example hypothesis PBT per AC-006-4 asserting the
post-condition holds across a multi-year domain.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from investo.orchestrator.date_resolution import resolve_target_date, validate_target_date_sanity

_KST = ZoneInfo("Asia/Seoul")


def _kst(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    """Construct a KST-aware datetime."""
    return datetime(year, month, day, hour, minute, tzinfo=_KST)


# ---------------------------------------------------------------------------
# AC-005-1 — KST weekday morning cron → previous US trading day
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kst_dt", "expected_target"),
    [
        # KST Tue 07:00 → Mon (US Mon close)
        (_kst(2026, 4, 28, 7), date(2026, 4, 27)),
        # KST Wed 07:00 → Tue
        (_kst(2026, 4, 29, 7), date(2026, 4, 28)),
        # KST Thu 07:00 → Wed
        (_kst(2026, 4, 30, 7), date(2026, 4, 29)),
        # KST Fri 07:00 → Thu
        (_kst(2026, 5, 1, 7), date(2026, 4, 30)),
        # KST Mon 07:00 → previous Fri (skip weekend)
        (_kst(2026, 4, 27, 7), date(2026, 4, 24)),
    ],
    ids=["tue-to-mon", "wed-to-tue", "thu-to-wed", "fri-to-thu", "mon-to-fri"],
)
def test_resolve_target_date_weekday_kst_morning(kst_dt: datetime, expected_target: date) -> None:
    target = resolve_target_date(kst_dt.astimezone(UTC))
    assert target == expected_target
    # Always a weekday under the default flag.
    assert target.weekday() < 5


# ---------------------------------------------------------------------------
# AC-005-2 — KST Saturday morning cron → Friday
# ---------------------------------------------------------------------------


def test_resolve_target_date_saturday_kst_morning_returns_friday() -> None:
    """KST Sat 09:00 cron fires for Friday's US session."""
    saturday_kst = _kst(2026, 4, 25, 9)
    assert saturday_kst.weekday() == 5  # sanity
    target = resolve_target_date(saturday_kst.astimezone(UTC))
    assert target == date(2026, 4, 24)
    assert target.weekday() == 4  # Friday


def test_resolve_target_date_sunday_kst_morning_walks_back_to_friday() -> None:
    """KST Sun (manual trigger only) → walks back through Saturday to
    the prior Friday (2 iterations of the weekend-skip loop).
    """
    sunday_kst = _kst(2026, 4, 26, 9)
    assert sunday_kst.weekday() == 6  # sanity
    target = resolve_target_date(sunday_kst.astimezone(UTC))
    assert target == date(2026, 4, 24)
    assert target.weekday() == 4


# ---------------------------------------------------------------------------
# AC-005-3 — no US trading calendar consultation
# ---------------------------------------------------------------------------


def test_resolve_target_date_returns_us_holiday_date_unchanged() -> None:
    """KST Fri 2026-07-03 07:00 cron fires for "Thu 2026-07-02 KST", but
    the US market was closed on Thu 2026-07-03 EDT (Independence Day
    observed). The function still returns the calendar date 2026-07-02 —
    no holiday calendar consultation. The pipeline's empty-collect path
    routes this to operator alert (AC-003-2).

    This pinning test documents the deliberate non-consultation per
    Q3=A so that any future "let's just add ``pandas_market_calendars``"
    PR has to delete this test.
    """
    fri_kst = _kst(2026, 7, 3, 7)
    target = resolve_target_date(fri_kst.astimezone(UTC))
    # Thursday 2026-07-02 — calendar date returned unconditionally.
    assert target == date(2026, 7, 2)
    assert target.weekday() == 3  # Thursday


# ---------------------------------------------------------------------------
# UTC input + boundary cases
# ---------------------------------------------------------------------------


def test_resolve_target_date_accepts_utc_input() -> None:
    """The cron passes ``datetime.now(UTC)`` directly — verify the UTC →
    KST conversion uses the +9 offset.
    """
    # KST Tue 2026-04-28 07:00 == UTC Mon 2026-04-27 22:00.
    utc_dt = datetime(2026, 4, 27, 22, 0, tzinfo=UTC)
    target = resolve_target_date(utc_dt)
    # KST date is 2026-04-28 (Tue) → previous day = Mon 2026-04-27.
    assert target == date(2026, 4, 27)


def test_resolve_target_date_naive_datetime_rejected() -> None:
    """Naive datetimes are rejected at the type boundary."""
    naive = datetime(2026, 4, 28, 7, 0)
    with pytest.raises(ValueError, match="timezone-aware"):
        resolve_target_date(naive)


def test_validate_target_date_sanity_accepts_supported_date() -> None:
    assert validate_target_date_sanity(date(2026, 4, 27), today_utc=date(2026, 5, 3)) == date(
        2026, 4, 27
    )


def test_validate_target_date_sanity_rejects_pre_project_date() -> None:
    with pytest.raises(ValueError, match="out of supported range"):
        validate_target_date_sanity(date(2023, 12, 31), today_utc=date(2026, 5, 3))


def test_validate_target_date_sanity_rejects_far_future_date() -> None:
    with pytest.raises(ValueError, match="2026-05-04"):
        validate_target_date_sanity(date(2026, 5, 5), today_utc=date(2026, 5, 3))


def test_resolve_target_date_year_boundary() -> None:
    """KST 2026-01-01 (Thu) 07:00 → Wed 2025-12-31."""
    new_year_kst = _kst(2026, 1, 1, 7)
    assert new_year_kst.weekday() == 3  # Thu
    target = resolve_target_date(new_year_kst.astimezone(UTC))
    assert target == date(2025, 12, 31)
    assert target.weekday() == 2  # Wed


def test_resolve_target_date_year_boundary_monday() -> None:
    """KST 2026-01-05 (Mon) 07:00 → Fri 2026-01-02 (skip weekend)."""
    monday_kst = _kst(2026, 1, 5, 7)
    assert monday_kst.weekday() == 0
    target = resolve_target_date(monday_kst.astimezone(UTC))
    assert target == date(2026, 1, 2)
    assert target.weekday() == 4  # Fri


def test_resolve_target_date_kst_no_dst_quirks() -> None:
    """Asia/Seoul is fixed UTC+9 (no DST since 1988) — pin that the
    function behaves identically across what would be DST boundaries
    in DST-observing zones (March / November in US/Eastern).
    """
    # March 8 2026 (US DST spring-forward) — KST is unaffected.
    march_kst = _kst(2026, 3, 8, 7)  # Sun
    target_march = resolve_target_date(march_kst.astimezone(UTC))
    # Sun walks back through Sat to Fri (2026-03-06).
    assert target_march == date(2026, 3, 6)
    assert target_march.weekday() == 4

    # November 1 2026 (US DST fall-back) — KST unaffected.
    nov_kst = _kst(2026, 11, 1, 9)  # Sun
    target_nov = resolve_target_date(nov_kst.astimezone(UTC))
    # Sun → Fri 2026-10-30.
    assert target_nov == date(2026, 10, 30)
    assert target_nov.weekday() == 4


# ---------------------------------------------------------------------------
# weekday_only_us_close=False — manual override path
# ---------------------------------------------------------------------------


def test_resolve_target_date_weekday_flag_false_returns_raw_yesterday() -> None:
    """When the flag is off, return ``kst_today - 1 day`` even if the
    result is a weekend. Useful for manual workflow_dispatch
    investigations that want to inspect a specific KST date.
    """
    saturday_kst = _kst(2026, 4, 25, 9)
    target = resolve_target_date(saturday_kst.astimezone(UTC), weekday_only_us_close=False)
    # Without weekend skip: Saturday → Friday is still 4-24, but on a
    # Sunday the result would be Saturday. Pick the Sunday case to make
    # the difference observable.
    sunday_kst = _kst(2026, 4, 26, 9)
    raw = resolve_target_date(sunday_kst.astimezone(UTC), weekday_only_us_close=False)
    assert target == date(2026, 4, 24)  # Sat → Fri (raw is also Fri here)
    assert raw == date(2026, 4, 25)  # Sun → Sat (weekend allowed)
    assert raw.weekday() == 5  # Saturday


def test_resolve_target_date_weekday_flag_default_is_true() -> None:
    """The default is ``True`` (cron path) — Sunday → Friday, not Sat."""
    sunday_kst = _kst(2026, 4, 26, 9)
    default_result = resolve_target_date(sunday_kst.astimezone(UTC))
    explicit_true = resolve_target_date(sunday_kst.astimezone(UTC), weekday_only_us_close=True)
    assert default_result == explicit_true == date(2026, 4, 24)


# ---------------------------------------------------------------------------
# AC-006-4 — hypothesis PBT (≥100 examples)
# ---------------------------------------------------------------------------


@given(
    st.datetimes(
        min_value=datetime(2024, 1, 1),
        max_value=datetime(2030, 12, 31, 23, 59),
        timezones=st.just(UTC),
    )
)
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_resolve_target_date_pbt_post_condition(now_utc: datetime) -> None:
    """For any UTC instant from 2024 through 2030, the returned date must:

    1. Be a weekday (Mon-Fri) — AC-005-3 + default flag.
    2. Be strictly less than the KST calendar date of ``now_utc``.
    3. Be at most 3 days before the KST date (Mon → prev Fri = 3-day
       gap is the maximum; any larger gap signals a bug).
    """
    target = resolve_target_date(now_utc)
    kst_today = now_utc.astimezone(_KST).date()

    # Post-condition 1: always a weekday.
    assert target.weekday() < 5, f"target {target} ({target.strftime('%A')}) is not a weekday"

    # Post-condition 2: strictly less than KST today.
    assert target < kst_today

    # Post-condition 3: at most 3 days back.
    assert (kst_today - target) <= timedelta(days=3)


@given(
    st.datetimes(
        min_value=datetime(2024, 1, 1),
        max_value=datetime(2030, 12, 31, 23, 59),
        timezones=st.just(UTC),
    )
)
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_resolve_target_date_pbt_raw_yesterday_with_flag_false(
    now_utc: datetime,
) -> None:
    """When the weekday-skip flag is off, the result is exactly
    ``kst_today - 1 day``, regardless of weekday/weekend.
    """
    target = resolve_target_date(now_utc, weekday_only_us_close=False)
    kst_today = now_utc.astimezone(_KST).date()
    assert target == kst_today - timedelta(days=1)
