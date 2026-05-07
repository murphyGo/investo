"""Tests for the publish-calendar heatmap renderer (u29 site-discovery-v2)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from investo.visuals.calendar_heatmap import (
    CalendarCell,
    render_publish_heatmap,
    scan_publish_coverage,
)


def test_render_empty_grid_returns_placeholder_svg() -> None:
    svg = render_publish_heatmap([], today=date(2026, 5, 8))
    assert svg.startswith("<svg")
    assert "발행 이력이 아직 없습니다" in svg


def test_render_heatmap_emits_status_rects_with_legend() -> None:
    cells = [
        CalendarCell(target_date=date(2026, 4, 27), status="normal"),
        CalendarCell(target_date=date(2026, 4, 28), status="partial"),
        CalendarCell(target_date=date(2026, 4, 29), status="insufficient"),
    ]
    svg = render_publish_heatmap(cells, today=date(2026, 5, 1))

    assert 'class="u29-cell-normal"' in svg
    assert 'class="u29-cell-partial"' in svg
    assert 'class="u29-cell-insufficient"' in svg
    # Tooltip per-cell <title> exposes ISO date + status label.
    assert "<title>2026-04-27 · 정상</title>" in svg
    assert "<title>2026-04-28 · 부분</title>" in svg
    assert "<title>2026-04-29 · 부족</title>" in svg
    # Legend includes all four status labels.
    assert "정상" in svg and "부분" in svg and "부족" in svg and "미발행" in svg


def test_render_heatmap_is_deterministic() -> None:
    cells = [
        CalendarCell(target_date=date(2026, 4, 27), status="normal"),
        CalendarCell(target_date=date(2026, 4, 28), status="partial"),
    ]
    a = render_publish_heatmap(cells, today=date(2026, 5, 1))
    b = render_publish_heatmap(cells, today=date(2026, 5, 1))
    assert a == b


def test_render_heatmap_uses_dark_mode_media_query() -> None:
    cells = [CalendarCell(target_date=date(2026, 4, 27), status="normal")]
    svg = render_publish_heatmap(cells, today=date(2026, 5, 1))
    assert "@media (prefers-color-scheme: dark)" in svg


def test_scan_publish_coverage_classifies_by_segment_count(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive"
    today = date(2026, 4, 28)

    def _seed(segment: str, day: date) -> None:
        path = (
            archive_root
            / segment
            / f"{day.year:04d}"
            / f"{day.month:02d}"
            / f"{day.isoformat()}.md"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("seed", encoding="utf-8")

    # Day 1 — all three segments → normal
    for segment in ("domestic-equity", "us-equity", "crypto"):
        _seed(segment, date(2026, 4, 26))
    # Day 2 — only us-equity → partial
    _seed("us-equity", date(2026, 4, 27))
    # Day 3 (today) — none → absent (excluded from cells)

    cells = scan_publish_coverage(
        archive_root,
        today=today,
        project_start=date(2026, 4, 26),
    )
    by_date = {cell.target_date: cell.status for cell in cells}
    assert by_date == {
        date(2026, 4, 26): "normal",
        date(2026, 4, 27): "partial",
    }


def test_scan_publish_coverage_returns_empty_before_project_start() -> None:
    cells = scan_publish_coverage(
        Path("/tmp/nonexistent"),
        today=date(2026, 4, 25),
        project_start=date(2026, 4, 26),
    )
    assert cells == []
