"""u54 — Same-day re-publish ``keep_worst`` semantics (AC-8).

An operator who re-runs the pipeline after a transient fix should not
silently improve the historical record. ``append_quality_snapshot``
defaults to ``keep_worst=True`` so an incoming snapshot with a *better*
severity than the existing same-day row is dropped (the existing
severity is preserved); other fields are still overwritten by the
later run.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from investo.briefing.quality_history import (
    QualitySnapshot,
    append_quality_snapshot,
)


def _read_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _snapshot(severity: str | None = None) -> QualitySnapshot:
    return QualitySnapshot(
        source_liveness=1.0,
        figures_presence=1.0,
        fallback_ratio=0.0,
        published_segments=3,
        total_items=10,
        total_failed_sources=0,
        worst_severity=severity,
    )


def test_first_write_records_severity(tmp_path: Path) -> None:
    path = tmp_path / "quality_history.jsonl"
    append_quality_snapshot(date(2026, 5, 9), snapshot=_snapshot("limited"), history_path=path)
    rows = _read_rows(path)
    assert len(rows) == 1
    assert rows[0]["worst_severity"] == "limited"


def test_keep_worst_drops_better_incoming_severity(tmp_path: Path) -> None:
    path = tmp_path / "quality_history.jsonl"
    append_quality_snapshot(date(2026, 5, 9), snapshot=_snapshot("limited"), history_path=path)
    # Re-publish with normal — must be dropped.
    append_quality_snapshot(date(2026, 5, 9), snapshot=_snapshot("normal"), history_path=path)
    rows = _read_rows(path)
    assert len(rows) == 1
    assert rows[0]["worst_severity"] == "limited"


def test_keep_worst_accepts_worse_incoming_severity(tmp_path: Path) -> None:
    path = tmp_path / "quality_history.jsonl"
    append_quality_snapshot(date(2026, 5, 9), snapshot=_snapshot("partial"), history_path=path)
    append_quality_snapshot(date(2026, 5, 9), snapshot=_snapshot("failed"), history_path=path)
    rows = _read_rows(path)
    assert len(rows) == 1
    assert rows[0]["worst_severity"] == "failed"


def test_keep_worst_false_overrides(tmp_path: Path) -> None:
    path = tmp_path / "quality_history.jsonl"
    append_quality_snapshot(date(2026, 5, 9), snapshot=_snapshot("limited"), history_path=path)
    append_quality_snapshot(
        date(2026, 5, 9),
        snapshot=_snapshot("normal"),
        history_path=path,
        keep_worst=False,
    )
    rows = _read_rows(path)
    assert rows[0]["worst_severity"] == "normal"


def test_different_days_unaffected(tmp_path: Path) -> None:
    path = tmp_path / "quality_history.jsonl"
    append_quality_snapshot(date(2026, 5, 8), snapshot=_snapshot("limited"), history_path=path)
    append_quality_snapshot(date(2026, 5, 9), snapshot=_snapshot("normal"), history_path=path)
    rows = _read_rows(path)
    assert {row["date"] for row in rows} == {"2026-05-08", "2026-05-09"}
    by_date = {row["date"]: row for row in rows}
    assert by_date["2026-05-08"]["worst_severity"] == "limited"
    assert by_date["2026-05-09"]["worst_severity"] == "normal"


def test_legacy_row_without_severity_is_overwritten(tmp_path: Path) -> None:
    """A pre-u54 row carries no ``worst_severity`` field; an incoming
    row with severity overwrites cleanly because the merge can only
    compare two populated severities."""
    path = tmp_path / "quality_history.jsonl"
    append_quality_snapshot(
        date(2026, 5, 9),
        snapshot=_snapshot(severity=None),
        history_path=path,
    )
    append_quality_snapshot(
        date(2026, 5, 9),
        snapshot=_snapshot("limited"),
        history_path=path,
    )
    rows = _read_rows(path)
    assert rows[0]["worst_severity"] == "limited"
