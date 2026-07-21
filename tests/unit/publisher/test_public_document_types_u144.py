"""Contract tests for the first u144 lifecycle/type slice."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
from types import MappingProxyType

import pytest

from investo.models.briefing import Briefing
from investo.models.bundle_context import (
    BundleContext,
    DailyThesisDecision,
    MarketStateSummary,
)
from investo.models.facts import VerifiedFactBundle
from investo.models.items import NormalizedItem
from investo.models.public_notification import PublicNotificationSummary
from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
    SegmentCoverage,
)
from investo.publisher import FinalizedPublicBundle, FinalizedPublicDocument
from investo.publisher.public_document import (
    _REGION_SPECS,
    PublicDocumentContext,
    PublicDocumentDraft,
    PublicDocumentFinalizationError,
    PublicDocumentLayout,
    PublicDocumentSupplement,
    PublicNotificationSummaryError,
    PublicRegionExpectation,
    SegmentFinalizationOutcome,
    SegmentInputAbsence,
    StagedArtifact,
    _build_finalized_bundle,
    _FinalizationPhaseHandlers,
    _finalize_bundle_skeleton,
    _finalize_segment_skeleton,
    _new_generated_draft,
    _render_supplement_block,
    _seal_document,
    _SegmentTrustBlockedError,
    _transition_draft,
)
from tests._helpers.briefings import build_briefing

_TARGET_DATE = date(2026, 7, 21)
_DIGEST = sha256(b"asset").hexdigest()


def _coverage(segment: MarketSegment = DOMESTIC_EQUITY) -> SegmentCoverage:
    return SegmentCoverage(
        segment=segment,
        status="normal",
        item_count=0,
        source_count=0,
        categories=(),
        missing_categories=(),
    )


def _expectation(*, supplement_ids: tuple[str, ...] = ()) -> PublicRegionExpectation:
    return PublicRegionExpectation(
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


def _region_expectation(
    *,
    segment: MarketSegment = DOMESTIC_EQUITY,
    segmented_mode: bool = True,
    supplement_ids: tuple[str, ...] = (),
    shared_macro_required: bool = False,
    crypto_indicators_required: bool = False,
    channel_anchors_required: bool = False,
    daily_thesis_required: bool = False,
    anchor_table_required: bool = False,
) -> PublicRegionExpectation:
    return PublicRegionExpectation(
        target_date=_TARGET_DATE,
        segment=segment,
        segmented_mode=segmented_mode,
        supplement_ids=supplement_ids,
        shared_macro_required=shared_macro_required,
        crypto_indicators_required=crypto_indicators_required,
        channel_anchors_required=channel_anchors_required,
        daily_thesis_required=daily_thesis_required,
        anchor_table_required=anchor_table_required,
    )


def _canonical_region_markdown(
    *,
    segment: MarketSegment = DOMESTIC_EQUITY,
    segmented_mode: bool = True,
    supplements: tuple[PublicDocumentSupplement, ...] = (),
    shared_macro: bool = False,
    crypto_indicators: bool = False,
    channel_anchors: bool = False,
    daily_thesis: bool = False,
    anchor_rows: tuple[str, ...] = (),
    cause: bool = False,
) -> str:
    label = {
        DOMESTIC_EQUITY: "국내 증시",
        US_EQUITY: "미국 증시",
        CRYPTO: "크립토",
    }[segment]
    short_disclaimer = (
        "> 정보 제공용 자동 시황이며 가상자산 매매 권유가 아닙니다. "
        "가상자산은 가격 변동성이 매우 큽니다."
        if segment == CRYPTO
        else "> 정보 제공용 자동 시황이며 매매 권유가 아닙니다."
    )
    lines = [f"# {_TARGET_DATE.isoformat()} {label} 시황", ""]
    if segmented_mode:
        lines.extend(("**세그먼트**: [국내](/domestic)", ""))
    lines.extend((short_disclaimer, ""))
    for supplement in supplements:
        lines.extend((_render_supplement_block(supplement), ""))
    if cause:
        lines.extend(("> **크로스마켓 연결 고리**: 금리와 수급", ""))
    if daily_thesis:
        lines.extend(("> **오늘의 큰 그림:** 확인 후 대응", ""))
    if anchor_rows:
        header = (
            "| 종목 | 스냅샷(UTC 24h) | 구간 변동 | 비고 |"
            if segment == CRYPTO
            else "| 종목 | 종가 | 변동 | 비고 |"
        )
        lines.extend((header, "|------|------|------|------|", *anchor_rows, ""))
    if shared_macro:
        lines.extend(("## ⓪ 오늘의 매크로", "", "매크로 본문", ""))
    if crypto_indicators:
        lines.extend(("## ⓪-A 크립토 지표 (UTC 24h 스냅샷)", "", "지표 본문", ""))
    if channel_anchors:
        lines.extend(("## ⓪-B 채널 기준선", "", "채널 본문", ""))
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
            "- 확인할 조건",
            "",
            "<details><summary>수집/품질 진단</summary>",
            "품질 본문",
            "</details>",
            "",
            "## ⑦ 면책조항",
            "",
            "본 문서는 정보 제공용입니다.",
        )
    )
    return "\n".join(lines) + "\n"


def _notification() -> PublicNotificationSummary:
    return PublicNotificationSummary(
        segment=DOMESTIC_EQUITY,
        target_date=_TARGET_DATE,
        conclusion="[관망] 확인된 결론",
        coverage_status="normal",
        coverage_label="정상",
    )


def _context(
    *,
    expected_segments: tuple[MarketSegment, ...] = (DOMESTIC_EQUITY,),
    input_absences: dict[MarketSegment, SegmentInputAbsence] | None = None,
) -> PublicDocumentContext:
    absences = {} if input_absences is None else input_absences
    generated = tuple(segment for segment in expected_segments if segment not in absences)
    return PublicDocumentContext(
        target_date=_TARGET_DATE,
        expected_segments=expected_segments,
        input_absences=absences,
        anchors_by_segment={},
        items_by_segment={},
        coverage_by_segment={segment: _coverage(segment) for segment in generated},
        source_outcomes=(),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=_TARGET_DATE),
        entity_observed_at_utc=datetime(2026, 7, 21, tzinfo=UTC),
    )


def _draft_factory(
    briefing: Briefing,
    segment: MarketSegment,
    context: PublicDocumentContext,
) -> PublicDocumentDraft:
    return _new_generated_draft(
        briefing,
        segment=segment,
        layout=PublicDocumentLayout(
            markdown=briefing.rendered_markdown,
            regions=(),
            expectation=PublicRegionExpectation(
                target_date=context.target_date,
                segment=segment,
                segmented_mode=True,
                supplement_ids=(),
                shared_macro_required=False,
                crypto_indicators_required=False,
                channel_anchors_required=False,
                daily_thesis_required=False,
                anchor_table_required=False,
            ),
        ),
    )


def _phase_handlers(events: list[str] | None = None) -> _FinalizationPhaseHandlers:
    seen = [] if events is None else events

    def assemble(draft: PublicDocumentDraft, context: PublicDocumentContext) -> PublicDocumentDraft:
        del context
        seen.append("assembled")
        return _transition_draft(draft, next_phase="assembled")

    def project(draft: PublicDocumentDraft, context: PublicDocumentContext) -> PublicDocumentDraft:
        del context
        seen.append("projected")
        return _transition_draft(draft, next_phase="projected")

    def repair(draft: PublicDocumentDraft, context: PublicDocumentContext) -> PublicDocumentDraft:
        del context
        seen.append("repaired")
        return _transition_draft(draft, next_phase="repaired")

    def validate(draft: PublicDocumentDraft, context: PublicDocumentContext) -> PublicDocumentDraft:
        seen.append("validated")
        coverage = context.coverage_by_segment[draft.segment]
        return _transition_draft(
            draft,
            next_phase="validated",
            notification_summary=PublicNotificationSummary(
                segment=draft.segment,
                target_date=draft.target_date,
                conclusion="[관망] 확인된 결론",
                coverage_status=coverage.status,
                coverage_label=coverage.status_label,
            ),
        )

    return _FinalizationPhaseHandlers(
        assemble=assemble,
        project=project,
        repair=repair,
        validate=validate,
        artifact_ids=lambda draft, context: (),
    )


def _validated_draft(*, supplement_ids: tuple[str, ...] = ()) -> PublicDocumentDraft:
    briefing = build_briefing(target_date=_TARGET_DATE)
    markdown = f"{briefing.rendered_markdown}\n<!-- sealed -->\n"
    generated = _new_generated_draft(
        briefing,
        segment=DOMESTIC_EQUITY,
        layout=PublicDocumentLayout(
            markdown=briefing.rendered_markdown,
            regions=(),
            expectation=_expectation(supplement_ids=supplement_ids),
        ),
    )
    assembled = _transition_draft(
        generated,
        next_phase="assembled",
        layout=PublicDocumentLayout(
            markdown=markdown,
            regions=(),
            expectation=_expectation(supplement_ids=supplement_ids),
        ),
    )
    projected = _transition_draft(assembled, next_phase="projected")
    repaired = _transition_draft(projected, next_phase="repaired")
    return _transition_draft(
        repaired,
        next_phase="validated",
        notification_summary=_notification(),
    )


def test_context_freezes_and_referentially_checks_supplements(tmp_path: Path) -> None:
    artifact = StagedArtifact(
        artifact_id="hero.svg",
        segment=DOMESTIC_EQUITY,
        kind="visual",
        relative_public_path=PurePosixPath("assets/hero.svg"),
        staged_path=tmp_path / "hero.svg",
        sha256=_DIGEST,
    )
    supplement = PublicDocumentSupplement(
        supplement_id="hero",
        kind="visual",
        markdown="![시장 카드](assets/hero.svg)",
        stable_order=1,
        artifact_ids=(artifact.artifact_id,),
    )

    context = PublicDocumentContext(
        target_date=_TARGET_DATE,
        expected_segments=(DOMESTIC_EQUITY,),
        input_absences={},
        anchors_by_segment={DOMESTIC_EQUITY: ()},
        items_by_segment={DOMESTIC_EQUITY: ()},
        coverage_by_segment={DOMESTIC_EQUITY: _coverage()},
        source_outcomes=(),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=_TARGET_DATE),
        entity_observed_at_utc=datetime(2026, 7, 21, tzinfo=UTC),
        supplements_by_segment={DOMESTIC_EQUITY: (supplement,)},
        staged_artifacts_by_segment={DOMESTIC_EQUITY: (artifact,)},
    )

    assert isinstance(context.coverage_by_segment, MappingProxyType)
    assert context.supplements_by_segment[DOMESTIC_EQUITY] == (supplement,)
    with pytest.raises(TypeError):
        context.coverage_by_segment[DOMESTIC_EQUITY] = _coverage()  # type: ignore[index]


def test_context_rejects_unreferenced_artifact(tmp_path: Path) -> None:
    artifact = StagedArtifact(
        artifact_id="unused.svg",
        segment=DOMESTIC_EQUITY,
        kind="visual",
        relative_public_path=PurePosixPath("assets/unused.svg"),
        staged_path=tmp_path / "unused.svg",
        sha256=_DIGEST,
    )

    with pytest.raises(ValueError, match="referenced by one supplement"):
        PublicDocumentContext(
            target_date=_TARGET_DATE,
            expected_segments=(DOMESTIC_EQUITY,),
            input_absences={},
            anchors_by_segment={},
            items_by_segment={},
            coverage_by_segment={DOMESTIC_EQUITY: _coverage()},
            source_outcomes=(),
            bundle_context=None,
            fact_bundle=VerifiedFactBundle(target_date=_TARGET_DATE),
            entity_observed_at_utc=datetime(2026, 7, 21, tzinfo=UTC),
            staged_artifacts_by_segment={DOMESTIC_EQUITY: (artifact,)},
        )


def test_context_defensively_freezes_nested_model_mappings() -> None:
    item = NormalizedItem(
        source_name="source",
        category="price",
        title="price",
        published_at=datetime(2026, 7, 21, tzinfo=UTC),
        raw_metadata={"ticker": "ORIGINAL"},
    )
    bundle_context = BundleContext(
        bundle_id="u144-test",
        target_kst_date=_TARGET_DATE,
        segments={
            DOMESTIC_EQUITY: MarketStateSummary(
                segment=DOMESTIC_EQUITY,
                target_date=_TARGET_DATE,
                tz="Asia/Seoul",
                close_state="close",
            )
        },
        daily_thesis_decision=DailyThesisDecision(
            mode="strong",
            per_segment_lines={DOMESTIC_EQUITY: "original line"},
            reason="test",
        ),
    )
    context = PublicDocumentContext(
        target_date=_TARGET_DATE,
        expected_segments=(DOMESTIC_EQUITY,),
        input_absences={},
        anchors_by_segment={},
        items_by_segment={DOMESTIC_EQUITY: (item,)},
        coverage_by_segment={DOMESTIC_EQUITY: _coverage()},
        source_outcomes=(),
        bundle_context=bundle_context,
        fact_bundle=VerifiedFactBundle(target_date=_TARGET_DATE),
        entity_observed_at_utc=datetime(2026, 7, 21, tzinfo=UTC),
    )

    item.raw_metadata["ticker"] = "MUTATED"
    bundle_context.segments.clear()
    bundle_context.daily_thesis_decision.per_segment_lines[DOMESTIC_EQUITY] = "mutated"

    frozen_item = context.items_by_segment[DOMESTIC_EQUITY][0]
    assert frozen_item.raw_metadata["ticker"] == "ORIGINAL"
    assert context.bundle_context is not None
    assert DOMESTIC_EQUITY in context.bundle_context.segments
    assert (
        context.bundle_context.daily_thesis_decision.per_segment_lines[DOMESTIC_EQUITY]
        == "original line"
    )
    with pytest.raises(TypeError):
        frozen_item.raw_metadata["ticker"] = "blocked"


def test_seal_factory_creates_exact_final_compatibility_view() -> None:
    draft = _validated_draft()

    document = _seal_document(draft, warnings=("surface.warning", "surface.warning"))

    assert document.briefing is not draft.source_briefing
    assert document.briefing.rendered_markdown == draft.layout.markdown
    assert document.markdown_sha256 == sha256(draft.layout.markdown.encode()).hexdigest()
    assert document.notification_summary is draft.notification_summary
    assert document.warnings == ("surface.warning",)
    with pytest.raises(FrozenInstanceError):
        document.markdown_sha256 = "0" * 64  # type: ignore[misc]


def test_finalized_document_has_no_public_constructor() -> None:
    with pytest.raises(TypeError):
        FinalizedPublicDocument()  # type: ignore[call-arg]

    with pytest.raises(TypeError):
        PublicDocumentDraft()  # type: ignore[call-arg]


def test_bundle_requires_outcome_and_promotion_manifest_agreement(tmp_path: Path) -> None:
    artifact = StagedArtifact(
        artifact_id="hero.svg",
        segment=DOMESTIC_EQUITY,
        kind="visual",
        relative_public_path=PurePosixPath("assets/hero.svg"),
        staged_path=tmp_path / "hero.svg",
        sha256=_DIGEST,
    )
    supplement = PublicDocumentSupplement(
        supplement_id="hero",
        kind="visual",
        markdown="![시장 카드](assets/hero.svg)",
        stable_order=1,
        artifact_ids=(artifact.artifact_id,),
    )
    context = PublicDocumentContext(
        target_date=_TARGET_DATE,
        expected_segments=(DOMESTIC_EQUITY,),
        input_absences={},
        anchors_by_segment={},
        items_by_segment={},
        coverage_by_segment={DOMESTIC_EQUITY: _coverage()},
        source_outcomes=(),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=_TARGET_DATE),
        entity_observed_at_utc=datetime(2026, 7, 21, tzinfo=UTC),
        supplements_by_segment={DOMESTIC_EQUITY: (supplement,)},
        staged_artifacts_by_segment={DOMESTIC_EQUITY: (artifact,)},
    )
    draft = _validated_draft(supplement_ids=(supplement.supplement_id,))
    document = _seal_document(draft, staged_artifact_ids=("hero.svg",))

    bundle = _build_finalized_bundle(
        context,
        documents=(document,),
        segment_outcomes=(SegmentFinalizationOutcome(segment=DOMESTIC_EQUITY, state="finalized"),),
    )

    assert bundle.documents == (document,)
    assert bundle.promotion_manifest == (artifact,)
    assert bundle.promotion_manifest[0] is artifact
    with pytest.raises(TypeError):
        FinalizedPublicBundle()  # type: ignore[call-arg]


def test_finalization_error_message_never_renders_cause() -> None:
    secret_cause = RuntimeError("token=must-not-render")
    error = PublicDocumentFinalizationError(
        target_date=_TARGET_DATE,
        segment=DOMESTIC_EQUITY,
        phase="validated",
        issue_codes=("summary.invalid", "summary.invalid"),
        cause=secret_cause,
    )

    assert error.issue_codes == ("summary.invalid",)
    assert error.cause is secret_cause
    assert "must-not-render" not in str(error)


def test_notification_summary_error_is_bounded_and_carries_only_issue_code() -> None:
    error = PublicNotificationSummaryError("summary.invalid_conclusion")

    assert error.issue_code == "summary.invalid_conclusion"
    assert str(error) == "public notification summary invalid: code=summary.invalid_conclusion"

    with pytest.raises(ValueError, match="unsupported public notification summary issue code"):
        PublicNotificationSummaryError("secret=value")  # type: ignore[arg-type]


def test_segment_skeleton_runs_declared_phase_order_and_seals() -> None:
    context = _context()
    briefing = build_briefing(target_date=_TARGET_DATE)
    draft = _draft_factory(briefing, DOMESTIC_EQUITY, context)
    events: list[str] = []

    document = _finalize_segment_skeleton(
        draft,
        context=context,
        handlers=_phase_handlers(events),
    )

    assert events == ["assembled", "projected", "repaired", "validated"]
    assert document.segment == DOMESTIC_EQUITY
    assert document.briefing.rendered_markdown == briefing.rendered_markdown


def test_segment_skeleton_rejects_handler_that_skips_phase() -> None:
    context = _context()
    briefing = build_briefing(target_date=_TARGET_DATE)
    draft = _draft_factory(briefing, DOMESTIC_EQUITY, context)
    valid = _phase_handlers()
    invalid = _FinalizationPhaseHandlers(
        assemble=lambda current, _: current,
        project=valid.project,
        repair=valid.repair,
        validate=valid.validate,
        artifact_ids=valid.artifact_ids,
    )

    with pytest.raises(ValueError, match=r"invariant\.phase_transition"):
        _finalize_segment_skeleton(draft, context=context, handlers=invalid)


def test_transition_factory_rejects_direct_phase_skip() -> None:
    context = _context()
    draft = _draft_factory(
        build_briefing(target_date=_TARGET_DATE),
        DOMESTIC_EQUITY,
        context,
    )

    with pytest.raises(
        ValueError,
        match="invalid public-document phase transition: generated->projected",
    ):
        _transition_draft(draft, next_phase="projected")


def test_bundle_skeleton_converts_phase_skip_to_bounded_e8() -> None:
    context = _context()
    briefing = build_briefing(target_date=_TARGET_DATE)
    valid = _phase_handlers()
    invalid = _FinalizationPhaseHandlers(
        assemble=lambda current, _: current,
        project=valid.project,
        repair=valid.repair,
        validate=valid.validate,
        artifact_ids=valid.artifact_ids,
    )

    with pytest.raises(PublicDocumentFinalizationError) as exc:
        _finalize_bundle_skeleton(
            {DOMESTIC_EQUITY: briefing},
            context=context,
            draft_factory=_draft_factory,
            handlers=invalid,
        )

    assert exc.value.segment == DOMESTIC_EQUITY
    assert exc.value.phase == "assembled"
    assert exc.value.issue_codes == ("invariant.phase_transition",)
    assert exc.value.cause is not None


def test_bundle_skeleton_converts_briefing_identity_swap_to_bounded_e8() -> None:
    context = _context()
    briefing = build_briefing(target_date=_TARGET_DATE)
    valid = _phase_handlers()

    def swap_briefing(
        draft: PublicDocumentDraft, phase_context: PublicDocumentContext
    ) -> PublicDocumentDraft:
        replacement = build_briefing(target_date=draft.target_date)
        replacement_draft = _draft_factory(replacement, draft.segment, phase_context)
        return _transition_draft(replacement_draft, next_phase="assembled")

    invalid = _FinalizationPhaseHandlers(
        assemble=swap_briefing,
        project=valid.project,
        repair=valid.repair,
        validate=valid.validate,
        artifact_ids=valid.artifact_ids,
    )

    with pytest.raises(PublicDocumentFinalizationError) as exc:
        _finalize_bundle_skeleton(
            {DOMESTIC_EQUITY: briefing},
            context=context,
            draft_factory=_draft_factory,
            handlers=invalid,
        )

    assert exc.value.segment == DOMESTIC_EQUITY
    assert exc.value.phase == "assembled"
    assert exc.value.issue_codes == ("invariant.briefing_identity",)
    assert exc.value.cause is not None


def test_bundle_skeleton_bounds_unexpected_handler_exception() -> None:
    context = _context()
    briefing = build_briefing(target_date=_TARGET_DATE)
    valid = _phase_handlers()

    def explode(
        draft: PublicDocumentDraft, phase_context: PublicDocumentContext
    ) -> PublicDocumentDraft:
        del draft, phase_context
        raise RuntimeError("secret payload must not render")

    handlers = _FinalizationPhaseHandlers(
        assemble=explode,
        project=valid.project,
        repair=valid.repair,
        validate=valid.validate,
        artifact_ids=valid.artifact_ids,
    )

    with pytest.raises(PublicDocumentFinalizationError) as exc:
        _finalize_bundle_skeleton(
            {DOMESTIC_EQUITY: briefing},
            context=context,
            draft_factory=_draft_factory,
            handlers=handlers,
        )

    assert exc.value.issue_codes == ("invariant.phase_handler_exception",)
    assert isinstance(exc.value.cause, RuntimeError)
    assert "secret payload" not in str(exc.value)


def test_bundle_skeleton_preserves_typed_generation_absence() -> None:
    context = _context(
        expected_segments=(DOMESTIC_EQUITY, US_EQUITY),
        input_absences={US_EQUITY: "generation_failed"},
    )
    briefing = build_briefing(target_date=_TARGET_DATE)

    bundle = _finalize_bundle_skeleton(
        {DOMESTIC_EQUITY: briefing},
        context=context,
        draft_factory=_draft_factory,
        handlers=_phase_handlers(),
    )

    assert tuple(outcome.state for outcome in bundle.segment_outcomes) == (
        "finalized",
        "generation_absent",
    )
    assert bundle.documents[0].segment == DOMESTIC_EQUITY


def test_bundle_skeleton_zero_survivors_raises_bounded_e8() -> None:
    context = _context()
    briefing = build_briefing(target_date=_TARGET_DATE)
    valid = _phase_handlers()

    def block(draft: PublicDocumentDraft, context: PublicDocumentContext) -> PublicDocumentDraft:
        del draft, context
        raise _SegmentTrustBlockedError(
            phase="assembled",
            issue_codes=("numeric.anchor_assertion",),
        )

    handlers = _FinalizationPhaseHandlers(
        assemble=block,
        project=valid.project,
        repair=valid.repair,
        validate=valid.validate,
        artifact_ids=valid.artifact_ids,
    )

    with pytest.raises(PublicDocumentFinalizationError) as exc:
        _finalize_bundle_skeleton(
            {DOMESTIC_EQUITY: briefing},
            context=context,
            draft_factory=_draft_factory,
            handlers=handlers,
        )

    assert exc.value.phase == "bundle"
    assert exc.value.issue_codes == (
        "bundle.zero_survivors",
        "numeric.anchor_assertion",
    )


def test_bundle_skeleton_keeps_valid_sibling_when_one_segment_is_trust_blocked() -> None:
    context = _context(expected_segments=(DOMESTIC_EQUITY, US_EQUITY))
    valid = _phase_handlers()

    def assemble(
        draft: PublicDocumentDraft, phase_context: PublicDocumentContext
    ) -> PublicDocumentDraft:
        if draft.segment == US_EQUITY:
            raise _SegmentTrustBlockedError(
                phase="assembled",
                issue_codes=("entity.fact_contradiction",),
            )
        return valid.assemble(draft, phase_context)

    handlers = _FinalizationPhaseHandlers(
        assemble=assemble,
        project=valid.project,
        repair=valid.repair,
        validate=valid.validate,
        artifact_ids=valid.artifact_ids,
    )

    bundle = _finalize_bundle_skeleton(
        {
            DOMESTIC_EQUITY: build_briefing(target_date=_TARGET_DATE),
            US_EQUITY: build_briefing(target_date=_TARGET_DATE),
        },
        context=context,
        draft_factory=_draft_factory,
        handlers=handlers,
    )

    assert tuple(document.segment for document in bundle.documents) == (DOMESTIC_EQUITY,)
    assert tuple(outcome.state for outcome in bundle.segment_outcomes) == (
        "finalized",
        "trust_blocked",
    )
    assert bundle.segment_outcomes[1].issue_codes == ("entity.fact_contradiction",)


def test_bundle_skeleton_rejects_unexplained_missing_briefing() -> None:
    context = _context()

    with pytest.raises(PublicDocumentFinalizationError) as exc:
        _finalize_bundle_skeleton(
            {},
            context=context,
            draft_factory=_draft_factory,
            handlers=_phase_handlers(),
        )

    assert exc.value.phase == "input"
    assert exc.value.issue_codes == ("input.briefing_keys",)


def test_region_spec_table_matches_all_seventeen_fd_priorities() -> None:
    assert tuple(spec.id_pattern for spec in _REGION_SPECS) == (
        "disclaimer:canonical",
        "diagnostics:quality",
        "chart:{supplement_id}",
        "visual:{supplement_id}",
        "carryover:{supplement_id}",
        "macro:shared",
        "indicator:crypto",
        "anchor:channel",
        "cause:cross_market",
        "thesis:daily",
        "navigation:segments",
        "disclaimer:short",
        "anchor:market",
        "watchpoints:section[`:continuation:{ordinal}`]",
        "section:{n}[`:continuation:{ordinal}`]",
        "header:title",
        "first_viewport:{ordinal}",
    )
    assert tuple(spec.block for spec in _REGION_SPECS) == (
        "disclaimer",
        "diagnostics",
        "chart",
        "visual",
        "carryover",
        "shared_macro",
        "crypto_indicators",
        "channel_anchors",
        "cause_map",
        "daily_thesis",
        "navigation",
        "disclaimer",
        "anchor_table",
        "watchpoints",
        "section_body",
        "header",
        "first_viewport",
    )
    assert tuple(spec.requirement for spec in _REGION_SPECS) == (
        "always",
        "always",
        "conditional",
        "conditional",
        "conditional",
        "conditional",
        "conditional",
        "conditional",
        "optional",
        "conditional",
        "conditional",
        "always",
        "conditional",
        "always",
        "always",
        "always",
        "conditional",
    )


def test_region_reindex_forms_exact_partition_with_active_conditions() -> None:
    supplements = (
        PublicDocumentSupplement(
            supplement_id="chart-one",
            kind="chart",
            markdown="![차트](chart.svg)",
            stable_order=1,
        ),
        PublicDocumentSupplement(
            supplement_id="carry-one",
            kind="carryover",
            markdown="## Watchlist Carryover\n\n| 항목 | 상태 |\n|---|---|\n| CPI | 확인 |",
            stable_order=2,
        ),
    )
    expectation = _region_expectation(
        supplement_ids=tuple(item.supplement_id for item in supplements),
        shared_macro_required=True,
        channel_anchors_required=True,
        daily_thesis_required=True,
        anchor_table_required=True,
    )
    markdown = _canonical_region_markdown(
        supplements=supplements,
        shared_macro=True,
        channel_anchors=True,
        daily_thesis=True,
        anchor_rows=("| KOSPI | 2,900 | +1.0% | 마감 |",),
        cause=True,
    )

    layout = PublicDocumentLayout.reindex(markdown, expectation=expectation)

    assert layout.markdown == markdown
    assert layout.regions[0].start == 0
    assert layout.regions[-1].end == len(markdown)
    assert all(
        left.end == right.start
        for left, right in zip(layout.regions, layout.regions[1:], strict=False)
    )
    region_ids = {region.region_id for region in layout.regions}
    assert {
        "chart:chart-one",
        "carryover:carry-one",
        "macro:shared",
        "anchor:channel",
        "cause:cross_market",
        "thesis:daily",
        "anchor:market",
        "section:1",
        "section:5",
        "watchpoints:section",
        "diagnostics:quality",
        "disclaimer:canonical",
    } <= region_ids


@pytest.mark.parametrize(
    ("segment", "anchor_row", "expected_header"),
    (
        (DOMESTIC_EQUITY, "| KOSPI | 2,900 | +1.0% | 마감 |", "| 종목 | 종가 | 변동 | 비고 |"),
        (
            CRYPTO,
            "| BTC | 100,000 | +2.0% | UTC |",
            "| 종목 | 스냅샷(UTC 24h) | 구간 변동 | 비고 |",
        ),
    ),
)
def test_anchor_region_uses_exact_segment_header_and_empty_anchor_absence(
    segment: MarketSegment,
    anchor_row: str,
    expected_header: str,
) -> None:
    absent_markdown = _canonical_region_markdown(segment=segment)
    absent = PublicDocumentLayout.reindex(
        absent_markdown,
        expectation=_region_expectation(segment=segment),
    )
    assert "anchor:market" not in {region.region_id for region in absent.regions}

    present_markdown = _canonical_region_markdown(segment=segment, anchor_rows=(anchor_row,))
    present = PublicDocumentLayout.reindex(
        present_markdown,
        expectation=_region_expectation(segment=segment, anchor_table_required=True),
    )
    anchor = next(region for region in present.regions if region.region_id == "anchor:market")
    assert present.markdown[anchor.start : anchor.content_start].startswith(expected_header)

    with pytest.raises(ValueError, match=r"structure.unexpected.anchor:market"):
        PublicDocumentLayout.reindex(
            present_markdown,
            expectation=_region_expectation(segment=segment),
        )


def test_crypto_indicator_is_active_pass_conditional_and_forbidden_on_sibling() -> None:
    crypto_markdown = _canonical_region_markdown(segment=CRYPTO, crypto_indicators=True)
    crypto = PublicDocumentLayout.reindex(
        crypto_markdown,
        expectation=_region_expectation(segment=CRYPTO, crypto_indicators_required=True),
    )
    assert "indicator:crypto" in {region.region_id for region in crypto.regions}

    sibling_markdown = _canonical_region_markdown(crypto_indicators=True)
    with pytest.raises(ValueError, match=r"structure.unexpected.indicator:crypto"):
        PublicDocumentLayout.reindex(
            sibling_markdown,
            expectation=_region_expectation(),
        )


def test_channel_region_ends_before_owned_cause_and_thesis_suffix() -> None:
    markdown = _canonical_region_markdown(channel_anchors=True)
    channel_body = "## ⓪-B 채널 기준선\n\n채널 본문\n\n"
    markdown = markdown.replace(
        channel_body,
        channel_body
        + "> **크로스마켓 연결 고리**: 금리와 수급\n"
        + "> **오늘의 큰 그림:** 확인 후 대응\n",
    )
    layout = PublicDocumentLayout.reindex(
        markdown,
        expectation=_region_expectation(
            channel_anchors_required=True,
            daily_thesis_required=True,
        ),
    )

    by_id = {region.region_id: region for region in layout.regions}
    assert by_id["anchor:channel"].end == by_id["cause:cross_market"].start
    assert by_id["cause:cross_market"].end == by_id["thesis:daily"].start


def test_marker_pairing_and_carryover_heading_fail_closed() -> None:
    supplement = PublicDocumentSupplement(
        supplement_id="hero",
        kind="visual",
        markdown="![hero](hero.svg)",
        stable_order=1,
    )
    markdown = _canonical_region_markdown(supplements=(supplement,))
    expectation = _region_expectation(supplement_ids=("hero",))

    with pytest.raises(ValueError, match=r"structure.mismatched_supplement_marker"):
        PublicDocumentLayout.reindex(
            markdown.replace(
                "<!-- /investo:block visual:hero -->",
                "<!-- /investo:block visual:other -->",
            ),
            expectation=expectation,
        )

    bad_carryover = PublicDocumentSupplement(
        supplement_id="carry",
        kind="carryover",
        markdown="제목 없는 본문",
        stable_order=1,
    )
    with pytest.raises(ValueError, match=r"structure.carryover_heading"):
        PublicDocumentLayout.reindex(
            _canonical_region_markdown(supplements=(bad_carryover,)),
            expectation=_region_expectation(supplement_ids=("carry",)),
        )


def test_region_replacement_targets_duplicate_evidence_by_region_id() -> None:
    first = PublicDocumentSupplement(
        supplement_id="first",
        kind="visual",
        markdown="동일 근거",
        stable_order=1,
    )
    second = PublicDocumentSupplement(
        supplement_id="second",
        kind="visual",
        markdown="동일 근거",
        stable_order=2,
    )
    markdown = _canonical_region_markdown(supplements=(first, second))
    layout = PublicDocumentLayout.reindex(
        markdown,
        expectation=_region_expectation(supplement_ids=("first", "second")),
    )

    replaced = layout.replace_region_body("visual:second", "교체 근거\n")

    first_region = next(region for region in replaced.regions if region.region_id == "visual:first")
    second_region = next(
        region for region in replaced.regions if region.region_id == "visual:second"
    )
    assert replaced.markdown[first_region.content_start : first_region.content_end] == "동일 근거\n"
    assert (
        replaced.markdown[second_region.content_start : second_region.content_end] == "교체 근거\n"
    )
    assert tuple(region.region_id for region in replaced.regions) == tuple(
        region.region_id for region in layout.regions
    )


def test_marker_omission_preserves_empty_shell_and_reindexes() -> None:
    supplement = PublicDocumentSupplement(
        supplement_id="hero",
        kind="visual",
        markdown="![hero](hero.svg)",
        stable_order=1,
    )
    layout = PublicDocumentLayout.reindex(
        _canonical_region_markdown(supplements=(supplement,)),
        expectation=_region_expectation(supplement_ids=("hero",)),
    )

    omitted = layout.omit_optional_region("visual:hero")

    region = next(region for region in omitted.regions if region.region_id == "visual:hero")
    assert omitted.markdown[region.content_start : region.content_end] == ""
    assert (
        omitted.markdown[region.start : region.end]
        == "<!-- investo:block visual:hero -->\n<!-- /investo:block visual:hero -->\n"
    )
    with pytest.raises(ValueError, match="already omitted"):
        omitted.omit_optional_region("visual:hero")


def test_region_reindex_rejects_duplicate_missing_and_unexpected_numbered_h2() -> None:
    markdown = _canonical_region_markdown()
    expectation = _region_expectation()

    with pytest.raises(ValueError, match=r"structure.duplicate.section:1"):
        PublicDocumentLayout.reindex(
            markdown.replace("## ② 전일", "## ① 요약\n\n## ② 전일", 1),
            expectation=expectation,
        )
    with pytest.raises(ValueError, match=r"structure.missing.section:3"):
        PublicDocumentLayout.reindex(
            markdown.replace("## ③ 섹터/수급 동향", "## 섹터/수급 동향"),
            expectation=expectation,
        )

    with pytest.raises(ValueError, match=r"structure.unexpected_numbered_h2"):
        PublicDocumentLayout.reindex(
            markdown.replace("요약 본문", "요약 본문\n\n## ⑧ 비허용 섹션"),
            expectation=expectation,
        )

    with pytest.raises(ValueError, match=r"structure.unexpected_numbered_h2"):
        PublicDocumentLayout.reindex(
            markdown.replace("요약 본문", "요약 본문\n\n## ⓪-C 비허용 섹션"),
            expectation=expectation,
        )


@pytest.mark.parametrize(
    ("heading", "body", "primary_id", "continuation_id"),
    (
        ("① 요약", "요약 본문", "section:1", "section:1:continuation:1"),
        (
            "⑥ 오늘의 관전 포인트",
            "- 확인할 조건",
            "watchpoints:section",
            "watchpoints:section:continuation:1",
        ),
    ),
)
def test_section_scoped_marker_partitions_into_stable_continuation_regions(
    heading: str,
    body: str,
    primary_id: str,
    continuation_id: str,
) -> None:
    markdown = _canonical_region_markdown()

    supplement = PublicDocumentSupplement(
        supplement_id="inside-section",
        kind="visual",
        markdown="![섹션 시각물](section.svg)",
        stable_order=1,
    )
    marked = markdown.replace(
        f"## {heading}\n\n{body}",
        f"## {heading}\n\n{_render_supplement_block(supplement)}\n\n{body}",
    )

    layout = PublicDocumentLayout.reindex(
        marked,
        expectation=_region_expectation(supplement_ids=("inside-section",)),
    )

    region_ids = tuple(region.region_id for region in layout.regions)
    assert primary_id in region_ids
    assert "visual:inside-section" in region_ids
    assert continuation_id in region_ids
    assert all(
        left.end == right.start
        for left, right in zip(layout.regions, layout.regions[1:], strict=False)
    )
