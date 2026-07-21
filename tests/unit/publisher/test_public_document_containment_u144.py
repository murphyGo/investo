"""U144 Step 4.1 grouped region disposition and outcome contracts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import get_args

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import investo.publisher.public_document as public_document_module
from investo._internal.briefing_extract import CONCLUSION_PREFIX, FALLBACK_BY_PREFIX
from investo._internal.public_quality_language import (
    FORBIDDEN_PUBLIC_PHRASES,
    PUBLIC_WATCHPOINT_LIMITED_TEXT,
    first_forbidden_public_evidence,
    project_public_quality_language,
)
from investo._internal.public_watermark import render_timestamp_watermark
from investo._internal.surface_quality import SurfaceQualityIssue
from investo.models import Briefing
from investo.models.facts import VerifiedFactBundle
from investo.models.segments import DOMESTIC_EQUITY, SegmentCoverage
from investo.publisher._public_document_policy import (
    FINALIZATION_DISPOSITION_PRECEDENCE,
    FinalizationIssueDisposition,
    strongest_surface_disposition,
)
from investo.publisher.public_document import (
    PublicDocumentContext,
    PublicDocumentDraft,
    PublicDocumentLayout,
    PublicDocumentRegion,
    PublicDocumentSupplement,
    PublicRegionExpectation,
    _append_region_block_outcome,
    _new_generated_draft,
    _OwnedSurfaceQualityFinding,
    _RegionDispositionDecision,
    _render_supplement_block,
    _repair_projected_draft,
    _resolve_owned_region_dispositions,
    _SegmentTrustBlockedError,
    _transition_draft,
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


def _canonical_markdown(
    *,
    watchpoint_body: str,
    supplements: tuple[tuple[str, str, str], ...] = (),
    first_viewport_lines: tuple[str, ...] = (),
) -> str:
    lines = [
        f"# {_TARGET_DATE.isoformat()} 국내 증시 시황",
        "",
        "**세그먼트**: [국내](/domestic)",
        "",
        "> 정보 제공용 자동 시황이며 매매 권유가 아닙니다.",
        "",
        *first_viewport_lines,
        *(("",) if first_viewport_lines else ()),
    ]
    for kind, supplement_id, body in supplements:
        region_id = f"{kind}:{supplement_id}"
        lines.extend(
            (
                f"<!-- investo:block {region_id} -->",
                body,
                f"<!-- /investo:block {region_id} -->",
                "",
            )
        )
    lines.extend(
        (
            "## ① 요약",
            "",
            "요약 본문",
            "",
            "## ② 전일 핵심 이슈",
            "",
            "이슈 본문",
            "",
            "## ③ 섹터/수급 동향",
            "",
            "수급 본문",
            "",
            "## ④ 지표·이벤트",
            "",
            "이벤트 본문",
            "",
            "## ⑤ 주요 종목",
            "",
            "종목 본문",
            "",
            "## ⑥ 오늘의 관전 포인트",
            "",
            watchpoint_body,
            "",
            "<details><summary>수집/품질 진단</summary>",
            "정상 수집",
            "</details>",
            "",
            "## ⑦ 면책조항",
            "",
            "본 문서는 정보 제공용입니다.",
        )
    )
    return "\n".join(lines) + "\n"


def _projected_draft(
    markdown: str,
    *,
    supplement_ids: tuple[str, ...] = (),
) -> tuple[PublicDocumentDraft, PublicDocumentContext]:
    expectation = PublicRegionExpectation(
        target_date=_TARGET_DATE,
        segment=DOMESTIC_EQUITY,
        segmented_mode=True,
        supplement_ids=supplement_ids,
        shared_macro_required=False,
        crypto_indicators_required=False,
        channel_anchors_required=False,
        daily_thesis_required=False,
        anchor_table_required=False,
    )
    layout = PublicDocumentLayout.reindex(markdown, expectation=expectation)
    briefing = Briefing(
        target_date=_TARGET_DATE,
        market_summary="요약 본문",
        key_issues="이슈 본문",
        sector_flow="수급 본문",
        indicators_events="이벤트 본문",
        notable_tickers="종목 본문",
        today_watch="확인할 조건",
        disclaimer="본 문서는 정보 제공용입니다.",
        rendered_markdown=markdown,
    )
    generated = _new_generated_draft(
        briefing,
        segment=DOMESTIC_EQUITY,
        layout=layout,
    )
    assembled = _transition_draft(generated, next_phase="assembled")
    projected = _transition_draft(assembled, next_phase="projected")
    context = PublicDocumentContext(
        target_date=_TARGET_DATE,
        expected_segments=(DOMESTIC_EQUITY,),
        input_absences={},
        anchors_by_segment={},
        items_by_segment={},
        coverage_by_segment={
            DOMESTIC_EQUITY: SegmentCoverage(
                segment=DOMESTIC_EQUITY,
                status="normal",
                item_count=1,
                source_count=1,
                categories=("news",),
                missing_categories=(),
            )
        },
        source_outcomes=(),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=_TARGET_DATE),
        entity_observed_at_utc=datetime(2026, 7, 21, tzinfo=UTC),
    )
    return projected, context


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


def test_required_watchpoint_fallback_preserves_heading_and_replaces_only_body() -> None:
    markdown = _canonical_markdown(watchpoint_body="- 관심 영향 데이터 부족")
    projected, context = _projected_draft(markdown)

    repaired = _repair_projected_draft(projected, context)

    assert repaired.phase == "repaired"
    assert repaired.layout.markdown.count("## ⑥ 오늘의 관전 포인트") == 1
    watchpoints = next(
        region for region in repaired.layout.regions if region.region_id == "watchpoints:section"
    )
    body = repaired.layout.markdown[watchpoints.content_start : watchpoints.content_end]
    assert PUBLIC_WATCHPOINT_LIMITED_TEXT in body
    assert "데이터 부족" not in body
    assert repaired.block_outcomes[-1].region_id == "watchpoints:section"
    assert repaired.block_outcomes[-1].disposition == "replaced"


def test_malformed_chart_and_visual_are_omitted_without_dropping_segment() -> None:
    supplements = (
        ("chart", "bad-chart", "source missing"),
        ("visual", "bad-visual", "price missing"),
    )
    markdown = _canonical_markdown(
        watchpoint_body="- 확인할 조건",
        supplements=supplements,
    )
    projected, context = _projected_draft(
        markdown,
        supplement_ids=("bad-chart", "bad-visual"),
    )

    repaired = _repair_projected_draft(projected, context)

    assert repaired.phase == "repaired"
    assert tuple(
        (outcome.region_id, outcome.disposition) for outcome in repaired.block_outcomes
    ) == (("chart:bad-chart", "omitted"), ("visual:bad-visual", "omitted"))
    for region_id in ("chart:bad-chart", "visual:bad-visual"):
        region = next(region for region in repaired.layout.regions if region.region_id == region_id)
        assert repaired.layout.markdown[region.content_start : region.content_end] == ""
        assert f"<!-- investo:block {region_id} -->" in repaired.layout.markdown
        assert f"<!-- /investo:block {region_id} -->" in repaired.layout.markdown


def test_first_viewport_replacements_use_canonical_summary_and_watermark_owners() -> None:
    malformed_watermark = "**기준 시각**: 2026-07-21 KST · 수집창 [깨짐"
    malformed_summary = "> **오늘의 결론**: 확인이 더 필요한 관"
    unrelated_line = "> 정상적인 별도 안내는 유지합니다."
    markdown = _canonical_markdown(
        watchpoint_body="- 확인할 조건",
        first_viewport_lines=(malformed_watermark, malformed_summary, unrelated_line),
    )
    projected, context = _projected_draft(markdown)

    repaired = _repair_projected_draft(projected, context)

    assert render_timestamp_watermark(_TARGET_DATE, DOMESTIC_EQUITY) in repaired.layout.markdown
    assert malformed_watermark not in repaired.layout.markdown
    assert malformed_summary not in repaired.layout.markdown
    assert f"{CONCLUSION_PREFIX} {FALLBACK_BY_PREFIX[CONCLUSION_PREFIX]}" in (
        repaired.layout.markdown
    )
    assert unrelated_line in repaired.layout.markdown
    assert any(
        outcome.block == "first_viewport" and outcome.disposition == "replaced"
        for outcome in repaired.block_outcomes
    )


def test_new_actionable_residual_after_projection_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    markdown = _canonical_markdown(watchpoint_body="- 확인할 조건")
    projected, context = _projected_draft(markdown)

    def inject_required_body_issue(
        layout: PublicDocumentLayout,
        *,
        limitation_reasons: tuple[str, ...],
    ) -> PublicDocumentLayout:
        del limitation_reasons
        return layout.replace_region_body("section:2", "\ninput_hash=late\n\n")

    monkeypatch.setattr(
        public_document_module,
        "project_public_markdown",
        inject_required_body_issue,
    )

    with pytest.raises(_SegmentTrustBlockedError) as blocked:
        _repair_projected_draft(projected, context)
    assert blocked.value.issue_codes == ("document.fallback_exhausted",)


_FORBIDDEN_PROPERTY_TOKENS = (
    *FORBIDDEN_PUBLIC_PHRASES,
    "본문 사용 7",
    "실패 3",
    "0건 2",
    "fallback ratio",
    "Figures Presence",
)


@settings(max_examples=100, deadline=None)
@given(
    fragments=st.lists(
        st.tuples(
            st.sampled_from(_FORBIDDEN_PROPERTY_TOKENS),
            st.sampled_from(("", " ", " / ", " · ", "\n")),
        ),
        min_size=1,
        max_size=12,
    )
)
def test_forbidden_public_label_combinations_close_idempotently(
    fragments: list[tuple[str, str]],
) -> None:
    raw = "".join(f"{token}{separator}" for token, separator in fragments)

    projected = project_public_quality_language(raw)

    assert first_forbidden_public_evidence(projected) is None
    assert project_public_quality_language(projected) == projected


@settings(max_examples=100, deadline=None)
@given(
    kind=st.sampled_from(("chart", "visual")),
    suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=24),
    body=st.tuples(
        st.sampled_from(tuple("가나다abcXYZ0123")),
        st.text(alphabet="가나다라마바사 abcXYZ0123|:_-.\n", max_size=119),
    ).map(lambda parts: "".join(parts)),
    stable_order=st.integers(min_value=0, max_value=10_000),
    artifact_ids=st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=16),
        unique=True,
        max_size=4,
    ).map(lambda values: [f"artifact-{value}" for value in values]),
)
def test_supplement_delimiters_stay_balanced_for_optional_field_combinations(
    kind: str,
    suffix: str,
    body: str,
    stable_order: int,
    artifact_ids: list[str],
) -> None:
    supplement = PublicDocumentSupplement(
        supplement_id=f"asset-{suffix}",
        kind=kind,  # type: ignore[arg-type]
        markdown=body,
        stable_order=stable_order,
        artifact_ids=tuple(artifact_ids),
    )

    rendered = _render_supplement_block(supplement)
    opening = f"<!-- investo:block {kind}:asset-{suffix} -->"
    closing = f"<!-- /investo:block {kind}:asset-{suffix} -->"

    assert rendered.count(opening) == 1
    assert rendered.count(closing) == 1
    assert rendered.index(opening) < rendered.index(closing)


@settings(max_examples=100, deadline=None)
@given(
    tokens=st.lists(
        st.sampled_from(_FORBIDDEN_PROPERTY_TOKENS),
        min_size=1,
        max_size=8,
    ),
    separator=st.sampled_from((" ", " / ", " · ", "\n- ")),
)
def test_required_block_fallback_is_deterministic(
    tokens: list[str],
    separator: str,
) -> None:
    markdown = _canonical_markdown(
        watchpoint_body=f"- {separator.join(tokens)}",
    )
    first_projected, first_context = _projected_draft(markdown)
    second_projected, second_context = _projected_draft(markdown)

    first = _repair_projected_draft(first_projected, first_context)
    second = _repair_projected_draft(second_projected, second_context)

    assert first.layout.markdown == second.layout.markdown
    assert first.block_outcomes == second.block_outcomes
    assert first.layout.markdown.count(PUBLIC_WATCHPOINT_LIMITED_TEXT) == 1


_ORDERABLE_FINDINGS = (
    ("first_viewport:1", "first_viewport", "bad_token.bulganghanseong"),
    ("first_viewport:1", "first_viewport", "markdown.broken_numeric_bold"),
    ("first_viewport:1", "first_viewport", "summary.truncated_mid_token"),
    ("first_viewport:1", "first_viewport", "template.repeated_phrase"),
    ("watchpoints:section", "watchpoints", "ellipsis.dangling_line"),
    ("watchpoints:section", "watchpoints", "public_diagnostic.raw_label"),
    ("watchpoints:section", "watchpoints", "trace.fragment"),
    ("watchpoints:section", "watchpoints", "template.repeated_phrase"),
)


@settings(max_examples=100, deadline=None)
@given(entries=st.lists(st.sampled_from(_ORDERABLE_FINDINGS), min_size=1, max_size=24))
def test_grouped_issue_order_is_stable_for_arbitrary_input_order(
    entries: list[tuple[str, str, str]],
) -> None:
    findings = tuple(_finding(region_id, block, code) for region_id, block, code in entries)

    decisions = _resolve_owned_region_dispositions(_layout(), findings)

    expected_regions = tuple(
        region_id
        for region_id in ("first_viewport:1", "watchpoints:section")
        if any(entry[0] == region_id for entry in entries)
    )
    assert tuple(decision.region_id for decision in decisions) == expected_regions
    for decision in decisions:
        assert decision.issue_codes == tuple(
            sorted({code for region_id, _block, code in entries if region_id == decision.region_id})
        )
