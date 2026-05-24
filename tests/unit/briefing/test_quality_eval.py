"""Tests for u32 Step 4 — daily quality evaluation harness."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from investo.briefing.quality_eval import (
    QualityKPIs,
    compute_quality_history,
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


def _write_history(path: Path, day: str, *, source_liveness: float = 1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": day,
        "source_liveness": source_liveness,
        "figures_presence": 0.5,
        "fallback_ratio": 0.25,
        "published_segments": 3,
        "total_items": 10,
        "total_failed_sources": 0,
    }
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload) + "\n")


def test_no_data_returns_n_a_kpis(tmp_path: Path) -> None:
    """u54 — Denominator-zero rates surface as ``None`` (rendered ``n/a``)
    rather than ``0.0`` so the reader does not confuse "we have no
    samples" with "we observed zero liveness"."""
    kpis = compute_quality_kpis(
        date(2026, 5, 9),
        coverage_path=tmp_path / "missing.jsonl",
        archive_root=tmp_path / "archive",
    )
    assert kpis.runs_observed == 0
    assert kpis.briefings_observed == 0
    assert kpis.source_liveness_rate is None
    assert kpis.figures_presence_rate is None
    assert kpis.fallback_ratio is None


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
    # 1 archived briefing, all data-limited → non-limited denominator is 0 → rate None (n/a).
    assert kpis.briefings_with_figures == 0
    assert kpis.figures_presence_rate is None


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


def test_compute_quality_history_returns_rolling_window(tmp_path: Path) -> None:
    history = tmp_path / "quality_history.jsonl"
    for day in range(1, 31):
        _write_history(history, f"2026-05-{day:02d}", source_liveness=day / 30)

    rows = compute_quality_history(30, history_path=history, today=date(2026, 5, 30))

    assert len(rows) == 30
    assert rows[0].day == date(2026, 5, 1)
    assert rows[-1].day == date(2026, 5, 30)
    assert rows[-1].source_liveness == 1.0


def test_compute_quality_history_preserves_missing_day_gaps(tmp_path: Path) -> None:
    history = tmp_path / "quality_history.jsonl"
    for day in range(1, 31):
        if day in {3, 9, 14, 20, 27}:
            continue
        _write_history(history, f"2026-05-{day:02d}")

    rows = compute_quality_history(30, history_path=history, today=date(2026, 5, 30))

    assert len(rows) == 30
    assert sum(1 for row in rows if not row.has_data) == 5
    assert rows[2].day == date(2026, 5, 3)
    assert rows[2].source_liveness is None


def test_compute_quality_history_empty_file_returns_empty(tmp_path: Path) -> None:
    history = tmp_path / "quality_history.jsonl"
    history.write_text("", encoding="utf-8")

    assert compute_quality_history(history_path=history) == []


def test_compute_quality_history_days_parameter_limits_window(tmp_path: Path) -> None:
    history = tmp_path / "quality_history.jsonl"
    for day in range(1, 31):
        _write_history(history, f"2026-05-{day:02d}")

    rows = compute_quality_history(7, history_path=history, today=date(2026, 5, 30))

    assert len(rows) == 7
    assert rows[0].day == date(2026, 5, 24)


def test_compute_quality_history_reads_macro_diagnostics(tmp_path: Path) -> None:
    history = tmp_path / "quality_history.jsonl"
    payload = {
        "date": "2026-05-30",
        "source_liveness": 1.0,
        "figures_presence": 0.5,
        "fallback_ratio": 0.25,
        "published_segments": 3,
        "total_items": 10,
        "total_failed_sources": 0,
        "macro_actual_missing_segments": 1,
        "required_macro_omitted": 2,
    }
    history.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    rows = compute_quality_history(1, history_path=history, today=date(2026, 5, 30))

    assert rows[0].macro_actual_missing_segments == 1
    assert rows[0].required_macro_omitted == 2
