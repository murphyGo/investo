"""u69 — canonical quality-snapshot cross-surface consistency tests."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from investo.briefing.quality_eval import QualityKPIs
from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.publisher.quality_consistency import (
    CODE_DENOMINATOR_UNKNOWN_BUT_EVIDENCE,
    CODE_FAILED_COUNT_MISMATCH,
    CODE_QUALITY_PAGE_MISSING,
    CODE_STATUS_MISMATCH,
    build_canonical_snapshot,
    check_quality_consistency,
    parse_segment_status_block,
    reconcile_kpis_with_history,
    validate_date_quality_consistency,
)

TARGET = date(2026, 5, 22)


def _segment_body(*, status_label: str, failed: int, data_limited: bool = False) -> str:
    limited = "데이터 부족 안내\n" if data_limited else ""
    return (
        "# title\n\n"
        f"> **데이터 상태**: {status_label} — 설명입니다.\n"
        "> **소스 카운트**: 수집 대상 5 / 성공 1 / 0건 0 / "
        f"실패 {failed} / 본문 사용 2\n\n"
        f"{limited}본문 내용입니다.\n"
    )


def _quality_page(failed_value: str) -> str:
    return (
        "# 데이터 품질\n\n"
        "| 지표 | 값 | 분모 |\n"
        "|------|------|------|\n"
        "| 소스 라이브니스 | n/a | 0 회 |\n"
        f"| 실패한 소스 누적 | {failed_value} | 0 회 |\n"
    )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_parse_status_block_reads_label_and_failed_count() -> None:
    block = parse_segment_status_block(_segment_body(status_label="실패", failed=3), US_EQUITY)
    assert block.status == "failed"
    assert block.failed_count == 3
    assert block.data_limited is False


def test_parse_status_block_handles_missing_block() -> None:
    block = parse_segment_status_block("# title\n\n본문만 있습니다.\n", CRYPTO)
    assert block.status is None
    assert block.failed_count == 0


# ---------------------------------------------------------------------------
# status_mismatch
# ---------------------------------------------------------------------------


def test_status_mismatch_when_history_healthier_than_segment() -> None:
    snapshot = build_canonical_snapshot(
        TARGET,
        segment_texts={US_EQUITY: _segment_body(status_label="실패", failed=3)},
        history_row={"date": TARGET.isoformat(), "worst_severity": "normal"},
    )
    findings = check_quality_consistency(snapshot, quality_page_text=_quality_page("3 회"))
    codes = {f.code for f in findings if f.is_failure}
    assert CODE_STATUS_MISMATCH in codes


def test_no_status_mismatch_when_history_matches_worst() -> None:
    snapshot = build_canonical_snapshot(
        TARGET,
        segment_texts={
            US_EQUITY: _segment_body(status_label="제한", failed=2),
            CRYPTO: _segment_body(status_label="정상", failed=0),
        },
        history_row={
            "date": TARGET.isoformat(),
            "worst_severity": "limited",
            "total_failed_sources": 2,
        },
    )
    findings = check_quality_consistency(snapshot, quality_page_text=_quality_page("2 회"))
    assert [f for f in findings if f.is_failure] == []


# ---------------------------------------------------------------------------
# failed_count_mismatch
# ---------------------------------------------------------------------------


def test_failed_count_mismatch_when_history_zero_but_segment_failed() -> None:
    snapshot = build_canonical_snapshot(
        TARGET,
        segment_texts={US_EQUITY: _segment_body(status_label="제한", failed=4)},
        history_row={
            "date": TARGET.isoformat(),
            "worst_severity": "limited",
            "total_failed_sources": 0,
        },
    )
    findings = check_quality_consistency(snapshot, quality_page_text=_quality_page("0 회"))
    codes = {f.code for f in findings if f.is_failure}
    assert CODE_FAILED_COUNT_MISMATCH in codes


# ---------------------------------------------------------------------------
# denominator_unknown_but_evidence_present (quality.md dashboard)
# ---------------------------------------------------------------------------


def test_dashboard_renders_zero_failed_with_evidence() -> None:
    snapshot = build_canonical_snapshot(
        TARGET,
        segment_texts={US_EQUITY: _segment_body(status_label="제한", failed=3)},
        history_row={
            "date": TARGET.isoformat(),
            "worst_severity": "limited",
            "total_failed_sources": 3,
        },
    )
    findings = check_quality_consistency(snapshot, quality_page_text=_quality_page("0 회"))
    codes = {f.code for f in findings if f.is_failure}
    assert CODE_DENOMINATOR_UNKNOWN_BUT_EVIDENCE in codes


def test_dashboard_agrees_when_failed_count_matches() -> None:
    snapshot = build_canonical_snapshot(
        TARGET,
        segment_texts={US_EQUITY: _segment_body(status_label="제한", failed=3)},
        history_row={
            "date": TARGET.isoformat(),
            "worst_severity": "limited",
            "total_failed_sources": 3,
        },
    )
    findings = check_quality_consistency(snapshot, quality_page_text=_quality_page("3 회"))
    assert [f for f in findings if f.is_failure] == []


# ---------------------------------------------------------------------------
# quality_page_missing is skipped, not failed
# ---------------------------------------------------------------------------


def test_missing_quality_page_records_skipped_not_failure() -> None:
    snapshot = build_canonical_snapshot(
        TARGET,
        segment_texts={US_EQUITY: _segment_body(status_label="정상", failed=0)},
        history_row={"date": TARGET.isoformat(), "worst_severity": "normal"},
    )
    findings = check_quality_consistency(snapshot, quality_page_text=None)
    skipped = [f for f in findings if f.skipped]
    assert any(f.code == CODE_QUALITY_PAGE_MISSING for f in skipped)
    assert [f for f in findings if f.is_failure] == []


# ---------------------------------------------------------------------------
# reconcile_kpis_with_history (rendering-path fix)
# ---------------------------------------------------------------------------


def _kpis(failed_sources: int) -> QualityKPIs:
    return QualityKPIs(
        today=TARGET,
        window_days=7,
        runs_observed=0,
        runs_with_failed_source=0,
        briefings_observed=0,
        briefings_data_limited=0,
        briefings_with_figures=0,
        failed_sources=failed_sources,
    )


def test_reconcile_bumps_failed_floor_from_history(tmp_path: Path) -> None:
    history = tmp_path / "quality_history.jsonl"
    history.write_text(
        json.dumps(
            {
                "date": TARGET.isoformat(),
                "worst_severity": "limited",
                "total_failed_sources": 4,
                "source_liveness": 0.0,
                "figures_presence": 1.0,
                "fallback_ratio": 0.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    reconciled = reconcile_kpis_with_history(_kpis(0), target_date=TARGET, history_path=history)
    assert reconciled.failed_sources == 4
    assert reconciled.runs_observed == 1
    assert reconciled.runs_with_failed_source == 1


def test_reconcile_noop_when_coverage_already_higher(tmp_path: Path) -> None:
    history = tmp_path / "quality_history.jsonl"
    history.write_text(
        json.dumps(
            {
                "date": TARGET.isoformat(),
                "total_failed_sources": 2,
                "source_liveness": 0.0,
                "figures_presence": 1.0,
                "fallback_ratio": 0.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    reconciled = reconcile_kpis_with_history(_kpis(5), target_date=TARGET, history_path=history)
    assert reconciled.failed_sources == 5


def test_reconcile_noop_when_no_history_row(tmp_path: Path) -> None:
    history = tmp_path / "missing.jsonl"
    reconciled = reconcile_kpis_with_history(_kpis(0), target_date=TARGET, history_path=history)
    assert reconciled.failed_sources == 0


# ---------------------------------------------------------------------------
# validate_date_quality_consistency (end-to-end, file-backed)
# ---------------------------------------------------------------------------


def test_validate_contradiction_bundle(tmp_path: Path) -> None:
    history = tmp_path / "quality_history.jsonl"
    history.write_text(
        json.dumps(
            {
                "date": TARGET.isoformat(),
                "worst_severity": "normal",
                "total_failed_sources": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    findings = validate_date_quality_consistency(
        TARGET,
        segment_texts={
            DOMESTIC_EQUITY: _segment_body(status_label="실패", failed=3, data_limited=True),
        },
        history_path=history,
        quality_page_text=_quality_page("0 회"),
    )
    failure_codes = {f.code for f in findings if f.is_failure}
    assert CODE_STATUS_MISMATCH in failure_codes
    assert CODE_FAILED_COUNT_MISMATCH in failure_codes
    assert CODE_DENOMINATOR_UNKNOWN_BUT_EVIDENCE in failure_codes


def test_validate_consistent_bundle_passes(tmp_path: Path) -> None:
    history = tmp_path / "quality_history.jsonl"
    history.write_text(
        json.dumps(
            {
                "date": TARGET.isoformat(),
                "worst_severity": "normal",
                "total_failed_sources": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    findings = validate_date_quality_consistency(
        TARGET,
        segment_texts={DOMESTIC_EQUITY: _segment_body(status_label="정상", failed=0)},
        history_path=history,
        quality_page_text=_quality_page("0 회"),
    )
    assert [f for f in findings if f.is_failure] == []
