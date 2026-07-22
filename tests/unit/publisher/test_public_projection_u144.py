"""U144 Step 3.1 terminal public-language projection tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import get_args

import pytest

import investo.publisher.segment_reader_format as segment_reader_format_module
from investo._internal.public_quality_language import (
    FORBIDDEN_PUBLIC_PHRASES,
    PUBLIC_LOW_COVERAGE_INLINE_TEXT,
)
from investo._internal.surface_quality import SurfaceQualityIssue, repair_surface_artifacts
from investo.models import Briefing, SourceOutcome
from investo.models.bundle_context import BundleContext
from investo.models.facts import VerifiedFactBundle
from investo.models.market_anchor import MarketAnchor
from investo.models.segments import DOMESTIC_EQUITY, CoverageReasonCode, SegmentCoverage
from investo.publisher import public_document
from investo.publisher.compliance_language import ComplianceLanguageError
from investo.publisher.public_document import (
    _COVERAGE_REASON_LIMITATIONS,
    PublicDocumentContext,
    PublicDocumentLayout,
    PublicRegionExpectation,
    _assemble_phase_one_reader_draft,
    _default_draft_factory,
    _derive_public_limitation_reasons,
    _new_generated_draft,
    _project_assembled_draft,
    _repair_projected_draft,
    _scan_terminal_anchor_assertions,
    _scan_terminal_compliance,
    _scan_terminal_entity_fact_claims,
    _SegmentTrustBlockedError,
    _transition_draft,
    _validate_repaired_draft,
)
from investo.publisher.reader_format import (
    PublicLabelLeakage,
    find_reader_visible_public_label_leaks,
)
from investo.publisher.reader_format.public_projection import project_public_markdown

_TARGET_DATE = date(2026, 7, 21)

_ASSEMBLY_PRODUCER_OUTPUTS = (
    "generated_body",
    "prebuilt_supplement",
    "anchor_table",
    "anchor_assertion",
    "reader_structure",
    "shared_macro",
    "crypto_indicators",
    "channel_anchors",
    "cause_map",
    "daily_thesis",
    "compliance_repair",
    "watchpoint_matrix",
    "partial_bundle_navigation",
    "canonical_disclaimer",
    "first_viewport_disclaimer",
    "first_viewport_reflow",
    "summary_repair",
    "body_used_count",
)
_FORBIDDEN_PUBLIC_TOKEN_MATRIX = tuple(
    dict.fromkeys(
        (
            *FORBIDDEN_PUBLIC_PHRASES,
            "본문 사용 7",
            "실패 3",
            "0건 2",
            "fallback ratio",
            "Figures Presence",
        )
    )
)


def _expectation() -> PublicRegionExpectation:
    return PublicRegionExpectation(
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


def _markdown(*, newline: str = "\n") -> str:
    lines = (
        f"# {_TARGET_DATE.isoformat()} 국내 증시 시황",
        "",
        "**세그먼트**: [국내](/domestic)",
        "",
        "> 정보 제공용 자동 시황이며 매매 권유가 아닙니다.",
        "",
        "## ① 요약",
        "",
        "데이터 부족입니다.",
        "",
        "```text",
        "```not-a-close",
        "데이터 부족",
        "```",
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
        "| 구분 | 상태 |",
        "|---|---|",
        "| 상방 | 상방 데이터 부족 |",
        "",
        "<details><summary>수집/품질 진단</summary>",
        "데이터 부족",
        "</details>",
        "",
        "## ⑦ 면책조항",
        "",
        "데이터 부족 원문은 면책조항 byte 보존 대상입니다.",
    )
    return newline.join(lines) + newline


def _layout(*, newline: str = "\n") -> PublicDocumentLayout:
    return PublicDocumentLayout.reindex(_markdown(newline=newline), expectation=_expectation())


def _context() -> PublicDocumentContext:
    return PublicDocumentContext(
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
                categories=(),
                missing_categories=(),
            )
        },
        source_outcomes=(SourceOutcome.ok("fixture", "news", 1),),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=_TARGET_DATE),
        entity_observed_at_utc=datetime(2026, 7, 21, tzinfo=UTC),
    )


def test_projection_uses_region_policy_and_projects_reader_visible_tables() -> None:
    layout = _layout()
    diagnostics = next(
        region for region in layout.regions if region.region_id == "diagnostics:quality"
    )
    disclaimer = next(
        region for region in layout.regions if region.region_id == "disclaimer:canonical"
    )
    protected_before = (
        layout.markdown[diagnostics.start : diagnostics.end],
        layout.markdown[disclaimer.start : disclaimer.end],
    )

    projected = project_public_markdown(layout, limitation_reasons=("limited_coverage",))

    assert "데이터 부족입니다" not in projected.markdown
    assert "| 상방 | 상방 데이터 부족 |" not in projected.markdown
    assert "| 상방 | 상방 수집 근거가 제한적입니다 |" in projected.markdown
    assert "```text\n```not-a-close\n데이터 부족\n```" in projected.markdown
    projected_diagnostics = next(
        region for region in projected.regions if region.region_id == "diagnostics:quality"
    )
    assert (
        projected.markdown[projected_diagnostics.start : projected_diagnostics.end]
        == protected_before[0]
    )
    projected_disclaimer = next(
        region for region in projected.regions if region.region_id == "disclaimer:canonical"
    )
    assert (
        projected.markdown[projected_disclaimer.start : projected_disclaimer.end]
        == protected_before[1]
    )


def test_projection_protects_exact_quality_diagnostics_not_arbitrary_details() -> None:
    markdown = _markdown().replace(
        "이슈 본문",
        "<details><summary>기타 메모</summary>\n데이터 부족\n</details>",
    )
    layout = PublicDocumentLayout.reindex(markdown, expectation=_expectation())

    projected = project_public_markdown(layout, limitation_reasons=("limited_coverage",))

    assert "<details><summary>기타 메모</summary>\n데이터 부족\n</details>" not in (
        projected.markdown
    )
    assert "<details><summary>기타 메모</summary>" in projected.markdown
    assert (
        f"<details><summary>기타 메모</summary>\n"
        f"{PUBLIC_LOW_COVERAGE_INLINE_TEXT}\n</details>" in projected.markdown
    )
    assert "<details><summary>수집/품질 진단</summary>\n데이터 부족\n</details>" in (
        projected.markdown
    )


def test_projection_keeps_raw_structured_source_metadata_private() -> None:
    layout = _layout()
    raw_summary = "[데이터부족] operator state"
    briefing = Briefing(
        target_date=_TARGET_DATE,
        market_summary=raw_summary,
        key_issues="이슈",
        sector_flow="수급",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer="데이터 부족 원문은 면책조항 byte 보존 대상입니다.",
        rendered_markdown=layout.markdown,
    )
    generated = _new_generated_draft(
        briefing,
        segment=DOMESTIC_EQUITY,
        layout=layout,
    )
    assembled = _transition_draft(generated, next_phase="assembled")

    projected = _project_assembled_draft(assembled, _context())

    assert projected.source_briefing is briefing
    assert projected.source_briefing.model_dump()["market_summary"] == raw_summary
    assert projected.source_briefing.rendered_markdown == layout.markdown
    assert projected.layout.markdown != layout.markdown
    assert "데이터 부족입니다" not in projected.layout.markdown


def test_reader_visible_leakage_traversal_is_owned_and_read_only() -> None:
    layout = _layout()
    original_markdown = layout.markdown
    original_regions = layout.regions

    leaks = find_reader_visible_public_label_leaks(layout)

    assert leaks == (
        PublicLabelLeakage(
            region_id="section:1",
            block="section_body",
            evidence="데이터 부족",
        ),
        PublicLabelLeakage(
            region_id="watchpoints:section",
            block="watchpoints",
            evidence="데이터 부족",
        ),
    )
    assert layout.markdown == original_markdown
    assert layout.regions is original_regions


def test_reader_visible_leakage_traversal_accepts_projected_owned_regions() -> None:
    layout = _layout()
    projected = project_public_markdown(layout, limitation_reasons=("limited_coverage",))

    assert find_reader_visible_public_label_leaks(projected) == ()


@pytest.mark.parametrize("producer", _ASSEMBLY_PRODUCER_OUTPUTS)
@pytest.mark.parametrize("token", _FORBIDDEN_PUBLIC_TOKEN_MATRIX)
def test_every_assembly_producer_output_is_closed_by_terminal_projection_and_repair(
    producer: str,
    token: str,
) -> None:
    """Pin transform closure for the complete documented phase-one call graph."""

    markdown = _markdown().replace(
        "이슈 본문",
        f"이슈 본문\n{producer}: {token}",
    )
    layout = PublicDocumentLayout.reindex(markdown, expectation=_expectation())

    projected = project_public_markdown(
        layout,
        limitation_reasons=("limited_coverage",),
    )
    repaired = PublicDocumentLayout.reindex(
        repair_surface_artifacts(projected.markdown),
        expectation=projected.expectation,
    )

    assert find_reader_visible_public_label_leaks(repaired) == ()


def test_projection_is_byte_idempotent_and_preserves_crlf() -> None:
    layout = _layout(newline="\r\n")

    projected = project_public_markdown(layout, limitation_reasons=("limited_coverage",))
    repeated = project_public_markdown(projected, limitation_reasons=("limited_coverage",))

    assert repeated is projected
    assert "\r\n" in projected.markdown
    assert "\n" not in projected.markdown.replace("\r\n", "")


@pytest.mark.parametrize(
    ("opening", "not_a_close", "closing"),
    (("```text", "```not-a-close", "```"), ("~~~text", "~~~not-a-close", "~~~")),
)
def test_projection_preserves_fenced_body_lines_with_nonclosing_marker_suffix(
    opening: str,
    not_a_close: str,
    closing: str,
) -> None:
    markdown = _markdown().replace(
        "```text\n```not-a-close\n데이터 부족\n```",
        f"{opening}\n{not_a_close}\n데이터 부족\n{closing}",
    )
    layout = PublicDocumentLayout.reindex(markdown, expectation=_expectation())

    projected = project_public_markdown(layout, limitation_reasons=("limited_coverage",))

    assert f"{opening}\n{not_a_close}\n데이터 부족\n{closing}" in projected.markdown


def test_projection_rejects_duplicate_typed_reasons() -> None:
    with pytest.raises(ValueError, match="unique and ordered"):
        project_public_markdown(
            _layout(),
            limitation_reasons=("limited_coverage", "limited_coverage"),
        )


def test_phase_two_handler_projects_only_after_assembled_transition() -> None:
    layout = _layout()
    briefing = Briefing(
        target_date=_TARGET_DATE,
        market_summary="요약",
        key_issues="이슈",
        sector_flow="수급",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer="데이터 부족 원문은 면책조항 byte 보존 대상입니다.",
        rendered_markdown=layout.markdown,
    )
    generated = _new_generated_draft(
        briefing,
        segment=DOMESTIC_EQUITY,
        layout=layout,
    )
    assembled = _transition_draft(
        generated,
        next_phase="assembled",
        limitation_reasons=("limited_coverage",),
    )

    projected = _project_assembled_draft(assembled, _context())

    assert projected.phase == "projected"
    assert projected.limitation_reasons == ("limited_coverage",)
    assert "데이터 부족입니다" not in projected.layout.markdown
    with pytest.raises(ValueError, match="invalid public-document phase transition"):
        _project_assembled_draft(projected, _context())


def test_coverage_reason_mapping_is_exhaustive_and_classified() -> None:
    expected = {
        "ZERO_ITEMS": ("limited_coverage",),
        "BELOW_THRESHOLD": ("limited_coverage",),
        "MISSING_NEWS": ("limited_coverage",),
        "MISSING_PRICE": ("core_price_missing",),
        "MISSING_MACRO": ("limited_coverage",),
        "MISSING_CALENDAR": ("limited_coverage",),
        "MISSING_EARNINGS": ("limited_coverage",),
        "SOURCE_FAILED": ("limited_coverage",),
        "SOURCE_ZERO": ("limited_coverage",),
        "DOMESTIC_DISCLOSURE_QUIET": (),
        "LOOKAHEAD_DATA_MISSING": ("limited_coverage",),
        "CORE_FAILED": ("core_price_missing",),
        "CORE_ZERO": ("core_price_missing",),
        "CORE_STALE": ("core_price_missing",),
        "ALL_FAILED": ("limited_coverage",),
        "MACRO_ACTUAL_MISSING": ("limited_coverage",),
        "MACRO_ACTUAL_ZERO": ("limited_coverage",),
        "MACRO_ACTUAL_FAILED": ("limited_coverage",),
        "MACRO_ACTUAL_STALE": ("limited_coverage",),
        "MACRO_REQUIRED_OMITTED": ("limited_coverage",),
        "MACRO_FORECAST_UNVERIFIED": ("limited_coverage",),
    }

    assert set(_COVERAGE_REASON_LIMITATIONS) == set(get_args(CoverageReasonCode))
    assert dict(_COVERAGE_REASON_LIMITATIONS) == expected


@pytest.mark.parametrize(
    ("reason_code", "expected"),
    tuple(_COVERAGE_REASON_LIMITATIONS.items()),
)
def test_typed_coverage_reason_derives_only_its_classified_limitation(
    reason_code: CoverageReasonCode,
    expected: tuple[str, ...],
) -> None:
    coverage = SegmentCoverage(
        segment=DOMESTIC_EQUITY,
        status="normal",
        item_count=1,
        source_count=1,
        categories=(),
        missing_categories=(),
        reason_codes=(reason_code,),
    )

    assert (
        _derive_public_limitation_reasons(
            coverage=coverage,
            source_outcomes=(SourceOutcome.ok("fixture", "news", 1),),
        )
        == expected
    )


def test_projection_merges_coverage_reasons_before_producer_reasons() -> None:
    context = _context()
    coverage = SegmentCoverage(
        segment=DOMESTIC_EQUITY,
        status="limited",
        item_count=1,
        source_count=0,
        categories=(),
        missing_categories=(),
        reason_codes=("CORE_STALE",),
    )
    context = PublicDocumentContext(
        target_date=context.target_date,
        expected_segments=context.expected_segments,
        input_absences=context.input_absences,
        anchors_by_segment=context.anchors_by_segment,
        items_by_segment=context.items_by_segment,
        coverage_by_segment={DOMESTIC_EQUITY: coverage},
        source_outcomes=context.source_outcomes,
        bundle_context=context.bundle_context,
        fact_bundle=context.fact_bundle,
        entity_observed_at_utc=context.entity_observed_at_utc,
    )
    generated = _new_generated_draft(
        Briefing(
            target_date=_TARGET_DATE,
            market_summary="요약",
            key_issues="이슈",
            sector_flow="수급",
            indicators_events="지표",
            notable_tickers="종목",
            today_watch="관전",
            disclaimer="면책",
            rendered_markdown=_layout().markdown,
        ),
        segment=DOMESTIC_EQUITY,
        layout=_layout(),
    )
    assembled = _transition_draft(
        generated,
        next_phase="assembled",
        limitation_reasons=("watchpoint_unavailable",),
    )

    projected = _project_assembled_draft(assembled, context)

    assert projected.limitation_reasons == (
        "limited_coverage",
        "core_price_missing",
        "source_count_unavailable",
        "watchpoint_unavailable",
    )


@pytest.mark.parametrize(
    ("source_outcomes", "expected"),
    (
        ((), ("source_count_unavailable",)),
        ((SourceOutcome.ok("fixture", "news", 1),), ()),
    ),
)
def test_projection_derives_source_count_availability_from_e1_outcomes(
    source_outcomes: tuple[SourceOutcome, ...],
    expected: tuple[str, ...],
) -> None:
    context = replace(_context(), source_outcomes=source_outcomes)
    layout = _layout()
    generated = _new_generated_draft(
        Briefing(
            target_date=_TARGET_DATE,
            market_summary="요약",
            key_issues="이슈",
            sector_flow="수급",
            indicators_events="지표",
            notable_tickers="종목",
            today_watch="관전",
            disclaimer="면책",
            rendered_markdown=layout.markdown,
        ),
        segment=DOMESTIC_EQUITY,
        layout=layout,
    )
    assembled = _transition_draft(generated, next_phase="assembled")

    projected = _project_assembled_draft(assembled, context)

    assert projected.limitation_reasons == expected


def test_terminal_entity_guard_uses_e1_observation_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _context()
    layout = _layout()
    generated = _new_generated_draft(
        Briefing(
            target_date=_TARGET_DATE,
            market_summary="요약",
            key_issues="이슈",
            sector_flow="수급",
            indicators_events="지표",
            notable_tickers="종목",
            today_watch="관전",
            disclaimer="면책",
            rendered_markdown=layout.markdown,
        ),
        segment=DOMESTIC_EQUITY,
        layout=layout,
    )
    observed: list[tuple[object, ...]] = []

    def fake_scan(
        markdown: str,
        bundle: VerifiedFactBundle,
        target_date: object,
        now_utc: datetime,
        *,
        segment: str,
    ) -> tuple[()]:
        observed.append((markdown, bundle, target_date, now_utc, segment))
        return ()

    monkeypatch.setattr(public_document, "scan_entity_fact_claims", fake_scan)

    assert _scan_terminal_entity_fact_claims(generated, context) == ()
    assert observed == [
        (
            layout.markdown,
            context.fact_bundle,
            context.target_date,
            context.entity_observed_at_utc,
            DOMESTIC_EQUITY,
        )
    ]


def test_terminal_anchor_guard_reads_final_layout_and_e1_symbols_only() -> None:
    layout = PublicDocumentLayout.reindex(
        _layout().markdown.replace("수급 본문", "코스피는 1.8% 급락 마감했다."),
        expectation=_expectation(),
    )
    generated = _new_generated_draft(
        Briefing(
            target_date=_TARGET_DATE,
            market_summary="요약",
            key_issues="이슈",
            sector_flow="수급",
            indicators_events="지표",
            notable_tickers="종목",
            today_watch="관전",
            disclaimer="면책",
            rendered_markdown=layout.markdown,
        ),
        segment=DOMESTIC_EQUITY,
        layout=layout,
    )
    original_markdown = generated.layout.markdown

    findings = _scan_terminal_anchor_assertions(generated, _context())

    assert len(findings) == 1
    assert findings[0].symbol == "^KOSPI"
    assert generated.layout.markdown == original_markdown

    anchored_context = replace(
        _context(),
        anchors_by_segment={
            DOMESTIC_EQUITY: (
                MarketAnchor(
                    ticker="^KOSPI",
                    close=Decimal("2500"),
                    is_ath=False,
                ),
            )
        },
    )
    assert _scan_terminal_anchor_assertions(generated, anchored_context) == ()


def test_terminal_compliance_guard_reads_final_layout_without_repair() -> None:
    layout = PublicDocumentLayout.reindex(
        _layout().markdown.replace("수급 본문", "오늘은 매수 검토가 필요합니다."),
        expectation=_expectation(),
    )
    generated = _new_generated_draft(
        Briefing(
            target_date=_TARGET_DATE,
            market_summary="요약",
            key_issues="이슈",
            sector_flow="수급",
            indicators_events="지표",
            notable_tickers="종목",
            today_watch="관전",
            disclaimer="면책",
            rendered_markdown=layout.markdown,
        ),
        segment=DOMESTIC_EQUITY,
        layout=layout,
    )
    original_markdown = generated.layout.markdown

    with pytest.raises(ComplianceLanguageError):
        _scan_terminal_compliance(generated, _context())

    assert generated.layout.markdown == original_markdown
    assert "매수 검토" in generated.layout.markdown


def test_terminal_validation_blocks_reader_visible_table_label_leak() -> None:
    layout = PublicDocumentLayout.reindex(
        _layout()
        .markdown.replace("데이터 부족입니다.", "관찰 범위가 제한됩니다.")
        .replace(
            "수급 본문",
            "| 관찰 항목 | 상태 |\n|---|---|\n| 정책 변수 | 데이터 부족 |",
        ),
        expectation=_expectation(),
    )
    briefing = Briefing(
        target_date=_TARGET_DATE,
        market_summary="요약",
        key_issues="이슈",
        sector_flow="수급",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer="면책",
        rendered_markdown=layout.markdown,
    )
    generated = _new_generated_draft(briefing, segment=DOMESTIC_EQUITY, layout=layout)
    assembled = _transition_draft(generated, next_phase="assembled")
    projected = _transition_draft(assembled, next_phase="projected")
    repaired = _transition_draft(projected, next_phase="repaired")
    original_markdown = repaired.layout.markdown

    with pytest.raises(_SegmentTrustBlockedError) as blocked:
        _validate_repaired_draft(repaired, _context())

    assert blocked.value.issue_codes == ("public_language.residual",)
    assert repaired.layout.markdown == original_markdown


def test_terminal_validation_runs_full_document_surface_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = PublicDocumentLayout.reindex(
        _layout().markdown.replace("데이터 부족입니다.", "관찰 범위가 제한됩니다."),
        expectation=_expectation(),
    )
    briefing = Briefing(
        target_date=_TARGET_DATE,
        market_summary="요약",
        key_issues="이슈",
        sector_flow="수급",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer="면책",
        rendered_markdown=layout.markdown,
    )
    generated = _new_generated_draft(briefing, segment=DOMESTIC_EQUITY, layout=layout)
    assembled = _transition_draft(generated, next_phase="assembled")
    projected = _transition_draft(assembled, next_phase="projected")
    repaired = _transition_draft(projected, next_phase="repaired")
    full_document_calls = 0

    def fake_surface_scan(text: str) -> tuple[SurfaceQualityIssue, ...]:
        nonlocal full_document_calls
        if text != repaired.layout.markdown:
            return ()
        full_document_calls += 1
        return (
            SurfaceQualityIssue(
                code="trace.fragment",
                severity="block",
                evidence="cross-region-context",
                region="body",
            ),
        )

    monkeypatch.setattr(public_document, "_scan_terminal_anchor_assertions", lambda *_: ())
    monkeypatch.setattr(public_document, "_scan_terminal_entity_fact_claims", lambda *_: ())
    monkeypatch.setattr(public_document, "_scan_terminal_compliance", lambda *_: None)
    monkeypatch.setattr(public_document, "find_reader_visible_public_label_leaks", lambda *_: ())
    monkeypatch.setattr(public_document, "validate_first_viewport_summary", lambda *_: None)
    monkeypatch.setattr(public_document, "verify_disclaimer", lambda *_: True)
    monkeypatch.setattr(public_document, "verify_short_disclaimer_first_viewport", lambda *_: True)
    monkeypatch.setattr(public_document, "find_surface_quality_issues", fake_surface_scan)

    with pytest.raises(_SegmentTrustBlockedError) as blocked:
        _validate_repaired_draft(repaired, _context())

    assert blocked.value.issue_codes == ("trace.fragment",)
    assert full_document_calls == 1


def test_reader_assembly_carries_typed_watchpoint_reason_into_projection() -> None:
    layout = _layout()
    briefing = Briefing(
        target_date=_TARGET_DATE,
        market_summary="요약",
        key_issues="이슈",
        sector_flow="수급",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer="데이터 부족 원문은 면책조항 byte 보존 대상입니다.",
        rendered_markdown=layout.markdown,
    )
    generated = _new_generated_draft(
        briefing,
        segment=DOMESTIC_EQUITY,
        layout=layout,
    )

    assembled = _assemble_phase_one_reader_draft(generated, _context())
    projected = _project_assembled_draft(assembled, _context())

    assert assembled.phase == "assembled"
    assert assembled.limitation_reasons == ("watchpoint_unavailable",)
    assert projected.phase == "projected"
    assert projected.limitation_reasons == ("watchpoint_unavailable",)


def test_active_pass_reuses_one_producer_plan_for_expectation_and_assembly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = _layout()
    briefing = Briefing(
        target_date=_TARGET_DATE,
        market_summary="요약",
        key_issues="이슈",
        sector_flow="수급",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer="데이터 부족 원문은 면책조항 byte 보존 대상입니다.",
        rendered_markdown=layout.markdown,
    )
    calls = 0
    real_builder = public_document.build_segment_reader_producer_plan

    def observe_builder(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        return real_builder(*args, **kwargs)

    def forbid_independent_rebuild(*args: object, **kwargs: object):
        del args, kwargs
        raise AssertionError("assembly must reuse the draft's producer plan")

    monkeypatch.setattr(public_document, "build_segment_reader_producer_plan", observe_builder)
    monkeypatch.setattr(
        segment_reader_format_module,
        "build_segment_reader_producer_plan",
        forbid_independent_rebuild,
    )

    generated = _default_draft_factory(briefing, DOMESTIC_EQUITY, _context())
    assembled = _assemble_phase_one_reader_draft(generated, _context())

    assert calls == 1
    assert generated._producer_plan is assembled._producer_plan
    assert generated._producer_plan is not None
    reader = generated._producer_plan.reader
    expectation = generated.layout.expectation
    assert expectation.anchor_table_required is bool(reader.anchor_table)
    assert expectation.shared_macro_required is bool(reader.shared_macro_block)
    assert expectation.crypto_indicators_required is bool(reader.crypto_indicator_block)
    assert expectation.channel_anchors_required is bool(reader.channel_anchor_block)
    assert expectation.daily_thesis_required is bool(reader.daily_thesis_line)


def test_full_finalizer_builds_each_active_producer_plan_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = _layout()
    briefing = Briefing(
        target_date=_TARGET_DATE,
        market_summary="요약",
        key_issues="이슈",
        sector_flow="수급",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer="데이터 부족 원문은 면책조항 byte 보존 대상입니다.",
        rendered_markdown=layout.markdown,
    )
    context = replace(
        _context(),
        bundle_context=BundleContext(
            bundle_id="u144-producer-plan",
            target_kst_date=_TARGET_DATE,
        ),
    )
    builder_calls: list[str] = []
    thesis_calls: list[str] = []
    real_builder = public_document.build_segment_reader_producer_plan
    real_thesis_renderer = segment_reader_format_module.render_daily_thesis_line

    def observe_builder(*args: object, **kwargs: object):
        builder_calls.append(str(args[0]))
        return real_builder(*args, **kwargs)

    def observe_thesis(*args: object, **kwargs: object) -> str:
        thesis_calls.append(str(kwargs["segment"]))
        return real_thesis_renderer(*args, **kwargs)

    def validate_for_structure_test(
        draft: public_document.PublicDocumentDraft,
        _context_value: PublicDocumentContext,
    ) -> public_document.PublicDocumentDraft:
        return _transition_draft(
            draft,
            next_phase="validated",
            notification_summary=public_document.PublicNotificationSummary(
                segment=draft.segment,
                target_date=draft.target_date,
                conclusion="검증된 결론",
                coverage_status="normal",
                coverage_label="정상",
            ),
        )

    monkeypatch.setattr(public_document, "build_segment_reader_producer_plan", observe_builder)
    monkeypatch.setattr(
        segment_reader_format_module,
        "render_daily_thesis_line",
        observe_thesis,
    )
    monkeypatch.setattr(
        public_document,
        "_validate_repaired_draft",
        validate_for_structure_test,
    )

    bundle = public_document.finalize_public_bundle(
        {DOMESTIC_EQUITY: briefing},
        context=context,
    )

    assert tuple(document.segment for document in bundle.documents) == (DOMESTIC_EQUITY,)
    assert builder_calls == [DOMESTIC_EQUITY]
    assert thesis_calls == [DOMESTIC_EQUITY]


def test_full_finalizer_bounds_producer_plan_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = _layout()
    briefing = Briefing(
        target_date=_TARGET_DATE,
        market_summary="요약",
        key_issues="이슈",
        sector_flow="수급",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer="데이터 부족 원문은 면책조항 byte 보존 대상입니다.",
        rendered_markdown=layout.markdown,
    )

    def fail_builder(*args: object, **kwargs: object):
        del args, kwargs
        raise ValueError("must-not-escape")

    monkeypatch.setattr(public_document, "_build_public_document_producer_plan", fail_builder)

    with pytest.raises(public_document.PublicDocumentFinalizationError) as raised:
        public_document.finalize_public_bundle(
            {DOMESTIC_EQUITY: briefing},
            context=_context(),
        )

    assert raised.value.segment == DOMESTIC_EQUITY
    assert raised.value.phase == "generated"
    assert raised.value.issue_codes == ("invariant.producer_plan",)
    assert "must-not-escape" not in str(raised.value)


def test_full_finalizer_bounds_invalid_cached_plan_map(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = _layout()
    briefing = Briefing(
        target_date=_TARGET_DATE,
        market_summary="요약",
        key_issues="이슈",
        sector_flow="수급",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer="데이터 부족 원문은 면책조항 byte 보존 대상입니다.",
        rendered_markdown=layout.markdown,
    )
    context = _context()
    plan = public_document._build_public_document_producer_plan(
        briefing,
        segment=DOMESTIC_EQUITY,
        context=context,
    )
    invalid_plan = replace(
        plan,
        reader=replace(plan.reader, segment="us-equity"),
    )
    monkeypatch.setattr(
        public_document,
        "_build_public_document_producer_plan",
        lambda *_args, **_kwargs: invalid_plan,
    )

    with pytest.raises(public_document.PublicDocumentFinalizationError) as raised:
        public_document.finalize_public_bundle(
            {DOMESTIC_EQUITY: briefing},
            context=context,
        )

    assert raised.value.segment is None
    assert raised.value.phase == "fixed_point"
    assert raised.value.issue_codes == ("invariant.producer_plan_context",)


def test_production_assembly_defers_surface_repair_until_outcome_owner() -> None:
    layout = PublicDocumentLayout.reindex(
        _layout().markdown.replace("이슈 본문", "불강한성 확대를 점검합니다."),
        expectation=_expectation(),
    )
    briefing = Briefing(
        target_date=_TARGET_DATE,
        market_summary="요약",
        key_issues="이슈",
        sector_flow="수급",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer="데이터 부족 원문은 면책조항 byte 보존 대상입니다.",
        rendered_markdown=layout.markdown,
    )
    generated = _default_draft_factory(briefing, DOMESTIC_EQUITY, _context())

    assembled = _assemble_phase_one_reader_draft(generated, _context())
    projected = _project_assembled_draft(assembled, _context())
    repaired = _repair_projected_draft(projected, _context())

    assert "불강한성" in assembled.layout.markdown
    assert "불강한성" not in repaired.layout.markdown
    assert any(
        outcome.issue_codes == ("bad_token.bulganghanseong",) and outcome.disposition == "repaired"
        for outcome in repaired.block_outcomes
    )
