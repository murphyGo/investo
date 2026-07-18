"""Tests for u31 Step 3 — source health time series + N-day FAILED detection."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from investo.models.coverage import SourceOutcome
from investo.orchestrator import source_health


def _ok(name: str) -> SourceOutcome:
    return SourceOutcome.ok(name, "news", item_count=5)


def _failed(name: str) -> SourceOutcome:
    return SourceOutcome.from_failure(name, "news", message="boom", transient=True)


def test_append_daily_coverage_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "coverage.jsonl"
    source_health.append_daily_coverage(date(2026, 5, 9), [_ok("a"), _failed("b")], path=target)
    contents = target.read_text(encoding="utf-8")
    assert "2026-05-09" in contents
    assert '"source_name": "a"' in contents or "source_name" in contents
    assert '"status": "ok"' in contents or "ok" in contents


def test_append_daily_coverage_appends_multiple_days(tmp_path: Path) -> None:
    target = tmp_path / "coverage.jsonl"
    source_health.append_daily_coverage(date(2026, 5, 9), [_ok("a")], path=target)
    source_health.append_daily_coverage(date(2026, 5, 10), [_ok("a")], path=target)
    lines = [line for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2


def test_append_daily_coverage_records_image_stage_note(tmp_path: Path) -> None:
    # u137 R9 — the image-candidate stage note rides the daily coverage
    # line under the ``image_stage`` key; omitted when not supplied
    # (legacy/unsegmented runs).
    target = tmp_path / "coverage.jsonl"
    source_health.append_daily_coverage(
        date(2026, 7, 16),
        [_ok("a")],
        path=target,
        image_stage="failed: RuntimeError",
    )
    source_health.append_daily_coverage(date(2026, 7, 17), [_ok("a")], path=target)
    lines = [line for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert '"image_stage": "failed: RuntimeError"' in lines[0]
    assert "image_stage" not in lines[1]


def test_detect_consecutive_failed_returns_empty_when_no_log(tmp_path: Path) -> None:
    target = tmp_path / "coverage.jsonl"
    assert source_health.detect_consecutive_failed(today=date(2026, 5, 9), path=target) == ()


def test_detect_consecutive_failed_picks_source_failed_three_days(tmp_path: Path) -> None:
    target = tmp_path / "coverage.jsonl"
    source_health.append_daily_coverage(
        date(2026, 5, 7), [_failed("flaky"), _ok("good")], path=target
    )
    source_health.append_daily_coverage(
        date(2026, 5, 8), [_failed("flaky"), _ok("good")], path=target
    )
    source_health.append_daily_coverage(
        date(2026, 5, 9), [_failed("flaky"), _ok("good")], path=target
    )
    assert source_health.detect_consecutive_failed(
        today=date(2026, 5, 9), threshold=3, path=target
    ) == ("flaky",)


def test_detect_consecutive_failed_resets_on_ok_day(tmp_path: Path) -> None:
    target = tmp_path / "coverage.jsonl"
    source_health.append_daily_coverage(date(2026, 5, 7), [_failed("flaky")], path=target)
    source_health.append_daily_coverage(date(2026, 5, 8), [_ok("flaky")], path=target)
    source_health.append_daily_coverage(date(2026, 5, 9), [_failed("flaky")], path=target)
    assert (
        source_health.detect_consecutive_failed(today=date(2026, 5, 9), threshold=3, path=target)
        == ()
    )


def test_detect_consecutive_failed_returns_empty_when_day_missing(tmp_path: Path) -> None:
    target = tmp_path / "coverage.jsonl"
    # Only two of the last three days logged → cannot assert "every day failed".
    source_health.append_daily_coverage(date(2026, 5, 7), [_failed("flaky")], path=target)
    source_health.append_daily_coverage(date(2026, 5, 9), [_failed("flaky")], path=target)
    assert (
        source_health.detect_consecutive_failed(today=date(2026, 5, 9), threshold=3, path=target)
        == ()
    )


def test_detect_consecutive_failed_intersects_failed_sources(tmp_path: Path) -> None:
    """A source must be failed on EVERY day in the window, not on average."""
    target = tmp_path / "coverage.jsonl"
    source_health.append_daily_coverage(date(2026, 5, 7), [_failed("a"), _failed("b")], path=target)
    source_health.append_daily_coverage(date(2026, 5, 8), [_failed("a"), _ok("b")], path=target)
    source_health.append_daily_coverage(date(2026, 5, 9), [_failed("a"), _failed("b")], path=target)
    # Only "a" failed all three days; "b" recovered on day 2.
    assert source_health.detect_consecutive_failed(
        today=date(2026, 5, 9), threshold=3, path=target
    ) == ("a",)


def test_resolve_coverage_path_honours_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("INVESTO_COVERAGE_LOG_PATH", "/tmp/x.jsonl")
    assert source_health.resolve_coverage_path() == Path("/tmp/x.jsonl")
    monkeypatch.delenv("INVESTO_COVERAGE_LOG_PATH")
    assert source_health.resolve_coverage_path() == Path("archive/_meta/coverage.jsonl")
