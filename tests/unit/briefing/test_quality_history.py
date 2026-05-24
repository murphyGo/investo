"""Tests for u42 quality-history persistence."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from investo.briefing.quality_history import QualitySnapshot, append_quality_snapshot


def _snapshot(source_liveness: float = 1.0) -> QualitySnapshot:
    return QualitySnapshot(
        source_liveness=source_liveness,
        figures_presence=0.75,
        fallback_ratio=0.25,
        published_segments=3,
        total_items=12,
        total_failed_sources=0 if source_liveness == 1.0 else 1,
    )


def _read_rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_first_publish_creates_history_file(tmp_path: Path) -> None:
    path = tmp_path / "archive" / "_meta" / "quality_history.jsonl"
    append_quality_snapshot(date(2026, 5, 9), snapshot=_snapshot(), history_path=path)

    rows = _read_rows(path)
    assert len(rows) == 1
    assert rows[0]["date"] == "2026-05-09"
    assert rows[0]["source_liveness"] == 1.0


def test_second_day_appends(tmp_path: Path) -> None:
    path = tmp_path / "quality_history.jsonl"
    append_quality_snapshot(date(2026, 5, 8), snapshot=_snapshot(), history_path=path)
    append_quality_snapshot(date(2026, 5, 9), snapshot=_snapshot(0.0), history_path=path)

    rows = _read_rows(path)
    assert [row["date"] for row in rows] == ["2026-05-08", "2026-05-09"]


def test_macro_diagnostics_persist_as_append_only_fields(tmp_path: Path) -> None:
    path = tmp_path / "quality_history.jsonl"
    append_quality_snapshot(
        date(2026, 5, 9),
        snapshot=QualitySnapshot(
            source_liveness=1.0,
            figures_presence=0.75,
            fallback_ratio=0.25,
            published_segments=3,
            total_items=12,
            total_failed_sources=0,
            macro_actual_missing_segments=1,
            required_macro_omitted=2,
        ),
        history_path=path,
    )

    rows = _read_rows(path)
    assert rows[0]["macro_actual_missing_segments"] == 1
    assert rows[0]["required_macro_omitted"] == 2


def test_same_day_republish_replaces_existing_row(tmp_path: Path) -> None:
    path = tmp_path / "quality_history.jsonl"
    append_quality_snapshot(date(2026, 5, 8), snapshot=_snapshot(), history_path=path)
    append_quality_snapshot(date(2026, 5, 9), snapshot=_snapshot(), history_path=path)
    append_quality_snapshot(date(2026, 5, 9), snapshot=_snapshot(0.0), history_path=path)

    rows = _read_rows(path)
    assert len(rows) == 2
    assert rows[-1]["date"] == "2026-05-09"
    assert rows[-1]["source_liveness"] == 0.0


def test_corrupt_jsonl_line_is_skipped(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    path = tmp_path / "quality_history.jsonl"
    path.write_text("{broken\n", encoding="utf-8")

    append_quality_snapshot(date(2026, 5, 9), snapshot=_snapshot(), history_path=path)

    assert len(_read_rows(path)) == 1
    assert "skipping corrupt JSONL line" in caplog.text


def test_atomic_write_failure_preserves_existing_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "quality_history.jsonl"
    path.write_text('{"date":"2026-05-08"}\n', encoding="utf-8")
    original = path.read_text(encoding="utf-8")

    def fail_replace(self: Path, target: Path) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(RuntimeError, match="could not write quality history"):
        append_quality_snapshot(date(2026, 5, 9), snapshot=_snapshot(), history_path=path)
    assert path.read_text(encoding="utf-8") == original
