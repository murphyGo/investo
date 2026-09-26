"""Terminal history/page parity without implying post-push publication."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from investo.briefing.quality_eval import compute_quality_history
from investo.briefing.quality_history import QualitySnapshot, append_quality_snapshot
from investo.models.event_quality import EventCoverage, EventStageReceipt, EventTraceEntry
from investo.publisher.quality_consistency import (
    CODE_EVENT_COVERAGE_MISMATCH,
    validate_date_quality_consistency,
)
from investo.publisher.site_index import update_quality_page

DAY = date(2026, 9, 27)
BASE = QualitySnapshot(
    source_liveness=1,
    figures_presence=1,
    fallback_ratio=0,
    published_segments=1,
    total_items=4,
    total_failed_sources=0,
)


def _page(tmp_path: Path, coverage: EventCoverage | None) -> tuple[Path, str]:
    history = tmp_path / "history.jsonl"
    snapshot = BASE if coverage is None else replace(BASE, event_coverage={"us-equity": coverage})
    append_quality_snapshot(DAY, snapshot=snapshot, history_path=history)
    page = update_quality_page(
        DAY,
        coverage_path=tmp_path / "coverage.jsonl",
        archive_root=tmp_path / "archive",
        quality_history_path=history,
        quality_page_path=tmp_path / "quality.md",
    )
    return history, page.read_text()


def test_legacy_history_stays_nullable_without_new_page_claim(tmp_path: Path) -> None:
    history, page = _page(tmp_path, None)
    row = compute_quality_history(1, history_path=history, today=DAY)[0]
    assert row.event_coverage is row.event_coverage_basis is None
    assert "event_coverage" not in json.loads(history.read_text())
    assert "## 중요 사건 반영" not in page


@pytest.mark.parametrize(
    "coverage,expected",
    [
        (
            EventCoverage(collected_candidate_count=3, state="classification_unavailable"),
            "| 미국 증시 | 3/미집계/미집계 | 미집계/미집계/미집계 | "
            "미집계/미집계/미집계 | 미집계 | 미집계 | 분류 미완료 |",
        ),
        (
            EventCoverage(
                collected_candidate_count=0,
                selected_count=0,
                prompted_count=0,
                terminal_event_count=0,
                qualified_event_count=0,
                details_limited_count=0,
                summary_event_count=0,
                unsupported_count=0,
                state="no_qualifying_event",
            ),
            "| 미국 증시 | 0/0/0 | 0/0/0 | 0/0/0 | 미집계 | 미집계 | 설명 충족 사건 없음 |",
        ),
        (
            EventCoverage(
                collected_candidate_count=5,
                selected_count=3,
                prompted_count=3,
                terminal_event_count=2,
                qualified_event_count=1,
                details_limited_count=1,
                summary_event_count=2,
                unsupported_count=0,
                state="detail_limited",
            ),
            "| 미국 증시 | 5/3/3 | 2/1/1 | 2/1/0 | 66.7% | 33.3% | 세부 근거 제한 |",
        ),
    ],
)
def test_current_counts_and_unknown_denominators_match_metadata_and_page(
    tmp_path: Path,
    coverage: EventCoverage,
    expected: str,
) -> None:
    history, page = _page(tmp_path, coverage)
    persisted = json.loads(history.read_text())
    assert persisted["event_coverage_basis"] == "terminal"
    assert persisted["event_coverage"]["us-equity"] == coverage.model_dump(mode="json")
    assert compute_quality_history(1, history_path=history, today=DAY)[0].event_coverage == {
        "us-equity": coverage,
    }
    assert expected in page
    assert "최종 본문 검증 기준이며 원격 게시 확정 집계가 아닙니다." in page
    assert "remote_confirmed" not in persisted
    findings = validate_date_quality_consistency(
        DAY,
        segment_texts={},
        history_path=history,
        quality_page_text=page,
    )
    assert not any(f.code == CODE_EVENT_COVERAGE_MISMATCH for f in findings)
    _, rerendered = _page(tmp_path, coverage)
    assert page == rerendered


def test_public_history_never_contains_private_trace_identifiers(tmp_path: Path) -> None:
    coverage = EventCoverage(
        receipts=(
            EventStageReceipt(
                stage="selected",
                status="completed",
                count=1,
                trace=(
                    EventTraceEntry(hash_id="a" * 24, stage="selected", source_name="private-feed"),
                ),
            ),
        )
    )
    history, page = _page(tmp_path, coverage)
    for text in (history.read_text(), page):
        assert "private-feed" not in text
        assert "a" * 24 not in text
        assert "receipts" not in text


def test_consistency_rejects_false_rate_and_false_publication_basis(tmp_path: Path) -> None:
    history, page = _page(
        tmp_path,
        EventCoverage(
            selected_count=2,
            terminal_event_count=1,
            qualified_event_count=1,
            state="qualified",
        ),
    )
    findings = validate_date_quality_consistency(
        DAY,
        segment_texts={},
        history_path=history,
        quality_page_text=page.replace("50.0%", "100.0%"),
    )
    assert any(f.code == CODE_EVENT_COVERAGE_MISMATCH and f.is_failure for f in findings)
    raw = json.loads(history.read_text())
    raw["event_coverage_basis"] = "remote_confirmed"
    history.write_text(json.dumps(raw) + "\n")
    findings = validate_date_quality_consistency(
        DAY,
        segment_texts={},
        history_path=history,
        quality_page_text=page,
    )
    assert any(f.code == CODE_EVENT_COVERAGE_MISMATCH and f.is_failure for f in findings)
    assert compute_quality_history(1, history_path=history, today=DAY)[0].event_coverage is None


def test_sealed_measurements_override_consistent_but_wrong_history_and_page(tmp_path: Path) -> None:
    incorrect = EventCoverage(
        selected_count=2,
        terminal_event_count=2,
        qualified_event_count=2,
        state="qualified",
    )
    sealed = EventCoverage(
        selected_count=2,
        terminal_event_count=1,
        qualified_event_count=1,
        state="qualified",
    )
    history, page = _page(tmp_path, incorrect)
    findings = validate_date_quality_consistency(
        DAY,
        segment_texts={},
        history_path=history,
        quality_page_text=page,
        expected_event_coverage={"us-equity": sealed},
    )
    assert any(f.code == CODE_EVENT_COVERAGE_MISMATCH and f.is_failure for f in findings)
    assert not any(
        f.code == CODE_EVENT_COVERAGE_MISMATCH
        for f in validate_date_quality_consistency(
            DAY,
            segment_texts={},
            history_path=history,
            quality_page_text=page,
            expected_event_coverage={"us-equity": incorrect},
        )
    )


def test_sealed_measurements_detect_missing_segment_and_history(tmp_path: Path) -> None:
    coverage = EventCoverage(state="source_limited")
    history, page = _page(tmp_path, coverage)
    for expected in ({"crypto": coverage}, {"us-equity": coverage, "crypto": coverage}):
        findings = validate_date_quality_consistency(
            DAY,
            segment_texts={},
            history_path=history,
            quality_page_text=page,
            expected_event_coverage=expected,  # type: ignore[arg-type]
        )
        assert any(f.code == CODE_EVENT_COVERAGE_MISMATCH and f.is_failure for f in findings)
    history, page = _page(tmp_path, None)
    findings = validate_date_quality_consistency(
        DAY,
        segment_texts={},
        history_path=history,
        quality_page_text=page,
        expected_event_coverage={"us-equity": coverage},
    )
    assert any(f.code == CODE_EVENT_COVERAGE_MISMATCH and f.is_failure for f in findings)


@pytest.mark.parametrize("concealment", ["comment", "fenced", "duplicate", "indented_duplicate"])
def test_only_one_visible_canonical_event_section_can_pass(
    tmp_path: Path,
    concealment: str,
) -> None:
    history, page = _page(
        tmp_path,
        EventCoverage(
            selected_count=2,
            terminal_event_count=1,
            qualified_event_count=1,
            state="qualified",
        ),
    )
    start = page.index("## 중요 사건 반영")
    canonical = page[start:]
    altered = canonical.replace("50.0%", "100.0%")
    if concealment == "comment":
        body = page[:start] + "<!--\n" + canonical + "-->\n" + altered
    elif concealment == "fenced":
        body = page[:start] + "```markdown\n" + canonical + "```\n" + altered
    elif concealment == "indented_duplicate":
        body = page + altered.replace("## 중요 사건 반영", "  ## 중요 사건 반영")
    else:
        body = page + altered
    findings = validate_date_quality_consistency(
        DAY,
        segment_texts={},
        history_path=history,
        quality_page_text=body,
    )
    assert any(f.code == CODE_EVENT_COVERAGE_MISMATCH and f.is_failure for f in findings)


def test_all_selected_events_removed_is_not_labeled_nothing_selected(tmp_path: Path) -> None:
    _, page = _page(
        tmp_path,
        EventCoverage(
            selected_count=1,
            terminal_event_count=0,
            qualified_event_count=0,
            state="no_qualifying_event",
            reasons=("finalization_removed",),
        ),
    )
    assert "설명 충족 사건 없음" in page
    assert "선정 사건 없음" not in page
