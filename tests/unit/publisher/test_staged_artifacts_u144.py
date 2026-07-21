from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath

import pytest

from investo.models.facts import VerifiedFactBundle
from investo.models.public_artifact import StagedArtifact, build_staged_artifact
from investo.models.public_notification import PublicNotificationSummary
from investo.models.segments import DOMESTIC_EQUITY, SegmentCoverage
from investo.publisher.errors import PublisherIOError
from investo.publisher.public_document import (
    FinalizedPublicBundle,
    PublicDocumentContext,
    PublicDocumentLayout,
    PublicDocumentSupplement,
    PublicRegionExpectation,
    SegmentFinalizationOutcome,
    _build_finalized_bundle,
    _new_generated_draft,
    _seal_document,
    _transition_draft,
)
from investo.publisher.staged_artifacts import promote_finalized_bundle_artifacts
from tests._helpers.briefings import build_briefing

_TARGET_DATE = date(2026, 7, 21)


def _coverage() -> SegmentCoverage:
    return SegmentCoverage(
        segment=DOMESTIC_EQUITY,
        status="normal",
        item_count=0,
        source_count=0,
        categories=(),
        missing_categories=(),
    )


def _bundle_with_artifacts(artifacts: tuple[StagedArtifact, ...]) -> FinalizedPublicBundle:
    supplements = tuple(
        PublicDocumentSupplement(
            supplement_id=f"asset-{index}",
            kind=artifact.kind,
            markdown=f"file-backed supplement {index}",
            stable_order=index,
            artifact_ids=(artifact.artifact_id,),
        )
        for index, artifact in enumerate(artifacts)
    )
    briefing = build_briefing(target_date=_TARGET_DATE)
    expectation = PublicRegionExpectation(
        target_date=_TARGET_DATE,
        segment=DOMESTIC_EQUITY,
        segmented_mode=True,
        supplement_ids=tuple(supplement.supplement_id for supplement in supplements),
        shared_macro_required=False,
        crypto_indicators_required=False,
        channel_anchors_required=False,
        daily_thesis_required=False,
        anchor_table_required=False,
    )
    layout = PublicDocumentLayout(
        markdown=briefing.rendered_markdown,
        regions=(),
        expectation=expectation,
    )
    generated = _new_generated_draft(
        briefing,
        segment=DOMESTIC_EQUITY,
        layout=layout,
    )
    assembled = _transition_draft(generated, next_phase="assembled")
    projected = _transition_draft(assembled, next_phase="projected")
    repaired = _transition_draft(projected, next_phase="repaired")
    validated = _transition_draft(
        repaired,
        next_phase="validated",
        notification_summary=PublicNotificationSummary(
            segment=DOMESTIC_EQUITY,
            target_date=_TARGET_DATE,
            conclusion="[관망] 확인된 결론",
            coverage_status="normal",
            coverage_label="정상",
        ),
    )
    document = _seal_document(
        validated,
        staged_artifact_ids=tuple(artifact.artifact_id for artifact in artifacts),
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
        supplements_by_segment={DOMESTIC_EQUITY: supplements},
        staged_artifacts_by_segment={DOMESTIC_EQUITY: artifacts},
    )
    return _build_finalized_bundle(
        context,
        documents=(document,),
        segment_outcomes=(SegmentFinalizationOutcome(segment=DOMESTIC_EQUITY, state="finalized"),),
    )


def _artifact(staging_root: Path, name: str, payload: bytes) -> StagedArtifact:
    path = staging_root / f"domestic-equity/2026/07/2026-07-21.assets/{name}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return build_staged_artifact(
        staging_root=staging_root,
        staged_path=path,
        segment=DOMESTIC_EQUITY,
        kind="visual",
    )


def test_post_e6_promotion_writes_exact_manifest_and_snapshots_destination(
    tmp_path: Path,
) -> None:
    staging_root = tmp_path / "stage"
    artifact = _artifact(staging_root, "hero.svg", b"new")
    bundle = _bundle_with_artifacts((artifact,))
    archive_root = tmp_path / "archive"
    destination = archive_root.joinpath(*artifact.relative_public_path.parts)
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"old")
    snapshots: dict[Path, bytes | None] = {}

    promoted = promote_finalized_bundle_artifacts(
        bundle,
        staging_root=staging_root,
        archive_root=archive_root,
        snapshots=snapshots,
    )

    assert promoted == (destination.resolve(),)
    assert destination.read_bytes() == b"new"
    assert snapshots == {destination.resolve(): b"old"}


def test_manifest_validation_finishes_before_any_public_write(tmp_path: Path) -> None:
    staging_root = tmp_path / "stage"
    first = _artifact(staging_root, "first.svg", b"first")
    second = _artifact(staging_root, "second.svg", b"second")
    bundle = _bundle_with_artifacts((first, second))
    second.staged_path.write_bytes(b"tampered")
    archive_root = tmp_path / "archive"

    with pytest.raises(PublisherIOError):
        promote_finalized_bundle_artifacts(
            bundle,
            staging_root=staging_root,
            archive_root=archive_root,
            snapshots={},
        )

    assert not archive_root.exists()


def test_manifest_path_mismatch_is_rejected_without_public_write(tmp_path: Path) -> None:
    staging_root = tmp_path / "stage"
    artifact = _artifact(staging_root, "hero.svg", b"hero")
    outside = tmp_path / "outside.svg"
    outside.write_bytes(b"hero")
    mismatched = replace(artifact, staged_path=outside.resolve())
    bundle = _bundle_with_artifacts((mismatched,))
    archive_root = tmp_path / "archive"

    with pytest.raises(PublisherIOError):
        promote_finalized_bundle_artifacts(
            bundle,
            staging_root=staging_root,
            archive_root=archive_root,
            snapshots={},
        )

    assert not archive_root.exists()


def test_manifest_rejects_symlinked_source_parent_alias(tmp_path: Path) -> None:
    staging_root = tmp_path / "stage"
    artifact = _artifact(staging_root, "hero.svg", b"hero")
    real_parent = artifact.staged_path.parent
    alias_parent = staging_root / "alias"
    alias_parent.symlink_to(real_parent, target_is_directory=True)
    aliased = replace(
        artifact,
        relative_public_path=PurePosixPath("alias/hero.svg"),
        staged_path=alias_parent / "hero.svg",
    )
    bundle = _bundle_with_artifacts((aliased,))
    archive_root = tmp_path / "archive"

    with pytest.raises(PublisherIOError):
        promote_finalized_bundle_artifacts(
            bundle,
            staging_root=staging_root,
            archive_root=archive_root,
            snapshots={},
        )

    assert not archive_root.exists()


def test_manifest_rejects_symlinked_destination_parent(tmp_path: Path) -> None:
    staging_root = tmp_path / "stage"
    artifact = _artifact(staging_root, "hero.svg", b"hero")
    bundle = _bundle_with_artifacts((artifact,))
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (archive_root / DOMESTIC_EQUITY).symlink_to(outside, target_is_directory=True)

    with pytest.raises(PublisherIOError):
        promote_finalized_bundle_artifacts(
            bundle,
            staging_root=staging_root,
            archive_root=archive_root,
            snapshots={},
        )

    assert tuple(outside.rglob("*")) == ()
