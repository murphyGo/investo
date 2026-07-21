"""u144 Step 0 — freeze the legacy producer/gate incident behavior."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from investo._internal.public_quality_language import (
    PUBLIC_WATCHPOINT_LIMITED_TEXT,
    first_forbidden_public_evidence,
)
from investo._internal.surface_quality import find_surface_quality_issues
from investo.models.segments import US_EQUITY
from investo.publisher.quality_consistency import (
    CODE_BODY_EVIDENCE_UNTRACKED,
    build_canonical_snapshot,
    check_quality_consistency,
    parse_segment_status_block,
)
from investo.publisher.reader_format import (
    normalize_data_limited_reader_copy,
    reflow_first_viewport,
)
from investo.publisher.watchpoint_matrix import (
    build_watchpoint_rows,
    render_watchpoint_matrix,
)

_FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "u144"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _blocking_codes(markdown: str) -> tuple[str, ...]:
    return tuple(
        issue.code for issue in find_surface_quality_issues(markdown) if issue.severity == "block"
    )


def _quality_failure_codes(markdown: str) -> frozenset[str]:
    snapshot = build_canonical_snapshot(
        date(2026, 7, 17),
        segment_texts={US_EQUITY: markdown},
        history_row={
            "date": "2026-07-17",
            "worst_severity": "normal",
            "total_failed_sources": 0,
        },
    )
    return frozenset(
        finding.code
        for finding in check_quality_consistency(snapshot, quality_page_text=None)
        if finding.is_failure
    )


def test_watchpoint_incident_fixture_now_uses_safe_producer_default() -> None:
    fixture = _load_fixture("run-29707052598-watchpoint-reintroduction.json")
    before = fixture["markdown_before_watchpoint"]

    # Legacy ordering projects visible text before the watchpoint producer.
    assert normalize_data_limited_reader_copy(before) == before

    rows = build_watchpoint_rows(fixture["input_bullets"])
    assert len(rows) == 1
    legacy_row = fixture["expected_row"]
    assert first_forbidden_public_evidence(legacy_row["implication"]) is not None
    for field, value in legacy_row.items():
        if field != "implication":
            assert getattr(rows[0], field) == value
    assert rows[0].implication == PUBLIC_WATCHPOINT_LIMITED_TEXT

    rendered = render_watchpoint_matrix(
        before,
        segment=fixture["incident"]["segment"],
    )
    assert _blocking_codes(fixture["markdown_after_watchpoint"]) == tuple(
        fixture["expected_pre_u144"]["blocking_issue_codes"]
    )
    assert rendered != fixture["markdown_after_watchpoint"]
    assert _blocking_codes(rendered) == ()


@pytest.mark.parametrize("case_index", range(3))
def test_historical_first_viewport_gate_corpus_and_current_repair(case_index: int) -> None:
    fixture = _load_fixture("first-viewport-truncation-family.json")
    case = fixture["cases"][case_index]

    # These are historical post-reflow incident strings, not output the current
    # producer still emits. Keep the old detector evidence while proving the
    # current producer repairs the malformed shape before the terminal gate.
    assert fixture["fixture_role"] == "historical_gate_corpus"
    assert _blocking_codes(case["markdown_before_reflow"]) == ()
    assert _blocking_codes(case["markdown_after_reflow"]) == tuple(case["expected_issue_codes"])
    current_output = reflow_first_viewport(
        case["markdown_after_reflow"],
        segment=US_EQUITY,
    )
    assert current_output == case["current_reflow_output"]
    assert _blocking_codes(current_output) == ()


def test_projection_removes_body_evidence_signal_before_later_accounting_gate() -> None:
    fixture = _load_fixture("body-evidence-projection-mismatch.json")
    before = fixture["markdown_before_projection"]
    after = fixture["markdown_after_projection"]
    expected = fixture["expected_pre_u144"]

    before_status = parse_segment_status_block(before, US_EQUITY)
    assert before_status.known_body_evidence_count == expected["known_body_evidence_count"]
    assert before_status.body_used_count == expected["parsed_body_used_count_before_projection"]
    assert before_status.body_used_observed is expected["body_used_observed_before_projection"]
    assert CODE_BODY_EVIDENCE_UNTRACKED in _quality_failure_codes(before)

    assert normalize_data_limited_reader_copy(before) == after
    after_status = parse_segment_status_block(after, US_EQUITY)
    assert after_status.known_body_evidence_count == expected["known_body_evidence_count"]
    assert after_status.body_used_count == expected["parsed_body_used_count_after_projection"]
    assert after_status.body_used_observed is expected["body_used_observed_after_projection"]
    assert CODE_BODY_EVIDENCE_UNTRACKED not in _quality_failure_codes(after)
