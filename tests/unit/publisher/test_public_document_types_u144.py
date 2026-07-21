"""Contract tests for the first u144 lifecycle/type slice."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
from types import MappingProxyType

import pytest

from investo.models.bundle_context import (
    BundleContext,
    DailyThesisDecision,
    MarketStateSummary,
)
from investo.models.facts import VerifiedFactBundle
from investo.models.items import NormalizedItem
from investo.models.public_notification import PublicNotificationSummary
from investo.models.segments import DOMESTIC_EQUITY, SegmentCoverage
from investo.publisher import FinalizedPublicBundle, FinalizedPublicDocument
from investo.publisher.public_document import (
    PublicDocumentContext,
    PublicDocumentDraft,
    PublicDocumentFinalizationError,
    PublicDocumentLayout,
    PublicDocumentSupplement,
    PublicRegionExpectation,
    SegmentFinalizationOutcome,
    StagedArtifact,
    _build_finalized_bundle,
    _new_generated_draft,
    _seal_document,
    _transition_draft,
)
from tests._helpers.briefings import build_briefing

_TARGET_DATE = date(2026, 7, 21)
_DIGEST = sha256(b"asset").hexdigest()


def _coverage() -> SegmentCoverage:
    return SegmentCoverage(
        segment=DOMESTIC_EQUITY,
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


def _notification() -> PublicNotificationSummary:
    return PublicNotificationSummary(
        segment=DOMESTIC_EQUITY,
        target_date=_TARGET_DATE,
        conclusion="[관망] 확인된 결론",
        coverage_status="normal",
        coverage_label="정상",
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
