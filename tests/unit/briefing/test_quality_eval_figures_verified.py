"""u55 Step 5 — Tests for the ``figures_verified`` KPI column."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from investo.briefing.quality_eval import (
    QualityKPIs,
    compute_quality_kpis,
)
from investo.briefing.quality_history import QualitySnapshot, append_quality_snapshot


def _write_archive_brief(archive_root: Path, target_date: date, *, body: str) -> None:
    target = archive_root / f"{target_date.year}" / f"{target_date.month:02d}"
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{target_date.isoformat()}.md").write_text(body, encoding="utf-8")


def test_kpi_default_none_rate_when_no_data(tmp_path: Path) -> None:
    kpis = compute_quality_kpis(
        today=date(2026, 5, 11),
        coverage_path=tmp_path / "coverage.jsonl",
        archive_root=tmp_path / "archive",
    )
    assert kpis.figures_verified_rate is None


def test_kpi_1_0_when_all_briefings_verify(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    body = "## 요약\n코스피 2,810.45 마감.\n"  # carries a figure; no downgrade callout
    _write_archive_brief(archive_root, date(2026, 5, 11), body=body)
    kpis = compute_quality_kpis(
        today=date(2026, 5, 11),
        coverage_path=tmp_path / "coverage.jsonl",
        archive_root=archive_root,
    )
    assert kpis.briefings_observed == 1
    assert kpis.figures_verified_rate == 1.0


def test_kpi_zero_when_downgrade_callout_present(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    body = "> ⚠️ 확인 필요: 수치 검증 실패 — spx_close\n## 요약\nS&P 500 5,900.00 (잘못된 수치)\n"
    _write_archive_brief(archive_root, date(2026, 5, 11), body=body)
    kpis = compute_quality_kpis(
        today=date(2026, 5, 11),
        coverage_path=tmp_path / "coverage.jsonl",
        archive_root=archive_root,
    )
    assert kpis.briefings_observed == 1
    assert kpis.figures_verified_rate == 0.0


def test_kpi_partial_when_some_briefings_downgraded(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    # Day 1: clean — verified.
    _write_archive_brief(
        archive_root,
        date(2026, 5, 10),
        body="## 요약\n코스피 2,810.45 마감\n",
    )
    # Day 2: downgrade callout present.
    _write_archive_brief(
        archive_root,
        date(2026, 5, 11),
        body=("> ⚠️ 확인 필요: 수치 검증 실패 — spx_close\n## 요약\n2,810.45 (의심 수치)\n"),
    )
    kpis = compute_quality_kpis(
        today=date(2026, 5, 11),
        coverage_path=tmp_path / "coverage.jsonl",
        archive_root=archive_root,
    )
    assert kpis.briefings_observed == 2
    rate = kpis.figures_verified_rate
    assert rate is not None
    assert 0.49 < rate < 0.51


def test_kpis_render_contains_figures_verified_row(tmp_path: Path) -> None:
    from investo.briefing.quality_eval import render_quality_page

    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    _write_archive_brief(
        archive_root,
        date(2026, 5, 11),
        body="## 요약\n코스피 2,810.45\n",
    )
    kpis = compute_quality_kpis(
        today=date(2026, 5, 11),
        coverage_path=tmp_path / "coverage.jsonl",
        archive_root=archive_root,
    )
    page = render_quality_page(kpis)
    assert "수치 검증 비율" in page


def test_quality_snapshot_persists_figures_verified(tmp_path: Path) -> None:
    history = tmp_path / "quality_history.jsonl"
    snapshot = QualitySnapshot(
        source_liveness=1.0,
        figures_presence=1.0,
        fallback_ratio=0.0,
        published_segments=3,
        total_items=42,
        total_failed_sources=0,
        figures_verified=0.85,
    )
    append_quality_snapshot(date(2026, 5, 11), snapshot=snapshot, history_path=history)
    raw = history.read_text(encoding="utf-8")
    assert "figures_verified" in raw
    assert "0.85" in raw


def test_quality_snapshot_legacy_without_figures_verified(tmp_path: Path) -> None:
    """Backward-compat: snapshot without ``figures_verified`` writes without the column."""
    history = tmp_path / "quality_history.jsonl"
    snapshot = QualitySnapshot(
        source_liveness=1.0,
        figures_presence=1.0,
        fallback_ratio=0.0,
        published_segments=3,
        total_items=42,
        total_failed_sources=0,
    )
    append_quality_snapshot(date(2026, 5, 11), snapshot=snapshot, history_path=history)
    raw = history.read_text(encoding="utf-8")
    assert "figures_verified" not in raw


def test_kpi_class_accepts_briefings_with_verified_figures() -> None:
    kpis = QualityKPIs(
        today=date(2026, 5, 11),
        window_days=7,
        runs_observed=5,
        runs_with_failed_source=0,
        briefings_observed=10,
        briefings_data_limited=2,
        briefings_with_figures=8,
        briefings_with_verified_figures=6,
    )
    rate = kpis.figures_verified_rate
    assert rate is not None
    assert 0.74 < rate < 0.76
