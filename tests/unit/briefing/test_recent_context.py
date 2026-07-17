"""Tests for u34 ``investo.briefing.context``.

Pins:

* archive walk skips weekends (R-hint: weekday-only count),
* ``N=0`` and ``segments=()`` short-circuit cleanly,
* missing archive directory yields empty context (first-publish path),
* per-day truncation cap (50 chars) keeps prompt budget bounded,
* defensive STRICT-policy redaction strips secret-shaped substrings
  even if a future archive bypassed publish-time leak guards (R13),
* env-var resolver clamps invalid / out-of-range values to default.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pytest

from investo.briefing.context import (
    DEFAULT_RECENT_DAYS,
    ENV_RECENT_DAYS,
    MAX_RECENT_DAYS,
    RecentBriefingEntry,
    RecentBriefingsContext,
    load_recent_briefings,
    resolve_recent_days,
)
from investo.briefing.pipeline import _render_timestamp_watermark
from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY, MarketSegment

_ALL_SEGMENTS: tuple[MarketSegment, ...] = (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)


def _write_archive(
    archive_root: Path,
    segment: MarketSegment,
    day: date,
    *,
    conclusion: str = "테스트 결론",
    drivers: str = "테스트 동인",
    watermark: str | None = None,
    extra_body: str = "본문 생략",
) -> Path:
    """Write a minimal archive markdown file mirroring publisher output."""
    folder = archive_root / segment / f"{day.year:04d}" / f"{day.month:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{day.isoformat()}.md"
    watermark_line = (
        _render_timestamp_watermark(day, segment)
        if watermark is None
        else f"**기준 시각**: {watermark}"
    )
    body = (
        f"# {day.isoformat()} 시황\n\n"
        f"{watermark_line}\n\n"
        f"> **오늘의 결론**: {conclusion}\n"
        f"> **핵심 동인**: {drivers}\n"
        f"> **주의할 점**: 주의\n\n"
        f"## ① 요약\n\n{extra_body}\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# load_recent_briefings
# ---------------------------------------------------------------------------


def test_load_returns_empty_context_when_archive_root_missing(tmp_path: Path) -> None:
    target = date(2026, 5, 8)  # Fri
    context = load_recent_briefings(tmp_path / "missing", target, days=5)

    assert isinstance(context, RecentBriefingsContext)
    assert context.is_empty()
    assert context.target_date == target
    assert context.days == 5
    for segment in _ALL_SEGMENTS:
        assert context.for_segment(segment) == ()


def test_load_returns_empty_context_when_days_is_zero(tmp_path: Path) -> None:
    target = date(2026, 5, 8)
    _write_archive(tmp_path, US_EQUITY, date(2026, 5, 7))

    context = load_recent_briefings(tmp_path, target, days=0)

    assert context.days == 0
    assert context.is_empty()


def test_load_pulls_one_entry_per_segment_for_yesterday(tmp_path: Path) -> None:
    target = date(2026, 5, 8)  # Fri → look back to Thu
    yesterday = date(2026, 5, 7)
    for segment in _ALL_SEGMENTS:
        _write_archive(
            tmp_path,
            segment,
            yesterday,
            conclusion=f"{segment} 결론",
            drivers=f"{segment} 동인",
        )

    context = load_recent_briefings(tmp_path, target, days=1)

    assert not context.is_empty()
    for segment in _ALL_SEGMENTS:
        entries = context.for_segment(segment)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.publish_date == yesterday
        assert entry.segment == segment
        assert entry.conclusion == f"{segment} 결론"
        assert entry.key_drivers == f"{segment} 동인"
        produced_watermark = _render_timestamp_watermark(yesterday, segment).removeprefix(
            "**기준 시각**: "
        )
        assert len(entry.watermark) == 50
        assert entry.watermark.endswith("…")
        assert produced_watermark.startswith(entry.watermark.removesuffix("…"))


def test_load_walks_back_n_weekdays_skipping_weekends(tmp_path: Path) -> None:
    """Mon target → load 5 trailing weekdays = prev Mon … prev Fri.

    target Mon 2026-05-11 → prev Fri 2026-05-08, Thu 5/7, Wed 5/6,
    Tue 5/5, Mon 5/4 (Sat 5/9 / Sun 5/10 skipped).
    """
    target = date(2026, 5, 11)  # Mon
    expected_days = [
        date(2026, 5, 8),  # Fri
        date(2026, 5, 7),  # Thu
        date(2026, 5, 6),  # Wed
        date(2026, 5, 5),  # Tue
        date(2026, 5, 4),  # Mon
    ]
    weekend_day = date(2026, 5, 10)  # Sun (should be skipped even if present)

    for day in [*expected_days, weekend_day]:
        _write_archive(tmp_path, US_EQUITY, day, conclusion=f"결론-{day.isoformat()}")

    context = load_recent_briefings(tmp_path, target, days=5)

    entries = context.for_segment(US_EQUITY)
    assert [e.publish_date for e in entries] == expected_days  # newest-first
    assert all(weekend_day != e.publish_date for e in entries)


def test_load_tolerates_gap_days(tmp_path: Path) -> None:
    """Missing archive on a weekday is silently skipped."""
    target = date(2026, 5, 11)  # Mon
    # Only Fri 5/8 and Wed 5/6 archived; Thu 5/7 / Tue 5/5 / Mon 5/4 missing.
    _write_archive(tmp_path, US_EQUITY, date(2026, 5, 8))
    _write_archive(tmp_path, US_EQUITY, date(2026, 5, 6))

    context = load_recent_briefings(tmp_path, target, days=5)

    entries = context.for_segment(US_EQUITY)
    assert [e.publish_date for e in entries] == [date(2026, 5, 8), date(2026, 5, 6)]


def test_load_truncates_long_fields(tmp_path: Path) -> None:
    """Per-day char budget caps each field at 50 chars (with ellipsis)."""
    target = date(2026, 5, 8)
    long_conclusion = "가" * 200
    long_drivers = "나" * 200
    _write_archive(
        tmp_path,
        US_EQUITY,
        date(2026, 5, 7),
        conclusion=long_conclusion,
        drivers=long_drivers,
    )

    context = load_recent_briefings(tmp_path, target, days=1)
    entry = context.for_segment(US_EQUITY)[0]

    assert len(entry.conclusion) <= 50
    assert entry.conclusion.endswith("…")
    assert len(entry.key_drivers) <= 50


def test_load_redacts_secret_shaped_substrings(tmp_path: Path) -> None:
    """Defensive STRICT-policy redaction strips secret shapes (R13)."""
    target = date(2026, 5, 8)
    # Use shorter strings so the conclusion isn't truncated before
    # we can observe the redaction. AKIA + 16 alphanumerics is the
    # canonical AWS key shape; the redaction marker is shorter than
    # the original so the field still fits the 50-char budget.
    leaky_conclusion = "키 노출 AKIAABCDEFGHIJKLMNOP 확인"
    _write_archive(
        tmp_path,
        US_EQUITY,
        date(2026, 5, 7),
        conclusion=leaky_conclusion,
        drivers="정상 동인",
    )

    context = load_recent_briefings(tmp_path, target, days=1)
    entry = context.for_segment(US_EQUITY)[0]

    assert "AKIA" not in entry.conclusion
    assert "[REDACTED_AWS_KEY]" in entry.conclusion


def test_load_skips_entry_when_both_signal_fields_empty(tmp_path: Path) -> None:
    """Watermark-only archives produce no entry (no narrative value)."""
    target = date(2026, 5, 8)
    folder = tmp_path / US_EQUITY / "2026" / "05"
    folder.mkdir(parents=True)
    # Watermark present, but no conclusion / driver lines.
    (folder / "2026-05-07.md").write_text(
        "# 2026-05-07 시황\n\n"
        f"{_render_timestamp_watermark(date(2026, 5, 7), US_EQUITY)}\n\n"
        "## ① 요약\n\n빈 본문\n",
        encoding="utf-8",
    )

    context = load_recent_briefings(tmp_path, target, days=1)
    assert context.for_segment(US_EQUITY) == ()


def test_load_respects_subset_of_segments(tmp_path: Path) -> None:
    target = date(2026, 5, 8)
    for segment in _ALL_SEGMENTS:
        _write_archive(tmp_path, segment, date(2026, 5, 7))

    context = load_recent_briefings(
        tmp_path,
        target,
        days=1,
        segments=(US_EQUITY,),
    )

    assert set(context.entries_by_segment) == {US_EQUITY}
    assert len(context.for_segment(US_EQUITY)) == 1


def test_recent_briefing_entry_is_frozen() -> None:
    from pydantic import ValidationError

    entry = RecentBriefingEntry(
        publish_date=date(2026, 5, 7),
        segment=US_EQUITY,
        conclusion="x",
        key_drivers="y",
        watermark="z",
    )
    with pytest.raises(ValidationError):
        entry.conclusion = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# resolve_recent_days
# ---------------------------------------------------------------------------


def test_resolve_recent_days_default_when_unset() -> None:
    assert resolve_recent_days({}) == DEFAULT_RECENT_DAYS


def test_resolve_recent_days_default_when_blank(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Blank env value is the normal default path — must NOT emit a warning."""
    with caplog.at_level(logging.WARNING, logger="investo.briefing.context"):
        assert resolve_recent_days({ENV_RECENT_DAYS: "  "}) == DEFAULT_RECENT_DAYS
    assert not [r for r in caplog.records if r.levelno == logging.WARNING], (
        "blank value should fall back silently"
    )


def test_resolve_recent_days_default_when_non_numeric(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="investo.briefing.context"):
        assert resolve_recent_days({ENV_RECENT_DAYS: "abc"}) == DEFAULT_RECENT_DAYS
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert ENV_RECENT_DAYS in warnings[0].getMessage()
    assert "abc" in warnings[0].getMessage()
    assert "invalid" in warnings[0].getMessage()


def test_resolve_recent_days_default_when_negative(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="investo.briefing.context"):
        assert resolve_recent_days({ENV_RECENT_DAYS: "-3"}) == DEFAULT_RECENT_DAYS
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert ENV_RECENT_DAYS in warnings[0].getMessage()
    assert "-3" in warnings[0].getMessage()
    assert "out of range" in warnings[0].getMessage()


def test_resolve_recent_days_default_when_above_max(
    caplog: pytest.LogCaptureFixture,
) -> None:
    over = str(MAX_RECENT_DAYS + 1)
    with caplog.at_level(logging.WARNING, logger="investo.briefing.context"):
        assert resolve_recent_days({ENV_RECENT_DAYS: over}) == DEFAULT_RECENT_DAYS
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert ENV_RECENT_DAYS in warnings[0].getMessage()
    assert over in warnings[0].getMessage()
    assert "out of range" in warnings[0].getMessage()


def test_resolve_recent_days_accepts_zero() -> None:
    """``0`` is a valid disable signal — the resolver returns it verbatim."""
    assert resolve_recent_days({ENV_RECENT_DAYS: "0"}) == 0


def test_resolve_recent_days_accepts_in_range() -> None:
    assert resolve_recent_days({ENV_RECENT_DAYS: "7"}) == 7
    assert resolve_recent_days({ENV_RECENT_DAYS: str(MAX_RECENT_DAYS)}) == MAX_RECENT_DAYS
