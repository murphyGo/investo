"""u149 domestic numeric-only containment and minimal fallback contracts."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath

import pytest

from investo._internal.disclaimer import DISCLAIMER
from investo.models import (
    Briefing,
    NumericContainmentOutcome,
    SegmentFinalizationOutcome,
    SourceOutcome,
)
from investo.models.facts import VerifiedFactBundle
from investo.models.public_artifact import StagedArtifact
from investo.models.segments import DOMESTIC_EQUITY, US_EQUITY, MarketSegment, SegmentCoverage
from investo.publisher import public_document as public_document_module
from investo.publisher.anchor_assertion_gate import scan_anchor_assertions
from investo.publisher.compliance_language import ComplianceHit, ComplianceLanguageError
from investo.publisher.numeric_containment import (
    apply_numeric_containment_plan,
    plan_numeric_containment,
)
from investo.publisher.public_document import (
    _REGION_SAFE_FALLBACK_TEXT,
    PublicDocumentContext,
    PublicDocumentFinalizationError,
    PublicDocumentLayout,
    PublicDocumentSupplement,
    PublicRegionExpectation,
    finalize_public_bundle,
)

_TARGET = date(2026, 8, 4)
_SHORT = "> 정보 제공용 자동 시황이며 매매 권유가 아닙니다."


def _markdown(*, diagnostic: str = "품질 진단 정상") -> str:
    return (
        f"# {_TARGET.isoformat()} 국내 증시 시황\n\n"
        "**세그먼트**: [국내 증시](2026-08-04.md)\n\n"
        f"{_SHORT}\n\n"
        "> **오늘의 결론**: 확인 가능한 근거만 반영합니다.\n"
        "> **핵심 동인**: 데이터 수집 상태를 우선 확인합니다.\n"
        "> **주의할 점**: 확인 전 방향을 단정하지 않습니다.\n\n"
        "## ① 요약\n요약 본문\n\n"
        "## ② 전일 핵심 이슈\n"
        "| 구분 | 값 |\n|---|---|\n| 코스피 | 150.00 |\n| 수급 | 확인 중 |\n\n"
        "## ③ 섹터/수급 동향\n수급 본문\n\n"
        "## ④ 지표·이벤트\n이벤트 본문\n\n"
        "## ⑤ 주요 종목\n종목 본문\n\n"
        "## ⑥ 오늘의 관전 포인트\n- 데이터 회복 여부를 확인합니다.\n\n"
        "<details><summary>수집/품질 진단</summary>\n"
        f"{diagnostic}\n"
        "</details>\n\n"
        f"{DISCLAIMER}\n"
    )


def _expectation() -> PublicRegionExpectation:
    return PublicRegionExpectation(
        target_date=_TARGET,
        segment=DOMESTIC_EQUITY,
        segmented_mode=True,
        supplement_ids=(),
        shared_macro_required=False,
        crypto_indicators_required=False,
        channel_anchors_required=False,
        daily_thesis_required=False,
        anchor_table_required=False,
    )


def _briefing(markdown: str) -> Briefing:
    return Briefing(
        target_date=_TARGET,
        market_summary="확인 가능한 근거만 반영합니다.",
        key_issues="핵심 이슈",
        sector_flow="수급 본문",
        indicators_events="이벤트 본문",
        notable_tickers="종목 본문",
        today_watch="데이터 회복 여부를 확인합니다.",
        disclaimer=DISCLAIMER,
        rendered_markdown=markdown,
    )


def _context(
    *segments: MarketSegment,
) -> PublicDocumentContext:
    expected_segments = segments or (DOMESTIC_EQUITY,)
    coverage_by_segment = {
        segment: SegmentCoverage(
            segment=segment,
            status="limited",
            item_count=0,
            source_count=0,
            categories=(),
            missing_categories=("price", "news"),
        )
        for segment in expected_segments
    }
    return PublicDocumentContext(
        target_date=_TARGET,
        expected_segments=expected_segments,
        input_absences={},
        anchors_by_segment={},
        items_by_segment={},
        coverage_by_segment=coverage_by_segment,
        source_outcomes=(SourceOutcome.zero("yonhap-index-close", "price"),),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=_TARGET),
        entity_observed_at_utc=datetime(2026, 8, 4, 12, tzinfo=UTC),
    )


def test_table_row_is_excluded_from_one_owned_section_region() -> None:
    markdown = _markdown()
    layout = PublicDocumentLayout.reindex(markdown, expectation=_expectation())
    findings = scan_anchor_assertions(
        markdown,
        segment=DOMESTIC_EQUITY,
        available_symbols=(),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.line_kind == "table_row"
    assert markdown[finding.start : finding.end] == "| 코스피 | 150.00 |"

    plan = plan_numeric_containment(
        layout,
        findings,
        target_date=_TARGET,
        fallback_text_by_block=_REGION_SAFE_FALLBACK_TEXT,
    )
    result = apply_numeric_containment_plan(layout, plan)

    assert "| 코스피 | 150.00 |" not in result.layout.markdown
    assert "| 수급 | 확인 중 |" in result.layout.markdown
    assert len(result.outcomes) == 1
    assert result.outcomes[0].action == "excluded"
    assert result.outcomes[0].claim_digest == sha256(finding.sentence.encode()).hexdigest()


def test_stale_finding_offsets_request_minimal_instead_of_editing_wrong_bytes() -> None:
    markdown = _markdown()
    layout = PublicDocumentLayout.reindex(markdown, expectation=_expectation())
    (finding,) = scan_anchor_assertions(
        markdown,
        segment=DOMESTIC_EQUITY,
        available_symbols=(),
    )
    stale = replace(finding, start=finding.start + 1, end=finding.end + 1)

    plan = plan_numeric_containment(
        layout,
        (stale,),
        target_date=_TARGET,
        fallback_text_by_block=_REGION_SAFE_FALLBACK_TEXT,
    )

    assert plan.requires_minimal is True
    assert plan.region_plans == ()


def test_multi_region_plan_uses_one_transaction_before_optional_cause_omission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    markdown = _markdown().replace(
        "## ① 요약",
        "> **크로스마켓 연결 고리**: 코스피는 150.00을 나타냈습니다.\n"
        "코스피는 151.00을 나타냈습니다.\n\n"
        "## ① 요약",
    )
    layout = PublicDocumentLayout.reindex(markdown, expectation=_expectation())
    findings = scan_anchor_assertions(
        markdown,
        segment=DOMESTIC_EQUITY,
        available_symbols=(),
    )

    plan = plan_numeric_containment(
        layout,
        findings,
        target_date=_TARGET,
        fallback_text_by_block=_REGION_SAFE_FALLBACK_TEXT,
    )
    real_reindex = PublicDocumentLayout.reindex
    reindex_calls: list[str] = []

    def observe_reindex(
        cls: type[PublicDocumentLayout],
        candidate: str,
        *,
        expectation: PublicRegionExpectation,
    ) -> PublicDocumentLayout:
        assert cls is PublicDocumentLayout
        reindex_calls.append(candidate)
        return real_reindex(candidate, expectation=expectation)

    monkeypatch.setattr(PublicDocumentLayout, "reindex", classmethod(observe_reindex))
    result = apply_numeric_containment_plan(layout, plan)

    assert plan.requires_minimal is False
    assert len(reindex_calls) == 1
    assert "크로스마켓 연결 고리" not in result.layout.markdown
    assert "150.00" not in result.layout.markdown
    assert "151.00" not in result.layout.markdown
    assert {"omitted", "rewritten"} <= {outcome.action for outcome in result.outcomes}


@pytest.mark.parametrize("newline", ["\n", "\r", "\r\n"])
def test_h3_finding_excludes_only_its_subtree(newline: str) -> None:
    markdown = (
        _markdown()
        .replace("| 코스피 | 150.00 |", "| 지수 | 확인 중 |")
        .replace(
            "## ② 전일 핵심 이슈\n",
            "## ② 전일 핵심 이슈\n### 코스피 150.00\n삭제할 설명\n### 다음 항목\n보존할 설명\n",
        )
        .replace("\n", newline)
    )
    layout = PublicDocumentLayout.reindex(markdown, expectation=_expectation())
    findings = scan_anchor_assertions(
        markdown,
        segment=DOMESTIC_EQUITY,
        available_symbols=(),
    )

    plan = plan_numeric_containment(
        layout,
        findings,
        target_date=_TARGET,
        fallback_text_by_block=_REGION_SAFE_FALLBACK_TEXT,
    )
    result = apply_numeric_containment_plan(layout, plan)

    assert {finding.line_kind for finding in findings} == {"h3_subtree"}
    assert "### 코스피 150.00" not in result.layout.markdown
    assert "삭제할 설명" not in result.layout.markdown
    assert f"### 다음 항목{newline}보존할 설명" in result.layout.markdown


def test_overlapping_findings_request_minimal() -> None:
    markdown = _markdown()
    layout = PublicDocumentLayout.reindex(markdown, expectation=_expectation())
    (finding,) = scan_anchor_assertions(
        markdown,
        segment=DOMESTIC_EQUITY,
        available_symbols=(),
    )

    plan = plan_numeric_containment(
        layout,
        (finding, finding),
        target_date=_TARGET,
        fallback_text_by_block=_REGION_SAFE_FALLBACK_TEXT,
    )

    assert plan.requires_minimal is True
    assert plan.region_plans == ()


def test_protected_diagnostic_claim_uses_one_minimal_fallback_and_seals_degraded() -> None:
    source = _briefing(_markdown(diagnostic="코스피는 150.00을 나타냈습니다."))

    bundle = finalize_public_bundle(
        {DOMESTIC_EQUITY: source},
        context=_context(),
    )

    assert len(bundle.documents) == 1
    document = bundle.documents[0]
    assert "150.00" not in document.briefing.rendered_markdown
    for heading in (
        "## ① 요약",
        "## ② 전일 핵심 이슈",
        "## ③ 섹터/수급 동향",
        "## ④ 지표·이벤트",
        "## ⑤ 주요 종목",
        "## ⑥ 오늘의 관전 포인트",
    ):
        assert document.briefing.rendered_markdown.count(heading) == 1
    assert "> **오늘의 결론**:" in document.briefing.rendered_markdown
    assert "> **핵심 동인**:" in document.briefing.rendered_markdown
    assert "> **주의할 점**:" in document.briefing.rendered_markdown
    assert _SHORT in document.briefing.rendered_markdown
    assert DISCLAIMER in document.briefing.rendered_markdown
    assert document.numeric_containment_outcomes
    assert {outcome.action for outcome in document.numeric_containment_outcomes} == {
        "minimal_fallback"
    }
    outcome = bundle.segment_outcomes[0]
    assert outcome.state == "finalized_degraded"
    assert outcome.numeric_containment_outcomes == document.numeric_containment_outcomes
    assert outcome.issue_codes == ("numeric.anchor_assertion",)


def test_default_finalizer_excludes_local_table_row_and_seals_degraded() -> None:
    source = _briefing(_markdown())

    bundle = finalize_public_bundle(
        {DOMESTIC_EQUITY: source},
        context=_context(),
    )

    document = bundle.documents[0]
    assert "| 코스피 | 150.00 |" not in document.briefing.rendered_markdown
    assert "| 수급 | 확인 중 |" in document.briefing.rendered_markdown
    assert {outcome.action for outcome in document.numeric_containment_outcomes} == {"excluded"}
    assert bundle.segment_outcomes[0].state == "finalized_degraded"


def test_numeric_visual_omission_seals_degraded_without_artifact_promotion(
    tmp_path: Path,
) -> None:
    artifact = StagedArtifact(
        artifact_id="visual.hero",
        segment=DOMESTIC_EQUITY,
        kind="visual",
        relative_public_path=PurePosixPath("assets/hero.svg"),
        staged_path=tmp_path / "hero.svg",
        sha256=sha256(b"hero").hexdigest(),
    )
    supplement = PublicDocumentSupplement(
        supplement_id="hero",
        kind="visual",
        markdown="![코스피 150.00](assets/hero.svg)",
        stable_order=1,
        artifact_ids=(artifact.artifact_id,),
    )
    marker = (
        "<!-- investo:block visual:hero -->\n"
        f"{supplement.markdown}\n"
        "<!-- /investo:block visual:hero -->\n"
    )
    source = _briefing(
        _markdown()
        .replace("| 코스피 | 150.00 |", "| 지수 | 확인 중 |")
        .replace("## ② 전일 핵심 이슈\n", f"## ② 전일 핵심 이슈\n{marker}")
    )
    context = replace(
        _context(),
        supplements_by_segment={DOMESTIC_EQUITY: (supplement,)},
        staged_artifacts_by_segment={DOMESTIC_EQUITY: (artifact,)},
    )

    bundle = finalize_public_bundle({DOMESTIC_EQUITY: source}, context=context)

    document = bundle.documents[0]
    assert "코스피 150.00" not in document.briefing.rendered_markdown
    assert document.staged_artifact_ids == ()
    assert bundle.promotion_manifest == ()
    assert document.numeric_containment_outcomes[0].action == "omitted"
    assert any(
        outcome.region_id == "visual:hero" and outcome.disposition == "omitted"
        for outcome in document.block_outcomes
    )


def test_local_containment_is_byte_and_witness_idempotent() -> None:
    source = _briefing(_markdown())

    first = finalize_public_bundle({DOMESTIC_EQUITY: source}, context=_context())
    second = finalize_public_bundle({DOMESTIC_EQUITY: source}, context=_context())

    assert first == second
    assert first.documents[0].markdown_sha256 == second.documents[0].markdown_sha256


def test_segment_outcome_rejects_invalid_state_witness_combinations() -> None:
    witness = NumericContainmentOutcome(
        target_date=_TARGET,
        segment=DOMESTIC_EQUITY,
        symbol="^KOSPI",
        region_id="section:2",
        line_kind="table_row",
        action="excluded",
        issue_codes=("numeric.anchor_assertion",),
        claim_digest=sha256(b"claim").hexdigest(),
    )

    with pytest.raises(ValueError, match="finalized state"):
        SegmentFinalizationOutcome(
            segment=DOMESTIC_EQUITY,
            state="finalized",
            numeric_containment_outcomes=(witness,),
        )
    with pytest.raises(ValueError, match="requires numeric containment"):
        SegmentFinalizationOutcome(
            segment=DOMESTIC_EQUITY,
            state="finalized_degraded",
            issue_codes=("numeric.anchor_assertion",),
        )


def test_numeric_and_compliance_codes_block_without_minimal_masking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_builder = public_document_module.build_data_limited_briefing
    builder_calls: list[tuple[date, MarketSegment]] = []

    def observe_builder(target_date: date, segment: MarketSegment) -> Briefing:
        builder_calls.append((target_date, segment))
        return original_builder(target_date, segment)

    def reject_compliance(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise ComplianceLanguageError(
            segment=DOMESTIC_EQUITY,
            hits=(ComplianceHit("매수 검토", "P0", 1, "action"),),
        )

    monkeypatch.setattr(
        public_document_module,
        "build_data_limited_briefing",
        observe_builder,
    )
    monkeypatch.setattr(public_document_module, "_scan_terminal_compliance", reject_compliance)

    with pytest.raises(PublicDocumentFinalizationError) as exc:
        finalize_public_bundle(
            {DOMESTIC_EQUITY: _briefing(_markdown())},
            context=_context(),
        )

    assert builder_calls == []
    assert "compliance.language" in exc.value.issue_codes
    assert "numeric.anchor_assertion" in exc.value.issue_codes


def test_numeric_and_entity_codes_block_without_minimal_masking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_builder = public_document_module.build_data_limited_briefing
    builder_calls: list[tuple[date, MarketSegment]] = []

    def observe_builder(target_date: date, segment: MarketSegment) -> Briefing:
        builder_calls.append((target_date, segment))
        return original_builder(target_date, segment)

    monkeypatch.setattr(
        public_document_module,
        "build_data_limited_briefing",
        observe_builder,
    )
    monkeypatch.setattr(
        public_document_module,
        "_scan_terminal_entity_fact_claims",
        lambda *_: (object(),),
    )

    with pytest.raises(PublicDocumentFinalizationError) as exc:
        finalize_public_bundle(
            {DOMESTIC_EQUITY: _briefing(_markdown())},
            context=_context(),
        )

    assert builder_calls == []
    assert "entity.fact_contradiction" in exc.value.issue_codes
    assert "numeric.anchor_assertion" in exc.value.issue_codes


def test_failed_minimal_source_is_not_rebuilt_or_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _briefing(_markdown(diagnostic="코스피는 150.00을 나타냈습니다."))
    builder_calls: list[tuple[date, MarketSegment]] = []

    def still_unsafe(target_date: date, segment: MarketSegment) -> Briefing:
        builder_calls.append((target_date, segment))
        return source

    monkeypatch.setattr(
        public_document_module,
        "build_data_limited_briefing",
        still_unsafe,
    )

    with pytest.raises(PublicDocumentFinalizationError) as exc:
        finalize_public_bundle(
            {DOMESTIC_EQUITY: source},
            context=_context(),
        )

    assert builder_calls == [(_TARGET, DOMESTIC_EQUITY)]
    assert "numeric.anchor_assertion" in exc.value.issue_codes
    assert "numeric.fallback_exhausted" in exc.value.issue_codes


def test_minimal_builder_runs_once_across_survivor_rerun_and_us_stays_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_builder = public_document_module.build_data_limited_briefing
    builder_calls: list[tuple[date, MarketSegment]] = []

    def observe_builder(target_date: date, segment: MarketSegment) -> Briefing:
        builder_calls.append((target_date, segment))
        return original_builder(target_date, segment)

    monkeypatch.setattr(
        public_document_module,
        "build_data_limited_briefing",
        observe_builder,
    )
    domestic = _briefing(_markdown(diagnostic="코스피는 150.00을 나타냈습니다."))
    us = _briefing(
        _markdown()
        .replace("국내 증시", "미국 증시")
        .replace("| 코스피 | 150.00 |", "| 나스닥 종합 | 15,000.00 | +0.5% | 상승 |")
    )

    bundle = finalize_public_bundle(
        {DOMESTIC_EQUITY: domestic, US_EQUITY: us},
        context=_context(DOMESTIC_EQUITY, US_EQUITY),
    )

    assert builder_calls == [(_TARGET, DOMESTIC_EQUITY)]
    assert tuple(outcome.state for outcome in bundle.segment_outcomes) == (
        "finalized_degraded",
        "trust_blocked",
    )
    assert tuple(document.segment for document in bundle.documents) == (DOMESTIC_EQUITY,)
