"""Tests for u42 quality-history sparkline SVG."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from investo.briefing.quality_eval import QualityHistoryRow
from investo.visuals.quality_sparkline import (
    SVG_HEIGHT,
    SVG_WIDTH,
    build_quality_sparkline_manifest,
    render_quality_sparkline,
)


def _rows(*, gaps: set[int] | None = None) -> list[QualityHistoryRow]:
    gap_days = gaps or set()
    start = date(2026, 5, 1)
    rows: list[QualityHistoryRow] = []
    for idx in range(30):
        day = start + timedelta(days=idx)
        if idx in gap_days:
            rows.append(QualityHistoryRow(day=day))
            continue
        rows.append(
            QualityHistoryRow(
                day=day,
                source_liveness=(idx + 1) / 30,
                figures_presence=0.8,
                fallback_ratio=idx / 60,
                published_segments=3,
                total_items=10,
                total_failed_sources=0,
            )
        )
    return rows


def test_quality_sparkline_is_deterministic() -> None:
    rows = _rows()

    assert render_quality_sparkline(rows) == render_quality_sparkline(rows)


def test_quality_sparkline_empty_input_renders_placeholder() -> None:
    svg = render_quality_sparkline([]).decode("utf-8")

    assert "데이터 부족" in svg


def test_quality_sparkline_missing_days_break_segments() -> None:
    svg = render_quality_sparkline(_rows(gaps={5})).decode("utf-8")

    assert svg.count('data-metric="source_liveness"') == 2
    assert "0,48" not in svg


def test_quality_sparkline_dimensions_are_fixed() -> None:
    svg = render_quality_sparkline(_rows()).decode("utf-8")

    assert f'viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}"' in svg


def test_quality_sparkline_manifest_fields() -> None:
    generated_at = datetime(2026, 5, 9, 12, 0, tzinfo=UTC)

    manifest = build_quality_sparkline_manifest(
        asset_relative_path="site_docs/assets/quality-sparkline.svg",
        generated_at=generated_at,
    )

    assert manifest.source_type == "generated_svg"
    assert manifest.generator == "investo.visuals.quality_sparkline"
    assert manifest.dimensions == (SVG_WIDTH, SVG_HEIGHT)
    assert manifest.card_kind == "quality-sparkline"
