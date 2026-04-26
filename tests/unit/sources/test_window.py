"""Unit + property-based tests for ``investo.sources._window.FetchWindow``.

Pins NFR-006 acceptance criteria AC-6.1 (window invariants) and
AC-6.2 (half-open membership) from
``aidlc-docs/construction/u1-sources/nfr-requirements/nfr-requirements.md``.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from investo.sources._window import FetchWindow

_KST = ZoneInfo("Asia/Seoul")
_PBT_SETTINGS = settings(max_examples=100, deadline=None)


# ---------------------------------------------------------------------------
# Construction + invariants
# ---------------------------------------------------------------------------


def test_from_kst_date_known_case() -> None:
    # Anchor case: the KST trading date 2026-04-27 covers UTC
    # [2026-04-26 15:00, 2026-04-27 15:00).
    window = FetchWindow.from_kst_date(date(2026, 4, 27))
    assert window.target_date == date(2026, 4, 27)
    assert window.start_utc == datetime(2026, 4, 26, 15, 0, tzinfo=UTC)
    assert window.end_utc == datetime(2026, 4, 27, 15, 0, tzinfo=UTC)


def test_window_span_is_24h() -> None:
    window = FetchWindow.from_kst_date(date(2026, 1, 15))
    assert window.end_utc - window.start_utc == timedelta(days=1)


def test_window_is_frozen() -> None:
    window = FetchWindow.from_kst_date(date(2026, 4, 27))
    with pytest.raises(FrozenInstanceError):
        window.target_date = date(2026, 4, 28)  # type: ignore[misc]


def test_naive_start_utc_rejected() -> None:
    with pytest.raises(ValueError, match="start_utc must be timezone-aware"):
        FetchWindow(
            start_utc=datetime(2026, 4, 27, 0, 0),
            end_utc=datetime(2026, 4, 28, 0, 0, tzinfo=UTC),
            target_date=date(2026, 4, 27),
        )


def test_naive_end_utc_rejected() -> None:
    with pytest.raises(ValueError, match="end_utc must be timezone-aware"):
        FetchWindow(
            start_utc=datetime(2026, 4, 27, 0, 0, tzinfo=UTC),
            end_utc=datetime(2026, 4, 28, 0, 0),
            target_date=date(2026, 4, 27),
        )


def test_inverted_range_rejected() -> None:
    with pytest.raises(ValueError, match="end_utc must be strictly after start_utc"):
        FetchWindow(
            start_utc=datetime(2026, 4, 28, 0, 0, tzinfo=UTC),
            end_utc=datetime(2026, 4, 27, 0, 0, tzinfo=UTC),
            target_date=date(2026, 4, 27),
        )


def test_zero_length_window_rejected() -> None:
    instant = datetime(2026, 4, 27, 0, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="end_utc must be strictly after start_utc"):
        FetchWindow(start_utc=instant, end_utc=instant, target_date=date(2026, 4, 27))


# ---------------------------------------------------------------------------
# contains() — half-open membership (AC-6.2 anchor cases)
# ---------------------------------------------------------------------------


def test_contains_start_inclusive() -> None:
    window = FetchWindow.from_kst_date(date(2026, 4, 27))
    assert window.contains(window.start_utc) is True


def test_contains_end_exclusive() -> None:
    window = FetchWindow.from_kst_date(date(2026, 4, 27))
    assert window.contains(window.end_utc) is False


def test_contains_one_microsecond_before_end() -> None:
    window = FetchWindow.from_kst_date(date(2026, 4, 27))
    just_before = window.end_utc - timedelta(microseconds=1)
    assert window.contains(just_before) is True


def test_contains_outside_returns_false() -> None:
    window = FetchWindow.from_kst_date(date(2026, 4, 27))
    earlier = window.start_utc - timedelta(seconds=1)
    later = window.end_utc + timedelta(seconds=1)
    assert window.contains(earlier) is False
    assert window.contains(later) is False


def test_contains_naive_datetime_rejected() -> None:
    window = FetchWindow.from_kst_date(date(2026, 4, 27))
    with pytest.raises(ValueError, match="dt must be timezone-aware"):
        window.contains(datetime(2026, 4, 27, 0, 0))


def test_contains_kst_timestamp_inside() -> None:
    # A KST timestamp midway through the trading date should be inside.
    window = FetchWindow.from_kst_date(date(2026, 4, 27))
    midday_kst = datetime(2026, 4, 27, 12, 0, tzinfo=_KST)
    assert window.contains(midday_kst) is True


# ---------------------------------------------------------------------------
# Property-based: NFR-006 AC-6.1 — window invariants
# ---------------------------------------------------------------------------


@given(
    st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31)),
)
@_PBT_SETTINGS
def test_property_window_invariants(target_date: date) -> None:
    window = FetchWindow.from_kst_date(target_date)
    # Both bounds tz-aware
    assert window.start_utc.tzinfo is not None
    assert window.end_utc.tzinfo is not None
    # Strictly ordered
    assert window.start_utc < window.end_utc
    # Span is exactly 24 hours
    assert window.end_utc - window.start_utc == timedelta(days=1)
    # target_date is preserved
    assert window.target_date == target_date


# ---------------------------------------------------------------------------
# Property-based: NFR-006 AC-6.2 — half-open membership
# ---------------------------------------------------------------------------


@given(
    target_date=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
    sample_dt=st.datetimes(
        min_value=datetime(2019, 1, 1),
        max_value=datetime(2031, 12, 31),
        timezones=st.timezones(),
    ).filter(lambda d: d.tzinfo is not None and d.tzinfo.utcoffset(d) is not None),
)
@_PBT_SETTINGS
def test_property_contains_membership(target_date: date, sample_dt: datetime) -> None:
    window = FetchWindow.from_kst_date(target_date)
    expected = window.start_utc <= sample_dt < window.end_utc
    assert window.contains(sample_dt) is expected


# ---------------------------------------------------------------------------
# Date arithmetic edge cases
# ---------------------------------------------------------------------------


def test_year_boundary_kst_date() -> None:
    # KST 2026-01-01 covers UTC [2025-12-31 15:00, 2026-01-01 15:00).
    window = FetchWindow.from_kst_date(date(2026, 1, 1))
    assert window.start_utc == datetime(2025, 12, 31, 15, 0, tzinfo=UTC)
    assert window.end_utc == datetime(2026, 1, 1, 15, 0, tzinfo=UTC)


def test_leap_day_window() -> None:
    # 2024-02-29 is a leap day; the window math still produces 24h.
    window = FetchWindow.from_kst_date(date(2024, 2, 29))
    assert window.end_utc - window.start_utc == timedelta(days=1)
    assert window.start_utc == datetime(2024, 2, 28, 15, 0, tzinfo=UTC)


def test_fixed_offset_tz_in_contains() -> None:
    # A fixed-offset (non-zoneinfo) tz still satisfies the membership check.
    window = FetchWindow.from_kst_date(date(2026, 4, 27))
    seven_hour_offset = datetime(2026, 4, 27, 8, 0, tzinfo=timezone(timedelta(hours=7)))
    # 08:00 +07:00 = 01:00 UTC on the same calendar day; window covers
    # 2026-04-26 15:00 UTC -> 2026-04-27 15:00 UTC, so this is inside.
    assert window.contains(seven_hour_offset) is True


# ---------------------------------------------------------------------------
# Boundary-date overflow (M1 fix from review)
# ---------------------------------------------------------------------------


def test_from_kst_date_min_raises_value_error() -> None:
    # date.min combined with KST midnight then astimezone(UTC) underflows
    # to year 0 — Python raises OverflowError, which the wrapper translates.
    with pytest.raises(ValueError, match="out of supported range"):
        FetchWindow.from_kst_date(date.min)


def test_from_kst_date_max_raises_value_error() -> None:
    # date.max + 1 day overflows to year 10000.
    with pytest.raises(ValueError, match="out of supported range"):
        FetchWindow.from_kst_date(date.max)


# ---------------------------------------------------------------------------
# Hostile tzinfo subclass (L2 fix from review)
# ---------------------------------------------------------------------------


class _RaisingTZ(tzinfo):
    """A pathological tzinfo whose utcoffset always raises."""

    def utcoffset(self, dt: datetime | None) -> timedelta | None:
        raise RuntimeError("synthetic tzinfo failure")

    def dst(self, dt: datetime | None) -> timedelta | None:
        return None

    def tzname(self, dt: datetime | None) -> str:
        return "RAISING"


def test_contains_raising_tzinfo_surfaces_as_value_error() -> None:
    window = FetchWindow.from_kst_date(date(2026, 4, 27))
    bad_dt = datetime(2026, 4, 27, 12, 0, tzinfo=_RaisingTZ())
    with pytest.raises(ValueError, match="tzinfo failed to resolve offset"):
        window.contains(bad_dt)


def test_construction_raising_tzinfo_surfaces_as_value_error() -> None:
    with pytest.raises(ValueError, match="tzinfo failed to resolve offset"):
        FetchWindow(
            start_utc=datetime(2026, 4, 27, 0, 0, tzinfo=_RaisingTZ()),
            end_utc=datetime(2026, 4, 28, 0, 0, tzinfo=UTC),
            target_date=date(2026, 4, 27),
        )
