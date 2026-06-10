"""u54 — Quality KPI computation rewrite (AC-4).

The legacy KPIs report ``0.0%`` when the denominator is zero, which
misleads readers into thinking "we measured a 0% liveness". u54
returns ``None`` so the renderer can surface ``n/a``. The new
counters (``failed_sources`` / ``zero_item_sources`` /
``core_missing_segments`` / ``segments_limited_or_worse``) populate
from the augmented ``coverage.jsonl`` schema.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from investo.briefing.quality_eval import (
    QualityKPIs,
    compute_quality_kpis,
    render_quality_page,
)


def _write_coverage_line(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload) + "\n")


def test_denominator_zero_kpis_render_as_n_a(tmp_path: Path) -> None:
    kpis = QualityKPIs(
        today=date(2026, 5, 9),
        window_days=7,
        runs_observed=0,
        runs_with_failed_source=0,
        briefings_observed=0,
        briefings_data_limited=0,
        briefings_with_figures=0,
    )
    body = render_quality_page(kpis)
    assert "측정 가능한 게시가 없습니다" in body


def test_render_quality_page_renders_n_a_when_only_runs_observed(tmp_path: Path) -> None:
    """One run observed but zero briefings → figures_presence is n/a but
    source_liveness is computable."""
    kpis = QualityKPIs(
        today=date(2026, 5, 9),
        window_days=7,
        runs_observed=2,
        runs_with_failed_source=0,
        briefings_observed=0,
        briefings_data_limited=0,
        briefings_with_figures=0,
    )
    body = render_quality_page(kpis)
    assert "소스 라이브니스 | 100.0%" in body
    assert "n/a" in body  # figures + fallback denominators are zero


def test_failed_sources_counter_aggregates_across_runs(tmp_path: Path) -> None:
    coverage = tmp_path / "coverage.jsonl"
    _write_coverage_line(
        coverage,
        {
            "target_date": "2026-05-07",
            "outcomes": [
                {"source_name": "a", "status": "failed", "category": "news"},
                {"source_name": "b", "status": "ok", "category": "price"},
            ],
        },
    )
    _write_coverage_line(
        coverage,
        {
            "target_date": "2026-05-08",
            "outcomes": [
                {"source_name": "a", "status": "failed", "category": "news"},
                {"source_name": "b", "status": "zero", "category": "price"},
            ],
        },
    )
    kpis = compute_quality_kpis(
        date(2026, 5, 9),
        coverage_path=coverage,
        archive_root=tmp_path / "archive",
    )
    assert kpis.failed_sources == 2
    assert kpis.zero_item_sources == 1


def test_severities_field_populates_core_missing_counter(tmp_path: Path) -> None:
    coverage = tmp_path / "coverage.jsonl"
    _write_coverage_line(
        coverage,
        {
            "target_date": "2026-05-07",
            "outcomes": [{"source_name": "a", "status": "ok", "category": "news"}],
            "severities": {
                "domestic-equity": "limited",
                "us-equity": "normal",
                "crypto": "failed",
            },
        },
    )
    kpis = compute_quality_kpis(
        date(2026, 5, 9),
        coverage_path=coverage,
        archive_root=tmp_path / "archive",
    )
    # Two segments at limited/failed → core_missing_segments=2.
    assert kpis.core_missing_segments == 2
    assert kpis.segments_limited_or_worse == 2


def test_legacy_coverage_line_without_severities_field_contributes_zero(
    tmp_path: Path,
) -> None:
    """Pre-u54 rows have no ``severities`` field — they contribute 0 to
    the new severity-based counters and stay readable."""
    coverage = tmp_path / "coverage.jsonl"
    _write_coverage_line(
        coverage,
        {
            "target_date": "2026-05-07",
            "outcomes": [
                {"source_name": "a", "status": "failed", "category": "news"},
            ],
        },
    )
    kpis = compute_quality_kpis(
        date(2026, 5, 9),
        coverage_path=coverage,
        archive_root=tmp_path / "archive",
    )
    assert kpis.runs_observed == 1
    assert kpis.runs_with_failed_source == 1
    assert kpis.failed_sources == 1
    assert kpis.core_missing_segments == 0
    assert kpis.segments_limited_or_worse == 0


def test_render_quality_page_includes_new_counters(tmp_path: Path) -> None:
    kpis = QualityKPIs(
        today=date(2026, 5, 9),
        window_days=7,
        runs_observed=3,
        runs_with_failed_source=1,
        briefings_observed=2,
        briefings_data_limited=0,
        briefings_with_figures=2,
        failed_sources=4,
        zero_item_sources=2,
        core_missing_segments=1,
        segments_limited_or_worse=2,
    )
    body = render_quality_page(kpis)
    assert "실패한 소스 누적" in body
    assert "0건 반환 소스 누적" in body
    assert "핵심 소스 결손 세그먼트" in body
    assert "제한/실패 세그먼트" in body


def test_data_limited_markers_include_status_tags_and_realtime_notice(tmp_path: Path) -> None:
    archive = tmp_path / "archive"
    for segment, marker in enumerate(("[데이터부족]", "데이터 부족 안내", "실시간 안내")):
        path = archive / f"segment-{segment}" / "2026" / "06" / "2026-06-09.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# title\n\n{marker}\n", encoding="utf-8")

    kpis = compute_quality_kpis(
        date(2026, 6, 9),
        coverage_path=tmp_path / "coverage.jsonl",
        archive_root=archive,
    )

    assert kpis.briefings_observed == 3
    assert kpis.briefings_data_limited == 3
