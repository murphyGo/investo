"""u54 — Severity-alert debouncing tests (AC-7).

Goal: a flaky core source must not page the operator on every flap.
The gate fires only when the same segment is at severity ≥ ``limited``
for ``REQUIRED_CONSECUTIVE_BAD`` consecutive runs.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from investo.briefing.quality_history import recent_segment_severities
from investo.notifier.severity_debounce import (
    BAD_SEVERITIES,
    REQUIRED_CONSECUTIVE_BAD,
    should_alert_severity,
)


def _write_coverage_line(
    path: Path,
    *,
    target_date: str,
    severities: dict[str, str] | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line: dict[str, object] = {"target_date": target_date, "outcomes": []}
    if severities is not None:
        line["severities"] = severities
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(line) + "\n")


def test_one_bad_run_does_not_alert() -> None:
    assert not should_alert_severity(("limited",))


def test_two_consecutive_bad_alerts() -> None:
    assert should_alert_severity(("limited", "limited"))
    assert should_alert_severity(("limited", "failed"))
    assert should_alert_severity(("failed", "failed"))


def test_recovery_resets_counter() -> None:
    """bad → normal → bad sequence does not alert (only most-recent
    two runs matter)."""
    assert not should_alert_severity(("limited", "normal", "limited"))


def test_first_run_safety_no_alert_with_short_history() -> None:
    assert not should_alert_severity(())
    assert not should_alert_severity(("limited",))


def test_partial_is_not_bad() -> None:
    """``partial`` is *not* in BAD_SEVERITIES — debounce alerts fire
    only for limited/failed."""
    assert "partial" not in BAD_SEVERITIES
    assert not should_alert_severity(("partial", "partial"))


def test_recent_segment_severities_returns_chronological(tmp_path: Path) -> None:
    coverage = tmp_path / "coverage.jsonl"
    _write_coverage_line(
        coverage,
        target_date="2026-05-08",
        severities={"crypto": "limited", "us-equity": "normal"},
    )
    _write_coverage_line(
        coverage,
        target_date="2026-05-09",
        severities={"crypto": "failed", "us-equity": "normal"},
    )
    crypto = recent_segment_severities(
        "crypto", today=date(2026, 5, 9), coverage_path=coverage, lookback_runs=2
    )
    assert crypto == ("limited", "failed")
    us = recent_segment_severities(
        "us-equity", today=date(2026, 5, 9), coverage_path=coverage, lookback_runs=2
    )
    assert us == ("normal", "normal")


def test_recent_segment_severities_returns_empty_on_missing_history(tmp_path: Path) -> None:
    coverage = tmp_path / "missing.jsonl"
    assert recent_segment_severities("crypto", today=date(2026, 5, 9), coverage_path=coverage) == ()


def test_recent_segment_severities_returns_empty_on_legacy_line(tmp_path: Path) -> None:
    coverage = tmp_path / "coverage.jsonl"
    # Pre-u54 line (no severities field) blocks the lookup chain
    # — caller treats this as "not enough history yet".
    _write_coverage_line(coverage, target_date="2026-05-09", severities=None)
    assert recent_segment_severities("crypto", today=date(2026, 5, 9), coverage_path=coverage) == ()


def test_threshold_constant_is_two() -> None:
    assert REQUIRED_CONSECUTIVE_BAD == 2
