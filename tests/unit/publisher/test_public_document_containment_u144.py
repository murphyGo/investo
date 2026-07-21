"""U144 Step 4.1 grouped region disposition and outcome contracts."""

from __future__ import annotations

from datetime import date
from typing import get_args

import pytest

from investo._internal.surface_quality import SurfaceQualityIssue
from investo.models.segments import DOMESTIC_EQUITY
from investo.publisher._public_document_policy import (
    FINALIZATION_DISPOSITION_PRECEDENCE,
    FinalizationIssueDisposition,
    strongest_surface_disposition,
)
from investo.publisher.public_document import (
    PublicDocumentLayout,
    PublicDocumentRegion,
    PublicRegionExpectation,
    _append_region_block_outcome,
    _OwnedSurfaceQualityFinding,
    _RegionDispositionDecision,
    _resolve_owned_region_dispositions,
    _SegmentTrustBlockedError,
)

_TARGET_DATE = date(2026, 7, 21)


def _layout() -> PublicDocumentLayout:
    markdown = "요약 본문관전 본문"
    expectation = PublicRegionExpectation(
        target_date=_TARGET_DATE,
        segment=DOMESTIC_EQUITY,
        segmented_mode=True,
        supplement_ids=(),
        shared_macro_required=False,
        crypto_indicators_required=False,
        channel_anchors_required=False,
        daily_thesis_required=False,
        anchor_table_required=False,
    )
    return PublicDocumentLayout(
        markdown=markdown,
        regions=(
            PublicDocumentRegion(
                region_id="first_viewport:1",
                block="first_viewport",
                required=True,
                projection_policy="reader_visible",
                start=0,
                end=5,
                content_start=0,
                content_end=5,
            ),
            PublicDocumentRegion(
                region_id="watchpoints:section",
                block="watchpoints",
                required=True,
                projection_policy="reader_visible",
                start=5,
                end=len(markdown),
                content_start=5,
                content_end=len(markdown),
            ),
        ),
        expectation=expectation,
    )


def _finding(
    region_id: str,
    block: str,
    issue_code: str,
    *,
    evidence: str = "private evidence must not enter outcomes",
) -> _OwnedSurfaceQualityFinding:
    return _OwnedSurfaceQualityFinding(
        region_id=region_id,
        block=block,  # type: ignore[arg-type]
        issue=SurfaceQualityIssue(
            code=issue_code,
            severity="warn",
            evidence=evidence,
            region="body",
        ),
    )


def test_disposition_precedence_is_exhaustive_and_fixed() -> None:
    assert set(FINALIZATION_DISPOSITION_PRECEDENCE) == set(get_args(FinalizationIssueDisposition))
    assert FINALIZATION_DISPOSITION_PRECEDENCE == (
        "block_segment",
        "omit_optional_block",
        "replace_block",
        "repair",
        "record_warning",
    )
    assert (
        strongest_surface_disposition(
            ("ellipsis.dangling_line", "summary.truncated_mid_token"),
            "first_viewport",
        )
        == "replace_block"
    )


def test_multiple_findings_group_once_in_region_order_and_record_redacted_outcomes() -> None:
    findings = (
        _finding(
            "watchpoints:section",
            "watchpoints",
            "ellipsis.dangling_line",
        ),
        _finding(
            "first_viewport:1",
            "first_viewport",
            "markdown.broken_numeric_bold",
        ),
        _finding(
            "watchpoints:section",
            "watchpoints",
            "public_diagnostic.raw_label",
        ),
        _finding(
            "first_viewport:1",
            "first_viewport",
            "bad_token.bulganghanseong",
        ),
    )

    decisions = _resolve_owned_region_dispositions(_layout(), findings)

    assert tuple(decision.region_id for decision in decisions) == (
        "first_viewport:1",
        "watchpoints:section",
    )
    assert decisions[0].issue_codes == (
        "bad_token.bulganghanseong",
        "markdown.broken_numeric_bold",
    )
    assert decisions[0].disposition == "repair"
    assert decisions[1].issue_codes == (
        "ellipsis.dangling_line",
        "public_diagnostic.raw_label",
    )
    assert decisions[1].disposition == "replace_block"

    outcomes = _append_region_block_outcome((), decisions[0])
    outcomes = _append_region_block_outcome(outcomes, decisions[1])

    assert tuple(outcome.disposition for outcome in outcomes) == ("repaired", "replaced")
    assert tuple(outcome.issue_codes for outcome in outcomes) == tuple(
        decision.issue_codes for decision in decisions
    )
    assert all("private evidence" not in repr(outcome) for outcome in outcomes)


@pytest.mark.parametrize(
    ("issue_code", "block", "expected"),
    (
        ("template.repeated_phrase", "first_viewport", "kept"),
        ("bad_token.bulganghanseong", "first_viewport", "repaired"),
        ("summary.truncated_mid_token", "first_viewport", "replaced"),
        ("ellipsis.dangling_line", "visual", "omitted"),
        ("trace.fragment", "watchpoints", None),
    ),
)
def test_every_finalization_disposition_has_one_outcome_or_trust_block(
    issue_code: str,
    block: str,
    expected: str | None,
) -> None:
    disposition = strongest_surface_disposition(
        (issue_code,),
        block,  # type: ignore[arg-type]
    )
    decision = _RegionDispositionDecision(
        region_id="region:one",
        block=block,  # type: ignore[arg-type]
        issue_codes=(issue_code,),
        disposition=disposition,
    )
    if expected is None:
        with pytest.raises(_SegmentTrustBlockedError):
            _append_region_block_outcome((), decision)
        return

    outcome = _append_region_block_outcome((), decision)[0]
    assert outcome.disposition == expected


def test_repeat_and_block_dispositions_fail_without_a_second_outcome() -> None:
    decision = _resolve_owned_region_dispositions(
        _layout(),
        (_finding("first_viewport:1", "first_viewport", "bad_token.bulganghanseong"),),
    )[0]
    outcomes = _append_region_block_outcome((), decision)

    with pytest.raises(_SegmentTrustBlockedError) as repeated:
        _append_region_block_outcome(outcomes, decision)
    assert repeated.value.issue_codes == ("document.fallback_repeat",)

    blocked = _resolve_owned_region_dispositions(
        _layout(),
        (_finding("watchpoints:section", "watchpoints", "trace.fragment"),),
    )[0]
    assert blocked.disposition == "block_segment"
    with pytest.raises(_SegmentTrustBlockedError) as trust_blocked:
        _append_region_block_outcome(outcomes, blocked)
    assert trust_blocked.value.issue_codes == ("trace.fragment",)


def test_finding_ownership_must_match_the_indexed_region() -> None:
    with pytest.raises(ValueError, match=r"invariant\.finding_ownership"):
        _resolve_owned_region_dispositions(
            _layout(),
            (_finding("watchpoints:section", "section_body", "ellipsis.dangling_line"),),
        )
