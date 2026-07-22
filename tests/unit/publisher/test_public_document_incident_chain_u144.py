"""U144 Step 3.7 whole-chain regression for run 29707052598."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from investo._internal.disclaimer import DISCLAIMER_CRYPTO
from investo._internal.surface_quality import find_surface_quality_issues
from investo.models import Briefing, SourceOutcome
from investo.models.facts import VerifiedFactBundle
from investo.models.public_notification import PublicNotificationSummary
from investo.models.segments import CRYPTO, MarketSegment, SegmentCoverage
from investo.publisher import FinalizedPublicDocument
from investo.publisher.public_document import (
    PublicDocumentContext,
    PublicDocumentDraft,
    PublicDocumentLayout,
    PublicDocumentSupplement,
    PublicRegionExpectation,
    _assemble_phase_one_reader_draft,
    _FinalizationPhaseHandlers,
    _finalize_segment_skeleton,
    _new_generated_draft,
    _project_assembled_draft,
    _render_supplement_block,
    _scan_terminal_entity_fact_claims,
    _transition_draft,
)
from investo.publisher.reader_format import find_reader_visible_public_label_leaks

_FIXTURE_PATH = (
    Path(__file__).parents[2]
    / "fixtures"
    / "u144"
    / "run-29707052598-watchpoint-reintroduction.json"
)


def _load_fixture() -> dict[str, Any]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _canonical_incident_markdown(target_date: date, watchpoint: str) -> str:
    short_disclaimer = (
        "> 정보 제공용 자동 시황이며 가상자산 매매 권유가 아닙니다. "
        "가상자산은 가격 변동성이 매우 큽니다."
    )
    lines = (
        f"# {target_date.isoformat()} 크립토 시황",
        "",
        "**세그먼트**: [크립토](/crypto)",
        "",
        short_disclaimer,
        "",
        "<details><summary>수집/품질 진단</summary>",
        "정상 수집",
        "</details>",
        "",
        "## ① 요약",
        "",
        "공개 근거를 요약합니다.",
        "",
        "## ② 전일 핵심 이슈",
        "",
        "핵심 이슈를 확인합니다.",
        "",
        "## ③ 섹터/수급 동향",
        "",
        "수급 흐름을 확인합니다.",
        "",
        "## ④ 지표·이벤트",
        "",
        "주요 지표를 확인합니다.",
        "",
        "## ⑤ 주요 종목",
        "",
        "주요 자산을 확인합니다.",
        "",
        "## ⑥ 오늘의 관전 포인트",
        "",
        f"- {watchpoint}",
        "",
        DISCLAIMER_CRYPTO,
    )
    return "\n".join(lines) + "\n"


def _build_incident_draft(
    fixture: dict[str, Any],
    *,
    markdown: str | None = None,
) -> tuple[PublicDocumentDraft, PublicDocumentContext, SegmentCoverage]:
    incident = fixture["incident"]
    target_date = date.fromisoformat(incident["target_date"])
    segment = cast(MarketSegment, incident["segment"])
    watchpoint = fixture["input_bullets"][0]
    rendered = (
        _canonical_incident_markdown(target_date, watchpoint) if markdown is None else markdown
    )
    expectation = PublicRegionExpectation(
        target_date=target_date,
        segment=segment,
        segmented_mode=True,
        supplement_ids=(),
        shared_macro_required=False,
        crypto_indicators_required=False,
        channel_anchors_required=False,
        daily_thesis_required=False,
        anchor_table_required=False,
    )
    layout = PublicDocumentLayout.reindex(rendered, expectation=expectation)
    briefing = Briefing(
        target_date=target_date,
        market_summary="공개 근거를 요약합니다.",
        key_issues="핵심 이슈를 확인합니다.",
        sector_flow="수급 흐름을 확인합니다.",
        indicators_events="주요 지표를 확인합니다.",
        notable_tickers="주요 자산을 확인합니다.",
        today_watch=watchpoint,
        disclaimer=DISCLAIMER_CRYPTO,
        rendered_markdown=rendered,
    )
    coverage = SegmentCoverage(
        segment=segment,
        status="normal",
        item_count=1,
        source_count=1,
        categories=("price",),
        missing_categories=(),
    )
    context = PublicDocumentContext(
        target_date=target_date,
        expected_segments=(segment,),
        input_absences={},
        anchors_by_segment={},
        items_by_segment={},
        coverage_by_segment={segment: coverage},
        source_outcomes=(SourceOutcome.ok("fixture-price", "price", 1),),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=target_date),
        entity_observed_at_utc=datetime(2026, 7, 17, 12, tzinfo=UTC),
    )
    return (
        _new_generated_draft(briefing, segment=segment, layout=layout),
        context,
        coverage,
    )


def test_run_29707052598_watchpoint_shape_seals_without_raw_public_label() -> None:
    fixture = _load_fixture()
    incident = fixture["incident"]
    target_date = date.fromisoformat(incident["target_date"])
    segment = cast(MarketSegment, incident["segment"])
    assert segment == CRYPTO
    assert incident["terminal_issue_code"] == "public_diagnostic.raw_label"
    assert any(
        issue.code == incident["terminal_issue_code"]
        for issue in find_surface_quality_issues(fixture["markdown_after_watchpoint"])
    )

    generated, context, coverage = _build_incident_draft(fixture)
    assembled_snapshots: list[PublicDocumentDraft] = []

    def assemble(
        draft: PublicDocumentDraft,
        active_context: PublicDocumentContext,
    ) -> PublicDocumentDraft:
        assembled = _assemble_phase_one_reader_draft(draft, active_context)
        assert assembled.phase == "assembled"
        assert fixture["expected_row"]["implication"] not in assembled.layout.markdown
        assert not any(
            issue.code == incident["terminal_issue_code"]
            for issue in find_surface_quality_issues(assembled.layout.markdown)
        )
        assembled_snapshots.append(assembled)
        return assembled

    def repair(
        draft: PublicDocumentDraft,
        active_context: PublicDocumentContext,
    ) -> PublicDocumentDraft:
        assert active_context is context
        return _transition_draft(draft, next_phase="repaired")

    def validate(
        draft: PublicDocumentDraft,
        active_context: PublicDocumentContext,
    ) -> PublicDocumentDraft:
        assert find_reader_visible_public_label_leaks(draft.layout) == ()
        assert not any(
            issue.code == incident["terminal_issue_code"]
            for issue in find_surface_quality_issues(draft.layout.markdown)
        )
        assert _scan_terminal_entity_fact_claims(draft, active_context) == ()
        return _transition_draft(
            draft,
            next_phase="validated",
            notification_summary=PublicNotificationSummary(
                segment=segment,
                target_date=target_date,
                conclusion="[관망] 공개 근거를 확인합니다.",
                coverage_status=coverage.status,
                coverage_label=coverage.status_label,
            ),
        )

    finalized = _finalize_segment_skeleton(
        generated,
        context=context,
        handlers=_FinalizationPhaseHandlers(
            assemble=assemble,
            project=_project_assembled_draft,
            repair=repair,
            validate=validate,
            artifact_ids=lambda draft, active_context: (),
        ),
    )

    assert isinstance(finalized, FinalizedPublicDocument)
    assert finalized.segment == CRYPTO
    assert finalized.target_date == target_date
    assert len(assembled_snapshots) == 1
    assert "관심 영향 데이터 부족" not in finalized.briefing.rendered_markdown
    assert not any(
        issue.code == incident["terminal_issue_code"]
        for issue in find_surface_quality_issues(finalized.briefing.rendered_markdown)
    )


def test_phase_one_watchpoint_rewrite_preserves_typed_visual_supplement() -> None:
    fixture = _load_fixture()
    generated, context, _coverage = _build_incident_draft(fixture)
    supplement = PublicDocumentSupplement(
        supplement_id="crypto.visual.watchlist-relevance",
        kind="visual",
        markdown="![관심 자산 관련성](watchlist-relevance.svg)",
        stable_order=1,
    )
    fragment = _render_supplement_block(supplement)
    rendered = generated.source_briefing.rendered_markdown.replace(
        "## ⑥ 오늘의 관전 포인트\n\n",
        f"## ⑥ 오늘의 관전 포인트\n\n{fragment}\n",
    )
    expectation = replace(
        generated.layout.expectation,
        supplement_ids=(supplement.supplement_id,),
    )
    briefing = generated.source_briefing.model_copy(update={"rendered_markdown": rendered})
    draft = _new_generated_draft(
        briefing,
        segment=generated.segment,
        layout=PublicDocumentLayout.reindex(rendered, expectation=expectation),
    )
    active_context = replace(
        context,
        supplements_by_segment={generated.segment: (supplement,)},
    )

    assembled = _assemble_phase_one_reader_draft(draft, active_context)

    assert assembled.phase == "assembled"
    assert assembled.layout.markdown.count(fragment) == 1
    assert "#### 관찰 신호:" in assembled.layout.markdown


def test_run_29707052598_legacy_assembled_shape_crosses_real_projection() -> None:
    fixture = _load_fixture()
    watchpoint = fixture["input_bullets"][0]
    target_date = date.fromisoformat(fixture["incident"]["target_date"])
    legacy_watchpoint_body = (
        fixture["markdown_after_watchpoint"]
        .split(
            "## ⑥ 오늘의 관전 포인트\n\n",
            maxsplit=1,
        )[1]
        .strip()
    )
    legacy_markdown = _canonical_incident_markdown(target_date, watchpoint).replace(
        f"- {watchpoint}",
        legacy_watchpoint_body,
    )
    generated, context, _ = _build_incident_draft(fixture, markdown=legacy_markdown)
    assembled = _transition_draft(generated, next_phase="assembled")

    assert find_reader_visible_public_label_leaks(assembled.layout)
    assert any(
        issue.code == fixture["incident"]["terminal_issue_code"]
        for issue in find_surface_quality_issues(assembled.layout.markdown)
    )

    projected = _project_assembled_draft(assembled, context)

    assert projected.phase == "projected"
    assert find_reader_visible_public_label_leaks(projected.layout) == ()
    assert not any(
        issue.code == fixture["incident"]["terminal_issue_code"]
        for issue in find_surface_quality_issues(projected.layout.markdown)
    )
