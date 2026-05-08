"""Tests for u31 Step 4 — operator weekly digest renderer."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from investo.models.coverage import SourceOutcome
from investo.orchestrator import source_health, weekly_ops_digest


def _ok(name: str) -> SourceOutcome:
    return SourceOutcome.ok(name, "news", item_count=5)


def _failed(name: str) -> SourceOutcome:
    return SourceOutcome.from_failure(name, "news", message="boom", transient=True)


def test_digest_no_data_emits_explicit_no_observed_runs(tmp_path: Path) -> None:
    text = weekly_ops_digest.build_weekly_digest_text(
        date(2026, 5, 9), path=tmp_path / "missing.jsonl"
    )
    assert "Investo 주간 운영" in text
    assert "관측된 실행 없음" in text


def test_digest_reports_success_rate_and_top_failed(tmp_path: Path) -> None:
    target = tmp_path / "coverage.jsonl"
    # Three days of data: two days ok, one day with two failed sources.
    source_health.append_daily_coverage(date(2026, 5, 7), [_ok("a"), _ok("b")], path=target)
    source_health.append_daily_coverage(date(2026, 5, 8), [_ok("a"), _ok("b")], path=target)
    source_health.append_daily_coverage(date(2026, 5, 9), [_failed("a"), _failed("b")], path=target)

    text = weekly_ops_digest.build_weekly_digest_text(date(2026, 5, 9), path=target)

    assert "Investo 주간 운영" in text
    assert "관측된 실행: 3회" in text
    assert "실패 포함 실행: 1회" in text
    # 2/3 successful → 66.7%.
    assert "66.7%" in text
    assert "a — 1회" in text
    assert "b — 1회" in text


def test_digest_minutes_used_estimate_appears_when_provided(tmp_path: Path) -> None:
    target = tmp_path / "coverage.jsonl"
    source_health.append_daily_coverage(date(2026, 5, 9), [_ok("a")], path=target)
    text = weekly_ops_digest.build_weekly_digest_text(
        date(2026, 5, 9), path=target, minutes_used_estimate=42.5
    )
    assert "GHA 사용 추정: 42.5분" in text


def test_digest_excludes_lines_outside_7_day_window(tmp_path: Path) -> None:
    target = tmp_path / "coverage.jsonl"
    # 8 days ago — outside the window.
    source_health.append_daily_coverage(date(2026, 5, 1), [_failed("old")], path=target)
    # Within the window.
    source_health.append_daily_coverage(date(2026, 5, 9), [_ok("fresh")], path=target)
    text = weekly_ops_digest.build_weekly_digest_text(date(2026, 5, 9), path=target)
    # The old "old" failure does not show up in the digest.
    assert "old" not in text
    # The single recent run is observed.
    assert "관측된 실행: 1회" in text


def test_is_opt_in_explicit_value() -> None:
    assert weekly_ops_digest.is_opt_in("1") is True
    assert weekly_ops_digest.is_opt_in("0") is False
    assert weekly_ops_digest.is_opt_in("") is False
