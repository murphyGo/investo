"""Tests for the public quality page renderer."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from investo.publisher.site_index import update_quality_page


def _write_history(path: Path, day: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": day,
        "source_liveness": 1.0,
        "figures_presence": 0.75,
        "fallback_ratio": 0.0,
        "published_segments": 3,
        "total_items": 12,
        "total_failed_sources": 0,
    }
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload) + "\n")


def _write_coverage(path: Path, day: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(
            json.dumps(
                {
                    "target_date": day,
                    "outcomes": [{"source_name": "src", "status": "ok", "item_count": 1}],
                }
            )
            + "\n"
        )


def test_update_quality_page_embeds_sparkline_and_trend_section(tmp_path: Path) -> None:
    history = tmp_path / "quality_history.jsonl"
    coverage = tmp_path / "coverage.jsonl"
    archive = tmp_path / "archive"
    quality_page = tmp_path / "quality.md"
    for day in range(1, 31):
        _write_history(history, f"2026-05-{day:02d}")
    _write_coverage(coverage, "2026-05-30")

    update_quality_page(
        date(2026, 5, 30),
        coverage_path=coverage,
        archive_root=archive,
        quality_history_path=history,
        quality_page_path=quality_page,
    )

    body = quality_page.read_text(encoding="utf-8")
    assert "<svg" in body
    assert "최근 30일 추세" in body
    assert "## 현재 7일 KPI" in body


def test_update_quality_page_empty_history_keeps_no_data_message(tmp_path: Path) -> None:
    quality_page = tmp_path / "quality.md"

    update_quality_page(
        date(2026, 5, 30),
        coverage_path=tmp_path / "missing.jsonl",
        archive_root=tmp_path / "archive",
        quality_history_path=tmp_path / "missing_history.jsonl",
        quality_page_path=quality_page,
    )

    body = quality_page.read_text(encoding="utf-8")
    assert "데이터 부족" in body
    assert "측정 가능한 게시가 없습니다" in body


def test_update_quality_page_is_idempotent(tmp_path: Path) -> None:
    history = tmp_path / "quality_history.jsonl"
    coverage = tmp_path / "coverage.jsonl"
    quality_page = tmp_path / "quality.md"
    for day in range(1, 31):
        _write_history(history, f"2026-05-{day:02d}")
    _write_coverage(coverage, "2026-05-30")

    kwargs = {
        "coverage_path": coverage,
        "archive_root": tmp_path / "archive",
        "quality_history_path": history,
        "quality_page_path": quality_page,
    }
    update_quality_page(date(2026, 5, 30), **kwargs)
    first = quality_page.read_bytes()
    update_quality_page(date(2026, 5, 30), **kwargs)

    assert quality_page.read_bytes() == first
