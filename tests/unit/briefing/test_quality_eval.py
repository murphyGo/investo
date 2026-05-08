"""Tests for u32 Step 4 — daily quality evaluation harness."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from investo.briefing.quality_eval import (
    QualityKPIs,
    compute_quality_kpis,
    render_quality_page,
)


def _write_coverage(path: Path, day: str, outcomes: list[dict]) -> None:  # type: ignore[type-arg]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps({"target_date": day, "outcomes": outcomes}) + "\n")


def _write_archive(root: Path, segment: str, day: str, body: str) -> None:
    file_path = root / segment / day[:4] / day[5:7] / f"{day}.md"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(body, encoding="utf-8")


def test_no_data_returns_zero_kpis(tmp_path: Path) -> None:
    kpis = compute_quality_kpis(
        date(2026, 5, 9),
        coverage_path=tmp_path / "missing.jsonl",
        archive_root=tmp_path / "archive",
    )
    assert kpis.runs_observed == 0
    assert kpis.briefings_observed == 0
    assert kpis.source_liveness_rate == 0.0
    assert kpis.figures_presence_rate == 0.0
    assert kpis.fallback_ratio == 0.0


def test_source_liveness_counts_runs_without_failed_outcome(tmp_path: Path) -> None:
    coverage = tmp_path / "coverage.jsonl"
    archive = tmp_path / "archive"
    _write_coverage(coverage, "2026-05-07", [{"source_name": "a", "status": "ok"}])
    _write_coverage(coverage, "2026-05-08", [{"source_name": "a", "status": "failed"}])
    _write_coverage(coverage, "2026-05-09", [{"source_name": "a", "status": "zero"}])

    kpis = compute_quality_kpis(date(2026, 5, 9), coverage_path=coverage, archive_root=archive)
    # 3 runs, 1 with a failed source → liveness 2/3 ≈ 0.6666...
    assert kpis.runs_observed == 3
    assert kpis.runs_with_failed_source == 1
    assert kpis.source_liveness_rate == 2 / 3


def test_figures_presence_counts_non_data_limited_briefings_with_numeric_token(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "archive"
    _write_archive(archive, "us-equity", "2026-05-08", "S&P 500 closed at 5,200.42 (+0.42%).")
    _write_archive(archive, "us-equity", "2026-05-09", "Markets calm. No reading available today.")

    kpis = compute_quality_kpis(
        date(2026, 5, 9),
        coverage_path=tmp_path / "missing.jsonl",
        archive_root=archive,
    )
    assert kpis.briefings_observed == 2
    assert kpis.briefings_with_figures == 1
    assert kpis.figures_presence_rate == 0.5


def test_fallback_ratio_counts_data_limited_briefings(tmp_path: Path) -> None:
    archive = tmp_path / "archive"
    _write_archive(archive, "us-equity", "2026-05-08", "Healthy briefing with 5,200.42 figure.")
    _write_archive(archive, "us-equity", "2026-05-09", "데이터 부족 안내 — fallback body")

    kpis = compute_quality_kpis(
        date(2026, 5, 9),
        coverage_path=tmp_path / "missing.jsonl",
        archive_root=archive,
    )
    assert kpis.briefings_observed == 2
    assert kpis.briefings_data_limited == 1
    assert kpis.fallback_ratio == 0.5


def test_data_limited_briefing_not_counted_in_figures_denominator(tmp_path: Path) -> None:
    """A data-limited body should not depress figures_presence_rate."""
    archive = tmp_path / "archive"
    _write_archive(archive, "us-equity", "2026-05-09", "데이터 부족 안내 — fallback body")

    kpis = compute_quality_kpis(
        date(2026, 5, 9),
        coverage_path=tmp_path / "missing.jsonl",
        archive_root=archive,
    )
    # 1 archived briefing, all data-limited → non-limited denominator is 0 → rate 0.0.
    assert kpis.briefings_with_figures == 0
    assert kpis.figures_presence_rate == 0.0


def test_render_quality_page_no_data() -> None:
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
    assert "데이터 품질" in body
    assert "측정 가능한 게시가 없습니다" in body


def test_render_quality_page_full() -> None:
    kpis = QualityKPIs(
        today=date(2026, 5, 9),
        window_days=7,
        runs_observed=10,
        runs_with_failed_source=2,
        briefings_observed=8,
        briefings_data_limited=1,
        briefings_with_figures=6,
    )
    body = render_quality_page(kpis)
    assert "데이터 품질" in body
    assert "소스 라이브니스" in body
    assert "수치 인용 비율" in body
    assert "데이터 부족 폴백" in body
    # liveness 8/10 = 80.0%
    assert "80.0%" in body
    # figures 6/(8-1) ≈ 85.7%
    assert "85.7%" in body
    # fallback 1/8 = 12.5%
    assert "12.5%" in body
