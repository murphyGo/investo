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
from investo._internal.surface_quality import SurfaceLinkShape, SurfaceQualityIssue
from investo.models import Briefing, PublicNotificationSummary, SegmentFinalizationOutcome
from investo.models.facts import VerifiedFactBundle
from investo.models.segments import DOMESTIC_EQUITY, SegmentCoverage
from investo.publisher._public_document_policy import (
    FINALIZATION_DISPOSITION_PRECEDENCE,
    FinalizationIssueDisposition,
    strongest_surface_disposition,
)
from investo.publisher.compliance_language import ComplianceLanguageError
from investo.publisher.public_document import (
    PublicDocumentContext,
    PublicDocumentDraft,
    PublicDocumentLayout,
    PublicDocumentRegion,
    PublicDocumentSupplement,
    PublicRegionExpectation,
    _append_region_block_outcome,
    _collect_terminal_hard_gates,
    _find_owned_surface_quality_issues,
    _new_generated_draft,
    _OwnedSurfaceQualityFinding,
    _RegionDispositionDecision,
    _render_supplement_block,
    _repair_projected_draft,
    _resolve_owned_region_dispositions,
    _SegmentTrustBlockedError,
    _terminal_failure_issue_codes,
    _TerminalHardGateSnapshot,
    _transition_draft,
    _validate_repaired_draft,
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
    link_shape: SurfaceLinkShape | None = None,
) -> _OwnedSurfaceQualityFinding:
    return _OwnedSurfaceQualityFinding(
        region_id=region_id,
        block=block,  # type: ignore[arg-type]
        issue=SurfaceQualityIssue(
            code=issue_code,
            severity="warn",
            evidence=evidence,
            region="body",
            link_shape=link_shape,
        ),
    )


def _isolate_terminal_surface_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        public_document_module,
        "validate_first_viewport_summary",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        public_document_module,
        "verify_disclaimer",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        public_document_module,
        "verify_short_disclaimer_first_viewport",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        public_document_module,
        "_derive_public_notification_summary",
        lambda draft, _context: PublicNotificationSummary(
            segment=draft.segment,
            target_date=draft.target_date,
            conclusion="[관망] 확인된 결론",
            coverage_status="normal",
            coverage_label="정상",
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
    anchor_table_required: bool = False,
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
        anchor_table_required=anchor_table_required,
    )
    layout = PublicDocumentLayout.reindex(markdown, expectation=expectation)
    rendered_disclaimer = markdown.split("## ⑦ 면책조항\n\n", 1)[1].strip()
    briefing = Briefing(
        target_date=_TARGET_DATE,
        market_summary="요약 본문",
        key_issues="이슈 본문",
        sector_flow="수급 본문",
        indicators_events="이벤트 본문",
        notable_tickers="종목 본문",
        today_watch="확인할 조건",
        disclaimer=rendered_disclaimer,
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


def test_truncated_summary_finding_is_owned_only_by_actual_first_viewport() -> None:
    body_markdown = _canonical_markdown(watchpoint_body="- 공급망 관")
    body_draft, _ = _projected_draft(body_markdown)

    assert all(
        finding.issue.code != "summary.truncated_mid_token"
        for finding in _find_owned_surface_quality_issues(body_draft.layout)
    )

    viewport_markdown = _canonical_markdown(
        watchpoint_body="- 확인할 조건",
        first_viewport_lines=("공급망 관...",),
    )
    viewport_draft, _ = _projected_draft(viewport_markdown)
    findings = _find_owned_surface_quality_issues(viewport_draft.layout)

    assert any(
        finding.issue.code == "summary.truncated_mid_token" and finding.block == "first_viewport"
        for finding in findings
    )


@pytest.mark.parametrize("repeats", [10, 270, 400])
def test_u153_region_local_scan_keeps_body_callout_continuations_unowned(repeats: int) -> None:
    markdown = _canonical_markdown(watchpoint_body="- 확인할 조건").replace(
        "수급 본문", "몸통 설명 " * repeats + "\n> **오늘의 결론**: 기관의 본문 참고."
    )
    draft, _ = _projected_draft(markdown)
    assert all(
        finding.issue.code != "summary.truncated_mid_token"
        for finding in _find_owned_surface_quality_issues(draft.layout)
    )
    assert draft.layout.markdown == markdown


def test_u153_region_local_scan_still_owns_real_viewport_continuations() -> None:
    markdown = _canonical_markdown(
        watchpoint_body="- 확인할 조건",
        first_viewport_lines=("설명 " * 600, "> **오늘의 결론**: 기관의 본문 참고."),
    )
    draft, _ = _projected_draft(markdown)
    findings = _find_owned_surface_quality_issues(draft.layout)
    assert any(
        finding.issue.code == "summary.truncated_mid_token" and finding.block == "first_viewport"
        for finding in findings
    )


def test_owned_bounded_body_truncation_findings_use_owner_specific_codes() -> None:
    watchpoint_markdown = _canonical_markdown(
        watchpoint_body="#### 관찰 신호: CoinGecko BTC · UTC 24h…"
    )
    watchpoint_draft, _ = _projected_draft(watchpoint_markdown)
    watchpoint_findings = _find_owned_surface_quality_issues(watchpoint_draft.layout)

    assert any(
        finding.issue.code == "watchpoint.title_truncated_surface"
        and finding.block == "watchpoints"
        for finding in watchpoint_findings
    )

    meaning_markdown = _canonical_markdown(watchpoint_body="- 확인할 조건").replace(
        "수급 본문",
        "> **그래서 의미는?** 수급 변화가 특정 지역의...",
    )
    meaning_draft, _ = _projected_draft(meaning_markdown)
    meaning_findings = _find_owned_surface_quality_issues(meaning_draft.layout)

    assert any(
        finding.issue.code == "meaning.truncated_surface" and finding.block == "section_body"
        for finding in meaning_findings
    )


@pytest.mark.parametrize(
    ("body", "expected_region", "expected_code", "expected_fallback"),
    (
        (
            "> **그래서 의미는?** 수급 변화가 특정 지역의...",
            "section:3",
            "meaning.truncated_surface",
            "검증된 수치 근거가 부족해 이 섹션의 정밀 판단을 보류합니다.",
        ),
        (
            "#### 관찰 신호: CoinGecko BTC · UTC 24h…",
            "watchpoints:section",
            "watchpoint.title_truncated_surface",
            PUBLIC_WATCHPOINT_LIMITED_TEXT,
        ),
    ),
)
def test_body_owned_structural_truncation_is_contained_in_its_region(
    body: str,
    expected_region: str,
    expected_code: str,
    expected_fallback: str,
) -> None:
    markdown = _canonical_markdown(watchpoint_body="- 확인할 조건")
    if expected_region == "section:3":
        markdown = markdown.replace("수급 본문", body)
    else:
        markdown = markdown.replace("- 확인할 조건", body)
    projected, context = _projected_draft(markdown)

    repaired = _repair_projected_draft(projected, context)

    assert repaired.phase == "repaired"
    outcome = next(item for item in repaired.block_outcomes if item.region_id == expected_region)
    assert outcome.disposition == "replaced"
    assert outcome.issue_codes == (expected_code,)
    region = next(item for item in repaired.layout.regions if item.region_id == expected_region)
    region_body = repaired.layout.markdown[region.content_start : region.content_end]
    assert expected_fallback in region_body
    assert body not in repaired.layout.markdown


@pytest.mark.parametrize(
    ("body", "expected_region", "expected_codes", "expected_fallback"),
    (
        (
            "> **그래서 의미는?** [수급](https://example.invalid/a/...) 흐름...",
            "section:3",
            ("markdown.href_ellipsis", "meaning.truncated_surface"),
            "검증된 수치 근거가 부족해 이 섹션의 정밀 판단을 보류합니다.",
        ),
        (
            "#### 관찰 신호: [국채](https://example.invalid/a/...) 변동…",
            "watchpoints:section",
            ("markdown.href_ellipsis", "watchpoint.title_truncated_surface"),
            PUBLIC_WATCHPOINT_LIMITED_TEXT,
        ),
    ),
)
def test_link_and_body_truncation_are_grouped_into_one_local_containment(
    body: str,
    expected_region: str,
    expected_codes: tuple[str, ...],
    expected_fallback: str,
) -> None:
    markdown = _canonical_markdown(watchpoint_body="- 확인할 조건")
    if expected_region == "section:3":
        markdown = markdown.replace("수급 본문", body)
    else:
        markdown = markdown.replace("- 확인할 조건", body)
    projected, context = _projected_draft(markdown)

    repaired = _repair_projected_draft(projected, context)

    assert repaired.phase == "repaired"
    assert len(repaired.block_outcomes) == 1
    outcome = repaired.block_outcomes[0]
    assert outcome.region_id == expected_region
    assert outcome.disposition == "replaced"
    assert outcome.issue_codes == expected_codes
    assert expected_fallback in repaired.layout.markdown
    assert body not in repaired.layout.markdown
    assert not _find_owned_surface_quality_issues(repaired.layout)


@pytest.mark.parametrize(
    ("body", "expected_region", "expected_disposition"),
    (
        (
            "> **그래서 의미는?** [수급](https://example.invalid/a/...",
            "section:3",
            "repaired",
        ),
        (
            "#### 관찰 신호: [국채](https://example.invalid/a/...",
            "watchpoints:section",
            "replaced",
        ),
    ),
)
def test_incomplete_link_does_not_impersonate_body_truncation(
    body: str,
    expected_region: str,
    expected_disposition: str,
) -> None:
    markdown = _canonical_markdown(watchpoint_body="- 확인할 조건")
    if expected_region == "section:3":
        markdown = markdown.replace("수급 본문", body)
    else:
        markdown = markdown.replace("- 확인할 조건", body)
    projected, context = _projected_draft(markdown)

    findings = _find_owned_surface_quality_issues(projected.layout)
    repaired = _repair_projected_draft(projected, context)

    owner_codes = tuple(
        finding.issue.code for finding in findings if finding.region_id == expected_region
    )
    assert owner_codes == ("markdown.unmatched_link",)
    assert len(repaired.block_outcomes) == 1
    outcome = repaired.block_outcomes[0]
    assert outcome.region_id == expected_region
    assert outcome.disposition == expected_disposition
    assert outcome.issue_codes == ("markdown.unmatched_link",)
    assert body not in repaired.layout.markdown


@pytest.mark.parametrize(
    "hard_code",
    ("entity.fact_contradiction", "compliance.language"),
)
def test_non_surface_hard_gate_blocks_before_body_fallback(
    hard_code: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    markdown = _canonical_markdown(watchpoint_body="- 확인할 조건").replace(
        "수급 본문",
        "> **그래서 의미는?** 수급 변화가 특정 지역의...",
    )
    projected, context = _projected_draft(markdown)
    if hard_code == "entity.fact_contradiction":
        monkeypatch.setattr(
            public_document_module,
            "_scan_terminal_entity_fact_claims",
            lambda *_args, **_kwargs: (object(),),
        )
    else:

        def reject_compliance(*_args: object, **_kwargs: object) -> None:
            raise ComplianceLanguageError(segment=DOMESTIC_EQUITY, hits=())

        monkeypatch.setattr(
            public_document_module,
            "_scan_terminal_compliance",
            reject_compliance,
        )

    with pytest.raises(_SegmentTrustBlockedError) as blocked:
        _repair_projected_draft(projected, context)

    assert blocked.value.phase == "repaired"
    assert blocked.value.issue_codes == (
        hard_code,
        "meaning.truncated_surface",
    )


def test_early_hard_gate_snapshot_keeps_every_actionable_surface_code() -> None:
    markdown = (
        _canonical_markdown(watchpoint_body="- 확인할 조건")
        .replace(
            "수급 본문",
            "> **그래서 의미는?** KOSPI **+1.20%** 상승...",
        )
        .replace(
            "**세그먼트**: [국내](/domestic)",
            "**세그먼트**: [국내](https://example.invalid/a/...)",
        )
    )
    projected, context = _projected_draft(markdown)

    with pytest.raises(_SegmentTrustBlockedError) as blocked:
        _repair_projected_draft(projected, context)

    assert blocked.value.issue_codes == (
        "markdown.href_ellipsis",
        "meaning.truncated_surface",
        "numeric.anchor_assertion",
    )


def test_complete_body_noun_endings_do_not_create_region_outcomes() -> None:
    markdown = _canonical_markdown(watchpoint_body="#### 관찰 신호: 미 국채").replace(
        "수급 본문",
        "> **그래서 의미는?** 주요 매수 주체는 기관",
    )
    projected, context = _projected_draft(markdown)

    repaired = _repair_projected_draft(projected, context)

    assert repaired.phase == "repaired"
    assert repaired.block_outcomes == ()
    assert repaired.layout.markdown == markdown


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


def test_repeated_link_code_uses_every_shape_before_redacting_the_region_decision() -> None:
    findings = (
        _finding(
            "first_viewport:1",
            "first_viewport",
            "markdown.href_ellipsis",
            link_shape="inline_link",
        ),
        _finding(
            "first_viewport:1",
            "first_viewport",
            "markdown.href_ellipsis",
            link_shape="reference_definition",
        ),
    )

    decision = _resolve_owned_region_dispositions(_layout(), findings)[0]

    assert decision.issue_codes == ("markdown.href_ellipsis",)
    assert decision.disposition == "replace_block"
    assert "link_shape" not in repr(decision)
    assert "private evidence" not in repr(decision)


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


def test_invalid_link_chart_and_visual_are_omitted_without_dropping_segment() -> None:
    supplements = (
        ("chart", "bad-chart", "[차트](https://example.invalid/chart/...)"),
        ("visual", "bad-visual", "![시각화](https://example.invalid/visual/…)"),
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


@pytest.mark.parametrize(
    ("protected_block", "needle"),
    (
        ("diagnostics", "정상 수집"),
        ("disclaimer", "본 문서는 정보 제공용입니다."),
    ),
)
def test_protected_region_link_finding_reaches_fail_closed_policy(
    protected_block: str,
    needle: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = "[비공개](https://example.invalid/protected/...)"
    markdown = _canonical_markdown(watchpoint_body="- 확인할 조건").replace(needle, invalid)
    projected, context = _projected_draft(markdown)
    _isolate_terminal_surface_gates(monkeypatch)

    findings = _find_owned_surface_quality_issues(projected.layout)
    link_finding = next(
        finding
        for finding in findings
        if finding.block == protected_block and finding.issue.code == "markdown.href_ellipsis"
    )
    assert link_finding.issue.region == "segment_first_viewport"

    repaired = _repair_projected_draft(projected, context)
    assert invalid in repaired.layout.markdown
    assert all(outcome.block != protected_block for outcome in repaired.block_outcomes)
    with pytest.raises(_SegmentTrustBlockedError) as blocked:
        _validate_repaired_draft(repaired, context)
    assert blocked.value.issue_codes == ("markdown.href_ellipsis",)


def test_anchor_table_invalid_link_is_not_mutated_and_blocks_segment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = "[비공개](https://example.invalid/anchor/...)"
    anchor_table = (
        "| 종목 | 종가 | 변동 | 비고 |\n"
        "|------|------|------|------|\n"
        f"| KOSPI | {invalid} | +1.0% | 마감 |\n\n"
    )
    markdown = _canonical_markdown(watchpoint_body="- 확인할 조건").replace(
        "## ① 요약",
        f"{anchor_table}## ① 요약",
    )
    projected, context = _projected_draft(markdown, anchor_table_required=True)
    _isolate_terminal_surface_gates(monkeypatch)

    repaired = _repair_projected_draft(projected, context)

    assert invalid in repaired.layout.markdown
    assert all(outcome.block != "anchor_table" for outcome in repaired.block_outcomes)
    with pytest.raises(_SegmentTrustBlockedError) as blocked:
        _validate_repaired_draft(repaired, context)
    assert blocked.value.issue_codes == ("markdown.href_ellipsis",)


def test_section_markdown_table_link_uses_protected_direct_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = "[비공개](https://example.invalid/table/...)"
    table = f"열 A | 열 B\n--- | ---\n값 | {invalid}"
    markdown = _canonical_markdown(watchpoint_body="- 확인할 조건").replace(
        "이슈 본문",
        table,
        1,
    )
    projected, context = _projected_draft(markdown)
    _isolate_terminal_surface_gates(monkeypatch)

    repaired = _repair_projected_draft(projected, context)

    assert invalid in repaired.layout.markdown
    assert all(outcome.region_id != "section:2" for outcome in repaired.block_outcomes)
    with pytest.raises(_SegmentTrustBlockedError) as blocked:
        _validate_repaired_draft(repaired, context)
    assert blocked.value.issue_codes == ("markdown.href_ellipsis",)


@pytest.mark.parametrize(
    "fragment",
    (
        "[<https://example.invalid/inner/...>](https://example.invalid/outer/...)",
        "![대체문구](https://example.invalid/incomplete...",
    ),
)
def test_ambiguous_link_shape_replaces_owner_without_false_repaired_outcome(
    fragment: str,
) -> None:
    markdown = _canonical_markdown(watchpoint_body="- 확인할 조건").replace(
        "요약 본문",
        fragment,
        1,
    )
    projected, context = _projected_draft(markdown)

    repaired = _repair_projected_draft(projected, context)

    outcome = next(
        outcome for outcome in repaired.block_outcomes if outcome.region_id == "section:1"
    )
    assert outcome.disposition == "replaced"
    assert "markdown.unmatched_link" in outcome.issue_codes
    assert fragment not in repaired.layout.markdown


def test_first_viewport_replacements_use_canonical_summary_and_watermark_owners() -> None:
    malformed_watermark = "**기준 시각**: 2026-07-21 KST · 수집창 invalid"
    malformed_summary = "> **오늘의 결론**: 확인이 더 필요..."
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


@pytest.mark.parametrize(
    ("special_line", "special_code"),
    (
        ("**기준 시각**: 2026-07-21 KST · 수집창 invalid", "watermark.window_bracket"),
        ("> **오늘의 결론**: 확인이 더 필요...", "summary.truncated_mid_token"),
    ),
)
def test_unrecoverable_first_viewport_link_uses_the_stronger_whole_region_replacement(
    special_line: str,
    special_code: str,
) -> None:
    reference = "[synthetic-ref]: https://example.invalid/path/..."
    markdown = _canonical_markdown(
        watchpoint_body="- 확인할 조건",
        first_viewport_lines=(special_line, reference),
    )
    projected, context = _projected_draft(markdown)

    repaired = _repair_projected_draft(projected, context)

    outcome = next(
        outcome
        for outcome in repaired.block_outcomes
        if outcome.block == "first_viewport" and "markdown.href_ellipsis" in outcome.issue_codes
    )
    assert outcome.disposition == "replaced"
    assert outcome.issue_codes == tuple(sorted((special_code, "markdown.href_ellipsis")))
    assert reference not in repaired.layout.markdown
    assert special_line not in repaired.layout.markdown
    assert repaired.layout.markdown.count("## ① 요약") == 1
    assert "## ② 전일 핵심 이슈\n\n이슈 본문" in repaired.layout.markdown


def test_stronger_link_replacement_prevents_pre_or_post_cosmetic_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    markdown = _canonical_markdown(watchpoint_body="- 확인할 조건").replace(
        "요약 본문",
        "불강한성\n[synthetic-ref]: https://example.invalid/path/...",
        1,
    )
    projected, context = _projected_draft(markdown)

    def reject_extra_repair(_text: str) -> str:
        raise AssertionError("cosmetic repair must not run before or after replacement")

    monkeypatch.setattr(
        public_document_module,
        "repair_surface_artifacts",
        reject_extra_repair,
    )

    repaired = _repair_projected_draft(projected, context)

    outcome = next(
        outcome for outcome in repaired.block_outcomes if outcome.region_id == "section:1"
    )
    assert outcome.disposition == "replaced"
    assert outcome.issue_codes == (
        "bad_token.bulganghanseong",
        "markdown.href_ellipsis",
    )
    assert "example.invalid" not in repaired.layout.markdown
    assert repaired.layout.markdown.count("## ① 요약") == 1
    assert "## ② 전일 핵심 이슈\n\n이슈 본문" in repaired.layout.markdown


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
    _isolate_terminal_surface_gates(monkeypatch)

    repaired = _repair_projected_draft(projected, context)

    with pytest.raises(_SegmentTrustBlockedError) as blocked:
        _validate_repaired_draft(repaired, context)
    assert blocked.value.issue_codes == ("trace.fragment",)


def test_actionable_link_residual_keeps_exact_code_and_simultaneous_hard_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    markdown = _canonical_markdown(watchpoint_body="- 확인할 조건")
    projected, context = _projected_draft(markdown)
    private_line = (
        "[private label](https://example.invalid/path/...?token=synthetic-secret-must-not-escape)"
    )

    def inject_required_body_link(
        layout: PublicDocumentLayout,
        *,
        limitation_reasons: tuple[str, ...],
    ) -> PublicDocumentLayout:
        del limitation_reasons
        return layout.replace_region_body("section:2", f"\n{private_line}\n\n")

    monkeypatch.setattr(
        public_document_module,
        "project_public_markdown",
        inject_required_body_link,
    )
    monkeypatch.setattr(
        public_document_module,
        "_scan_terminal_entity_fact_claims",
        lambda *_args, **_kwargs: (object(),),
    )
    _isolate_terminal_surface_gates(monkeypatch)

    repaired = _repair_projected_draft(projected, context)
    snapshot = _collect_terminal_hard_gates(repaired, context)

    assert snapshot.issue_codes == (
        "entity.fact_contradiction",
        "markdown.href_ellipsis",
    )
    assert snapshot.residual_actionable_link_codes == ("markdown.href_ellipsis",)
    assert snapshot.notification_summary is None
    with pytest.raises(_SegmentTrustBlockedError) as blocked:
        _validate_repaired_draft(repaired, context)
    assert blocked.value.phase == "validated"
    assert blocked.value.issue_codes == (
        "document.fallback_exhausted",
        "entity.fact_contradiction",
        "markdown.href_ellipsis",
    )

    typed_outcome = SegmentFinalizationOutcome(
        segment=DOMESTIC_EQUITY,
        state="trust_blocked",
        issue_codes=blocked.value.issue_codes,
    )
    forbidden = (
        "private label",
        "example.invalid",
        "synthetic-secret",
        "section:2",
        "inline_link",
        "https://example.invalid/path/...",
    )
    bounded_surfaces = (
        repr(snapshot),
        str(blocked.value),
        repr(blocked.value),
        repr(typed_outcome),
    )
    assert all(token not in surface for token in forbidden for surface in bounded_surfaces)


def test_residual_failure_with_warning_keeps_log_fields_bounded(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    private_line = (
        "[private label](https://example.invalid/path/...?token=synthetic-secret-must-not-escape)"
    )
    markdown = _canonical_markdown(
        watchpoint_body="- 확인할 조건",
        first_viewport_lines=("본문을 참고하세요. 본문을 참고하세요. 본문을 참고하세요.",),
    ).replace("요약 본문", private_line, 1)
    projected, context = _projected_draft(markdown)
    monkeypatch.setattr(
        public_document_module,
        "repair_surface_link_targets",
        lambda text: text,
    )
    _isolate_terminal_surface_gates(monkeypatch)

    repaired = _repair_projected_draft(projected, context)
    assert all(outcome.region_id != "section:1" for outcome in repaired.block_outcomes)
    with pytest.raises(_SegmentTrustBlockedError) as blocked:
        _validate_repaired_draft(repaired, context)

    assert blocked.value.issue_codes == (
        "document.fallback_exhausted",
        "markdown.href_ellipsis",
    )
    assert any(record.code == "template.repeated_phrase" for record in caplog.records)
    forbidden = (
        "first_viewport:",
        "region_id",
        "private label",
        "example.invalid",
        "synthetic-secret",
        "inline_link",
    )
    log_surfaces = tuple(f"{record.getMessage()} {record.__dict__!r}" for record in caplog.records)
    assert all(token not in surface for token in forbidden for surface in log_surfaces)


def test_protected_link_block_waits_for_exhaustive_terminal_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_navigation = (
        "**세그먼트**: "
        "[private label](https://example.invalid/path/...?token=synthetic-secret-must-not-escape)"
    )
    markdown = _canonical_markdown(watchpoint_body="- 확인할 조건").replace(
        "**세그먼트**: [국내](/domestic)",
        private_navigation,
    )
    projected, context = _projected_draft(markdown)
    monkeypatch.setattr(
        public_document_module,
        "_scan_terminal_entity_fact_claims",
        lambda *_args, **_kwargs: (object(),),
    )
    _isolate_terminal_surface_gates(monkeypatch)

    repaired = _repair_projected_draft(projected, context)
    snapshot = _collect_terminal_hard_gates(repaired, context)

    assert snapshot.issue_codes == (
        "entity.fact_contradiction",
        "markdown.href_ellipsis",
    )
    assert snapshot.residual_actionable_link_codes == ()
    assert snapshot.notification_summary is None
    with pytest.raises(_SegmentTrustBlockedError) as blocked:
        _validate_repaired_draft(repaired, context)
    assert blocked.value.issue_codes == (
        "entity.fact_contradiction",
        "markdown.href_ellipsis",
    )


def test_warn_severity_policy_block_survives_terminal_deferral(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    markdown = _canonical_markdown(watchpoint_body="- 확인할 조건").replace(
        "요약 본문",
        "본문을 참고하세요. 본문을 참고하세요. 본문을 참고하세요.",
        1,
    )
    projected, context = _projected_draft(markdown)
    _isolate_terminal_surface_gates(monkeypatch)

    repaired = _repair_projected_draft(projected, context)
    snapshot = _collect_terminal_hard_gates(repaired, context)

    assert snapshot.issue_codes == ("template.repeated_phrase",)
    assert snapshot.residual_actionable_link_codes == ()
    with pytest.raises(_SegmentTrustBlockedError) as blocked:
        _validate_repaired_draft(repaired, context)
    assert blocked.value.issue_codes == ("template.repeated_phrase",)


def test_non_link_action_residual_keeps_exact_code_without_link_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    markdown = _canonical_markdown(watchpoint_body="- 확인할 조건").replace(
        "요약 본문",
        "불강한성",
        1,
    )
    projected, context = _projected_draft(markdown)
    monkeypatch.setattr(
        public_document_module,
        "repair_surface_artifacts",
        lambda text: text,
    )
    _isolate_terminal_surface_gates(monkeypatch)

    repaired = _repair_projected_draft(projected, context)
    snapshot = _collect_terminal_hard_gates(repaired, context)

    assert snapshot.issue_codes == ("bad_token.bulganghanseong",)
    assert snapshot.residual_actionable_link_codes == ()
    with pytest.raises(_SegmentTrustBlockedError) as blocked:
        _validate_repaired_draft(repaired, context)
    assert blocked.value.issue_codes == ("bad_token.bulganghanseong",)


def test_failing_terminal_snapshot_discards_derived_private_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    markdown = _canonical_markdown(watchpoint_body="- 확인할 조건").replace(
        "[국내](/domestic)",
        "[국내](https://example.invalid/path/...)",
    )
    projected, context = _projected_draft(markdown)
    private_summary = PublicNotificationSummary(
        segment=DOMESTIC_EQUITY,
        target_date=_TARGET_DATE,
        conclusion="[관망] private label",
        coverage_status="normal",
        coverage_label="정상",
        watchlist="https://example.invalid/secret?token=synthetic-secret",
    )
    _isolate_terminal_surface_gates(monkeypatch)
    monkeypatch.setattr(
        public_document_module,
        "_derive_public_notification_summary",
        lambda *_args, **_kwargs: private_summary,
    )

    repaired = _repair_projected_draft(projected, context)
    snapshot = _collect_terminal_hard_gates(repaired, context)

    assert snapshot.issue_codes == ("markdown.href_ellipsis",)
    assert snapshot.notification_summary is None
    assert "private label" not in repr(snapshot)
    assert "example.invalid" not in repr(snapshot)
    assert "synthetic-secret" not in repr(snapshot)


def test_terminal_snapshot_enforces_residual_code_bounds() -> None:
    snapshot = _TerminalHardGateSnapshot(
        issue_codes=("markdown.href_ellipsis", "markdown.href_ellipsis"),
        residual_actionable_link_codes=("markdown.href_ellipsis",),
        notification_summary=None,
    )

    assert snapshot.issue_codes == ("markdown.href_ellipsis",)
    assert _terminal_failure_issue_codes(snapshot) == (
        "document.fallback_exhausted",
        "markdown.href_ellipsis",
    )
    protected_snapshot = _TerminalHardGateSnapshot(
        issue_codes=("markdown.href_ellipsis",),
        residual_actionable_link_codes=(),
        notification_summary=None,
    )
    assert _terminal_failure_issue_codes(protected_snapshot) == ("markdown.href_ellipsis",)
    with pytest.raises(ValueError, match="subset of issue_codes"):
        _TerminalHardGateSnapshot(
            issue_codes=(),
            residual_actionable_link_codes=("markdown.href_ellipsis",),
            notification_summary=None,
        )
    with pytest.raises(ValueError, match="registered link codes"):
        _TerminalHardGateSnapshot(
            issue_codes=("entity.fact_contradiction",),
            residual_actionable_link_codes=("entity.fact_contradiction",),
            notification_summary=None,
        )
    with pytest.raises(ValueError, match="must not retain notification summary"):
        _TerminalHardGateSnapshot(
            issue_codes=("entity.fact_contradiction",),
            residual_actionable_link_codes=(),
            notification_summary=PublicNotificationSummary(
                segment=DOMESTIC_EQUITY,
                target_date=_TARGET_DATE,
                conclusion="[관망] 확인된 결론",
                coverage_status="normal",
                coverage_label="정상",
            ),
        )


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
