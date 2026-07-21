"""Typed public-document lifecycle and sealed output contracts.

This module is the canonical publisher boundary introduced by u144.  It owns
only immutable in-process values and pure construction checks in this slice;
the phase algorithms and production switch land in later construction steps.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Final, Literal, Self, TypeVar

from investo.models.briefing import Briefing
from investo.models.bundle_context import BundleContext
from investo.models.coverage import SourceOutcome
from investo.models.facts import VerifiedFactBundle
from investo.models.items import NormalizedItem
from investo.models.market_anchor import MarketAnchor
from investo.models.public_notification import PublicNotificationSummary
from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
    SegmentCoverage,
)
from investo.publisher._public_document_policy import PUBLIC_BLOCK_KINDS, PublicBlockKind

PublicDocumentPhase = Literal["generated", "assembled", "projected", "repaired", "validated"]
PublicBlockDisposition = Literal["kept", "repaired", "replaced", "omitted"]
PublicProjectionPolicy = Literal[
    "reader_visible",
    "protected_diagnostics",
    "exact_disclaimer",
]
PublicRegionRequirement = Literal["always", "conditional", "optional"]
PublicSupplementKind = Literal["visual", "chart", "carryover"]
SegmentInputAbsence = Literal["generation_failed"]
PublicLimitationReason = Literal[
    "limited_coverage",
    "core_price_missing",
    "source_count_unavailable",
    "watchpoint_unavailable",
]
SegmentFinalizationState = Literal["finalized", "generation_absent", "trust_blocked"]

_PHASES: Final[tuple[PublicDocumentPhase, ...]] = (
    "generated",
    "assembled",
    "projected",
    "repaired",
    "validated",
)
_CANONICAL_SEGMENT_ORDER: Final[tuple[MarketSegment, ...]] = (
    DOMESTIC_EQUITY,
    US_EQUITY,
    CRYPTO,
)
_SUPPLEMENT_KINDS: Final[frozenset[str]] = frozenset({"visual", "chart", "carryover"})
_SEGMENTS: Final[frozenset[str]] = frozenset(_CANONICAL_SEGMENT_ORDER)
_PROJECTION_POLICIES: Final[frozenset[str]] = frozenset(
    {"reader_visible", "protected_diagnostics", "exact_disclaimer"}
)
_REGION_REQUIREMENTS: Final[frozenset[str]] = frozenset({"always", "conditional", "optional"})
_BLOCK_DISPOSITIONS: Final[frozenset[str]] = frozenset({"kept", "repaired", "replaced", "omitted"})
_LIMITATION_REASONS: Final[frozenset[str]] = frozenset(
    {
        "limited_coverage",
        "core_price_missing",
        "source_count_unavailable",
        "watchpoint_unavailable",
    }
)
_FINALIZATION_STATES: Final[frozenset[str]] = frozenset(
    {"finalized", "generation_absent", "trust_blocked"}
)
_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_ISSUE_CODE_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_K = TypeVar("_K")
_V = TypeVar("_V")


def _require_identifier(value: str, *, field_name: str) -> None:
    if _ID_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must use the bounded public-document identifier syntax")


def _require_unique(values: Sequence[str], *, field_name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must be unique")


def _canonical_issue_codes(issue_codes: Sequence[str]) -> tuple[str, ...]:
    canonical = tuple(sorted(set(issue_codes)))
    if any(_ISSUE_CODE_RE.fullmatch(code) is None for code in canonical):
        raise ValueError("issue_codes must contain bounded machine-readable codes")
    return canonical


def _freeze_mapping(value: Mapping[_K, _V]) -> Mapping[_K, _V]:
    return MappingProxyType(dict(value))


def _snapshot_item(item: NormalizedItem) -> NormalizedItem:
    """Copy the only mutable container inside a frozen NormalizedItem."""

    return item.model_copy(
        deep=True,
        update={"raw_metadata": MappingProxyType(dict(item.raw_metadata))},
    )


def _snapshot_bundle_context(context: BundleContext | None) -> BundleContext | None:
    """Defensively freeze BundleContext's two dict-backed fields."""

    if context is None:
        return None
    decision = context.daily_thesis_decision.model_copy(
        deep=True,
        update={
            "per_segment_lines": MappingProxyType(
                dict(context.daily_thesis_decision.per_segment_lines)
            )
        },
    )
    return context.model_copy(
        deep=True,
        update={
            "segments": MappingProxyType(dict(context.segments)),
            "daily_thesis_decision": decision,
        },
    )


@dataclass(frozen=True, slots=True)
class StagedArtifact:
    artifact_id: str
    segment: MarketSegment
    kind: PublicSupplementKind
    relative_public_path: PurePosixPath
    staged_path: Path
    sha256: str

    def __post_init__(self) -> None:
        _require_identifier(self.artifact_id, field_name="artifact_id")
        if self.segment not in _SEGMENTS:
            raise ValueError("segment must be a known market segment")
        if self.kind not in _SUPPLEMENT_KINDS:
            raise ValueError("kind must be visual, chart, or carryover")
        if not isinstance(self.relative_public_path, PurePosixPath):
            raise TypeError("relative_public_path must be PurePosixPath")
        if self.relative_public_path.is_absolute() or ".." in self.relative_public_path.parts:
            raise ValueError("relative_public_path must be relative and contain no '..'")
        if str(self.relative_public_path) in {"", "."}:
            raise ValueError("relative_public_path must identify a public file")
        if not isinstance(self.staged_path, Path):
            raise TypeError("staged_path must be Path")
        if _SHA256_RE.fullmatch(self.sha256) is None:
            raise ValueError("sha256 must be lowercase hexadecimal")


@dataclass(frozen=True, slots=True)
class PublicDocumentSupplement:
    supplement_id: str
    kind: PublicSupplementKind
    markdown: str
    stable_order: int
    artifact_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_identifier(self.supplement_id, field_name="supplement_id")
        if self.kind not in _SUPPLEMENT_KINDS:
            raise ValueError("kind must be visual, chart, or carryover")
        if not self.markdown.strip():
            raise ValueError("supplement markdown must not be blank")
        if "investo:block" in self.markdown:
            raise ValueError("supplement markdown must not contain investo:block markers")
        if self.stable_order < 0:
            raise ValueError("stable_order must be >= 0")
        artifact_ids = tuple(self.artifact_ids)
        _require_unique(artifact_ids, field_name="supplement artifact_ids")
        for artifact_id in artifact_ids:
            _require_identifier(artifact_id, field_name="artifact_id")
        object.__setattr__(self, "artifact_ids", artifact_ids)


@dataclass(frozen=True, slots=True)
class PublicDocumentContext:
    target_date: date
    expected_segments: tuple[MarketSegment, ...]
    input_absences: Mapping[MarketSegment, SegmentInputAbsence]
    anchors_by_segment: Mapping[MarketSegment, tuple[MarketAnchor, ...]]
    items_by_segment: Mapping[MarketSegment, tuple[NormalizedItem, ...]]
    coverage_by_segment: Mapping[MarketSegment, SegmentCoverage]
    source_outcomes: tuple[SourceOutcome, ...]
    bundle_context: BundleContext | None
    fact_bundle: VerifiedFactBundle
    entity_observed_at_utc: datetime
    supplements_by_segment: Mapping[MarketSegment, tuple[PublicDocumentSupplement, ...]] = field(
        default_factory=dict
    )
    staged_artifacts_by_segment: Mapping[MarketSegment, tuple[StagedArtifact, ...]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        expected = tuple(self.expected_segments)
        if not expected:
            raise ValueError("expected_segments must not be empty")
        if len(set(expected)) != len(expected):
            raise ValueError("expected_segments must not contain duplicates")
        canonical_positions = tuple(_CANONICAL_SEGMENT_ORDER.index(segment) for segment in expected)
        if canonical_positions != tuple(sorted(canonical_positions)):
            raise ValueError("expected_segments must follow canonical segment order")
        if self.entity_observed_at_utc.utcoffset() is None:
            raise ValueError("entity_observed_at_utc must be timezone-aware")
        if self.fact_bundle.target_date != self.target_date:
            raise ValueError("fact_bundle target_date must equal context target_date")

        expected_set = set(expected)
        absences = dict(self.input_absences)
        if not set(absences) <= expected_set:
            raise ValueError("input_absences contains an unexpected segment")
        if any(reason != "generation_failed" for reason in absences.values()):
            raise ValueError("input_absences contains an unsupported reason")
        generated = expected_set - set(absences)

        anchors = {segment: tuple(values) for segment, values in self.anchors_by_segment.items()}
        items = {
            segment: tuple(_snapshot_item(value) for value in values)
            for segment, values in self.items_by_segment.items()
        }
        coverage = dict(self.coverage_by_segment)
        supplements = {
            segment: tuple(values) for segment, values in self.supplements_by_segment.items()
        }
        artifacts = {
            segment: tuple(values) for segment, values in self.staged_artifacts_by_segment.items()
        }
        for field_name, mapping in (
            ("anchors_by_segment", anchors),
            ("items_by_segment", items),
            ("coverage_by_segment", coverage),
            ("supplements_by_segment", supplements),
            ("staged_artifacts_by_segment", artifacts),
        ):
            if not set(mapping) <= generated:
                raise ValueError(f"{field_name} contains an absent or unexpected segment")
        if set(coverage) != generated:
            raise ValueError(
                "coverage_by_segment must contain every generated segment exactly once"
            )
        if any(value.segment != segment for segment, value in coverage.items()):
            raise ValueError("coverage_by_segment key must match SegmentCoverage.segment")

        supplement_ids: list[str] = []
        artifact_by_id: dict[str, StagedArtifact] = {}
        public_paths: set[PurePosixPath] = set()
        for segment in expected:
            segment_supplements = supplements.get(segment, ())
            ordering = tuple(
                (value.stable_order, value.kind, value.supplement_id)
                for value in segment_supplements
            )
            if ordering != tuple(sorted(ordering)):
                raise ValueError("supplements must use stable (order, kind, id) ordering")
            order_kind = tuple((value.stable_order, value.kind) for value in segment_supplements)
            if len(set(order_kind)) != len(order_kind):
                raise ValueError("supplements must not duplicate (stable_order, kind)")
            supplement_ids.extend(value.supplement_id for value in segment_supplements)
            for artifact in artifacts.get(segment, ()):
                if artifact.segment != segment:
                    raise ValueError("staged artifact key must match artifact.segment")
                if artifact.artifact_id in artifact_by_id:
                    raise ValueError("artifact_id must be globally unique")
                if artifact.relative_public_path in public_paths:
                    raise ValueError("relative_public_path must be globally unique")
                artifact_by_id[artifact.artifact_id] = artifact
                public_paths.add(artifact.relative_public_path)
        _require_unique(supplement_ids, field_name="supplement_id")

        referenced_ids: list[str] = []
        for segment, segment_supplements in supplements.items():
            for supplement in segment_supplements:
                for artifact_id in supplement.artifact_ids:
                    referenced_artifact = artifact_by_id.get(artifact_id)
                    if referenced_artifact is None:
                        raise ValueError("supplement references an unknown staged artifact")
                    if (
                        referenced_artifact.segment != segment
                        or referenced_artifact.kind != supplement.kind
                    ):
                        raise ValueError("supplement artifact segment/kind must match")
                    referenced_ids.append(artifact_id)
        _require_unique(referenced_ids, field_name="supplement artifact references")
        if set(referenced_ids) != set(artifact_by_id):
            raise ValueError("every staged artifact must be referenced by one supplement")

        object.__setattr__(self, "expected_segments", expected)
        object.__setattr__(self, "input_absences", _freeze_mapping(absences))
        object.__setattr__(self, "anchors_by_segment", _freeze_mapping(anchors))
        object.__setattr__(self, "items_by_segment", _freeze_mapping(items))
        object.__setattr__(self, "coverage_by_segment", _freeze_mapping(coverage))
        object.__setattr__(self, "source_outcomes", tuple(self.source_outcomes))
        object.__setattr__(self, "bundle_context", _snapshot_bundle_context(self.bundle_context))
        object.__setattr__(self, "supplements_by_segment", _freeze_mapping(supplements))
        object.__setattr__(self, "staged_artifacts_by_segment", _freeze_mapping(artifacts))


@dataclass(frozen=True, slots=True)
class PublicDocumentRegion:
    region_id: str
    block: PublicBlockKind
    required: bool
    projection_policy: PublicProjectionPolicy
    start: int
    end: int
    content_start: int
    content_end: int

    def __post_init__(self) -> None:
        if not self.region_id:
            raise ValueError("region_id must not be empty")
        if self.block not in PUBLIC_BLOCK_KINDS:
            raise ValueError("block must be a known public block kind")
        if self.projection_policy not in _PROJECTION_POLICIES:
            raise ValueError("projection_policy is not supported")
        if not (0 <= self.start <= self.content_start <= self.content_end <= self.end):
            raise ValueError("region offsets must be ordered and non-negative")


@dataclass(frozen=True, slots=True)
class PublicRegionExpectation:
    target_date: date
    segment: MarketSegment
    segmented_mode: bool
    supplement_ids: tuple[str, ...]
    shared_macro_required: bool
    crypto_indicators_required: bool
    channel_anchors_required: bool
    daily_thesis_required: bool
    anchor_table_required: bool

    def __post_init__(self) -> None:
        if self.segment not in _SEGMENTS:
            raise ValueError("segment must be a known market segment")
        supplement_ids = tuple(self.supplement_ids)
        _require_unique(supplement_ids, field_name="supplement_ids")
        for supplement_id in supplement_ids:
            _require_identifier(supplement_id, field_name="supplement_id")
        object.__setattr__(self, "supplement_ids", supplement_ids)


@dataclass(frozen=True, slots=True)
class PublicDocumentLayout:
    markdown: str
    regions: tuple[PublicDocumentRegion, ...]
    expectation: PublicRegionExpectation

    def __post_init__(self) -> None:
        if not self.markdown:
            raise ValueError("layout markdown must not be empty")
        regions = tuple(self.regions)
        if tuple(sorted(regions, key=lambda region: (region.start, region.end))) != regions:
            raise ValueError("layout regions must use source order")
        region_ids = tuple(region.region_id for region in regions)
        _require_unique(region_ids, field_name="region_id")
        prior_end = 0
        for region in regions:
            if region.end > len(self.markdown):
                raise ValueError("region offsets exceed markdown length")
            if region.start < prior_end:
                raise ValueError("layout regions must not overlap")
            prior_end = region.end
        object.__setattr__(self, "regions", regions)


@dataclass(frozen=True, slots=True)
class RegionSpec:
    id_pattern: str
    block: PublicBlockKind
    start_rule: str
    end_rule: str
    requirement: PublicRegionRequirement
    projection_policy: PublicProjectionPolicy
    repeatable: bool = False

    def __post_init__(self) -> None:
        if not self.id_pattern or not self.start_rule or not self.end_rule:
            raise ValueError("region spec rules must not be empty")
        if self.block not in PUBLIC_BLOCK_KINDS:
            raise ValueError("block must be a known public block kind")
        if self.requirement not in _REGION_REQUIREMENTS:
            raise ValueError("region requirement is not supported")
        if self.projection_policy not in _PROJECTION_POLICIES:
            raise ValueError("projection_policy is not supported")


@dataclass(frozen=True, slots=True)
class PublicBlockOutcome:
    region_id: str
    block: PublicBlockKind
    disposition: PublicBlockDisposition
    issue_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.region_id:
            raise ValueError("region_id must not be empty")
        if self.block not in PUBLIC_BLOCK_KINDS:
            raise ValueError("block must be a known public block kind")
        if self.disposition not in _BLOCK_DISPOSITIONS:
            raise ValueError("block disposition is not supported")
        object.__setattr__(self, "issue_codes", _canonical_issue_codes(self.issue_codes))


@dataclass(frozen=True, slots=True, init=False)
class PublicDocumentDraft:
    segment: MarketSegment
    target_date: date
    source_briefing: Briefing
    layout: PublicDocumentLayout
    phase: PublicDocumentPhase
    limitation_reasons: tuple[PublicLimitationReason, ...] = ()
    block_outcomes: tuple[PublicBlockOutcome, ...] = ()
    notification_summary: PublicNotificationSummary | None = None
    _validation_witness: object | None = field(default=None, repr=False, compare=False)

    def __new__(cls) -> Self:
        raise TypeError("PublicDocumentDraft is created only by lifecycle transitions")


_VALIDATED_DRAFT_WITNESS: Final[object] = object()


def _construct_draft(
    *,
    segment: MarketSegment,
    target_date: date,
    source_briefing: Briefing,
    layout: PublicDocumentLayout,
    phase: PublicDocumentPhase,
    limitation_reasons: Sequence[PublicLimitationReason] = (),
    block_outcomes: Sequence[PublicBlockOutcome] = (),
    notification_summary: PublicNotificationSummary | None = None,
    validation_witness: object | None = None,
) -> PublicDocumentDraft:
    if phase not in _PHASES:
        raise ValueError("unknown public-document phase")
    if source_briefing.target_date != target_date:
        raise ValueError("source briefing target_date must match draft")
    if layout.expectation.segment != segment:
        raise ValueError("layout expectation segment must match draft")
    if layout.expectation.target_date != target_date:
        raise ValueError("layout expectation target_date must match draft")
    reasons = tuple(dict.fromkeys(limitation_reasons))
    if any(reason not in _LIMITATION_REASONS for reason in reasons):
        raise ValueError("limitation_reasons contains an unsupported reason")
    outcomes = tuple(block_outcomes)
    if len({outcome.region_id for outcome in outcomes}) != len(outcomes):
        raise ValueError("block_outcomes must contain at most one outcome per region")
    if phase == "validated":
        if validation_witness is not _VALIDATED_DRAFT_WITNESS:
            raise ValueError("validated draft requires the terminal-validation witness")
        if notification_summary is None:
            raise ValueError("validated draft requires notification_summary")
        if (
            notification_summary.segment != segment
            or notification_summary.target_date != target_date
        ):
            raise ValueError("notification_summary identity must match draft")
    elif notification_summary is not None or validation_witness is not None:
        raise ValueError("notification summary/witness is only legal in validated phase")

    draft = object.__new__(PublicDocumentDraft)
    object.__setattr__(draft, "segment", segment)
    object.__setattr__(draft, "target_date", target_date)
    object.__setattr__(draft, "source_briefing", source_briefing)
    object.__setattr__(draft, "layout", layout)
    object.__setattr__(draft, "phase", phase)
    object.__setattr__(draft, "limitation_reasons", reasons)
    object.__setattr__(draft, "block_outcomes", outcomes)
    object.__setattr__(draft, "notification_summary", notification_summary)
    object.__setattr__(draft, "_validation_witness", validation_witness)
    return draft


def _new_generated_draft(
    briefing: Briefing,
    *,
    segment: MarketSegment,
    layout: PublicDocumentLayout,
) -> PublicDocumentDraft:
    if layout.markdown != briefing.rendered_markdown:
        raise ValueError("generated draft layout must equal generated briefing markdown")
    return _construct_draft(
        segment=segment,
        target_date=briefing.target_date,
        source_briefing=briefing,
        layout=layout,
        phase="generated",
    )


def _transition_draft(
    draft: PublicDocumentDraft,
    *,
    next_phase: PublicDocumentPhase,
    layout: PublicDocumentLayout | None = None,
    limitation_reasons: Sequence[PublicLimitationReason] | None = None,
    block_outcomes: Sequence[PublicBlockOutcome] | None = None,
    notification_summary: PublicNotificationSummary | None = None,
) -> PublicDocumentDraft:
    current_index = _PHASES.index(draft.phase)
    if current_index + 1 >= len(_PHASES) or _PHASES[current_index + 1] != next_phase:
        raise ValueError(f"invalid public-document phase transition: {draft.phase}->{next_phase}")
    witness = _VALIDATED_DRAFT_WITNESS if next_phase == "validated" else None
    return _construct_draft(
        segment=draft.segment,
        target_date=draft.target_date,
        source_briefing=draft.source_briefing,
        layout=draft.layout if layout is None else layout,
        phase=next_phase,
        limitation_reasons=(
            draft.limitation_reasons if limitation_reasons is None else limitation_reasons
        ),
        block_outcomes=draft.block_outcomes if block_outcomes is None else block_outcomes,
        notification_summary=notification_summary,
        validation_witness=witness,
    )


_DraftFactory = Callable[[Briefing, MarketSegment, PublicDocumentContext], PublicDocumentDraft]
_DraftPhaseHandler = Callable[[PublicDocumentDraft, PublicDocumentContext], PublicDocumentDraft]
_ArtifactIdSelector = Callable[[PublicDocumentDraft, PublicDocumentContext], Sequence[str]]


@dataclass(frozen=True, slots=True)
class _FinalizationPhaseHandlers:
    """Pure collaborators used while the concrete phase algorithms land."""

    assemble: _DraftPhaseHandler
    project: _DraftPhaseHandler
    repair: _DraftPhaseHandler
    validate: _DraftPhaseHandler
    artifact_ids: _ArtifactIdSelector


class _SegmentTrustBlockedError(Exception):
    """Internal typed signal for one non-degradable segment finding."""

    def __init__(
        self,
        *,
        phase: PublicDocumentPhase,
        issue_codes: Sequence[str],
    ) -> None:
        self.phase = phase
        self.issue_codes = _canonical_issue_codes(issue_codes)
        codes = ",".join(self.issue_codes) if self.issue_codes else "unspecified"
        super().__init__(f"segment trust blocked: phase={phase} codes={codes}")


class _FinalizationInvariantError(ValueError):
    """Internal bounded programmer-invariant failure converted to E8."""

    def __init__(self, *, phase: str, issue_code: str) -> None:
        self.phase = phase
        self.issue_code = issue_code
        super().__init__(f"finalization invariant failed: phase={phase} code={issue_code}")


def _assert_phase_result(
    *,
    previous: PublicDocumentDraft,
    result: PublicDocumentDraft,
    expected_phase: PublicDocumentPhase,
) -> None:
    if result.phase != expected_phase:
        raise _FinalizationInvariantError(
            phase=expected_phase,
            issue_code="invariant.phase_transition",
        )
    if result.segment != previous.segment or result.target_date != previous.target_date:
        raise _FinalizationInvariantError(
            phase=expected_phase,
            issue_code="invariant.segment_identity",
        )
    if result.source_briefing is not previous.source_briefing:
        raise _FinalizationInvariantError(
            phase=expected_phase,
            issue_code="invariant.briefing_identity",
        )


def _finalize_segment_skeleton(
    draft: PublicDocumentDraft,
    *,
    context: PublicDocumentContext,
    handlers: _FinalizationPhaseHandlers,
) -> FinalizedPublicDocument:
    """Run one generated draft through the declared pure phase order."""

    if draft.phase != "generated":
        raise _FinalizationInvariantError(
            phase="generated",
            issue_code="invariant.segment_start_phase",
        )
    if draft.target_date != context.target_date or draft.segment not in context.expected_segments:
        raise _FinalizationInvariantError(
            phase="generated",
            issue_code="invariant.segment_identity",
        )
    if draft.segment in context.input_absences:
        raise _FinalizationInvariantError(
            phase="generated",
            issue_code="invariant.absence_conflict",
        )

    current = draft
    phase_handlers: tuple[tuple[PublicDocumentPhase, _DraftPhaseHandler], ...] = (
        ("assembled", handlers.assemble),
        ("projected", handlers.project),
        ("repaired", handlers.repair),
        ("validated", handlers.validate),
    )
    for expected_phase, handler in phase_handlers:
        result = handler(current, context)
        _assert_phase_result(
            previous=current,
            result=result,
            expected_phase=expected_phase,
        )
        current = result

    artifact_ids = tuple(handlers.artifact_ids(current, context))
    known_artifacts = {
        artifact.artifact_id
        for artifact in context.staged_artifacts_by_segment.get(draft.segment, ())
    }
    if not set(artifact_ids) <= known_artifacts:
        raise _FinalizationInvariantError(
            phase="validated",
            issue_code="invariant.artifact_selection",
        )
    return _seal_document(current, staged_artifact_ids=artifact_ids)


def _finalize_bundle_skeleton(
    briefings: Mapping[MarketSegment, Briefing],
    *,
    context: PublicDocumentContext,
    draft_factory: _DraftFactory,
    handlers: _FinalizationPhaseHandlers,
) -> FinalizedPublicBundle:
    """Pure single-pass bundle coordinator used before the production switch.

    The active-survivor fixed point and concrete phase collaborators land in
    later checklist items.  This skeleton already pins input identity,
    generation-absence outcomes, segment trust blocks, zero-survivor E8, and
    E1-derived promotion manifests.
    """

    expected_generated = set(context.expected_segments) - set(context.input_absences)
    if set(briefings) != expected_generated:
        raise PublicDocumentFinalizationError(
            target_date=context.target_date,
            segment=None,
            phase="input",
            issue_codes=("input.briefing_keys",),
        )
    if any(briefing.target_date != context.target_date for briefing in briefings.values()):
        raise PublicDocumentFinalizationError(
            target_date=context.target_date,
            segment=None,
            phase="input",
            issue_codes=("input.target_date",),
        )

    documents: list[FinalizedPublicDocument] = []
    outcomes: list[SegmentFinalizationOutcome] = []
    for segment in context.expected_segments:
        if segment in context.input_absences:
            outcomes.append(
                SegmentFinalizationOutcome(
                    segment=segment,
                    state="generation_absent",
                    issue_codes=("generation.failed",),
                )
            )
            continue
        briefing = briefings[segment]
        try:
            draft = draft_factory(briefing, segment, context)
            if (
                draft.phase != "generated"
                or draft.segment != segment
                or draft.target_date != context.target_date
                or draft.source_briefing is not briefing
            ):
                raise _FinalizationInvariantError(
                    phase="generated",
                    issue_code="invariant.draft_factory",
                )
            document = _finalize_segment_skeleton(
                draft,
                context=context,
                handlers=handlers,
            )
        except _SegmentTrustBlockedError as exc:
            outcomes.append(
                SegmentFinalizationOutcome(
                    segment=segment,
                    state="trust_blocked",
                    issue_codes=exc.issue_codes,
                )
            )
            continue
        except _FinalizationInvariantError as exc:
            raise PublicDocumentFinalizationError(
                target_date=context.target_date,
                segment=segment,
                phase=exc.phase,
                issue_codes=(exc.issue_code,),
                cause=exc,
            ) from exc
        except ValueError as exc:
            raise PublicDocumentFinalizationError(
                target_date=context.target_date,
                segment=segment,
                phase="bundle",
                issue_codes=("invariant.phase_handler",),
                cause=exc,
            ) from exc
        except Exception as exc:
            raise PublicDocumentFinalizationError(
                target_date=context.target_date,
                segment=segment,
                phase="bundle",
                issue_codes=("invariant.phase_handler_exception",),
                cause=exc,
            ) from exc
        documents.append(document)
        outcomes.append(SegmentFinalizationOutcome(segment=segment, state="finalized"))

    if not documents:
        all_codes = (
            *(code for outcome in outcomes for code in outcome.issue_codes),
            "bundle.zero_survivors",
        )
        raise PublicDocumentFinalizationError(
            target_date=context.target_date,
            segment=None,
            phase="bundle",
            issue_codes=all_codes,
        )
    try:
        return _build_finalized_bundle(
            context,
            documents=documents,
            segment_outcomes=outcomes,
        )
    except ValueError as exc:
        raise PublicDocumentFinalizationError(
            target_date=context.target_date,
            segment=None,
            phase="bundle",
            issue_codes=("invariant.bundle_factory",),
            cause=exc,
        ) from exc


@dataclass(frozen=True, slots=True, init=False)
class FinalizedPublicDocument:
    segment: MarketSegment
    target_date: date
    briefing: Briefing
    markdown_sha256: str
    staged_artifact_ids: tuple[str, ...]
    notification_summary: PublicNotificationSummary
    block_outcomes: tuple[PublicBlockOutcome, ...]
    warnings: tuple[str, ...] = ()

    def __new__(cls) -> Self:
        raise TypeError("FinalizedPublicDocument is created only by the seal factory")


def _seal_document(
    draft: PublicDocumentDraft,
    *,
    staged_artifact_ids: Sequence[str] = (),
    warnings: Sequence[str] = (),
) -> FinalizedPublicDocument:
    """Construct E5 from a validated draft; never performs I/O."""

    if (
        draft.phase != "validated"
        or draft.notification_summary is None
        or draft._validation_witness is not _VALIDATED_DRAFT_WITNESS
    ):
        raise ValueError("only a validated draft can be sealed")
    artifact_ids = tuple(staged_artifact_ids)
    _require_unique(artifact_ids, field_name="staged_artifact_ids")
    for artifact_id in artifact_ids:
        _require_identifier(artifact_id, field_name="artifact_id")
    canonical_warnings = tuple(dict.fromkeys(warnings))
    final_briefing = draft.source_briefing.model_copy(
        update={"rendered_markdown": draft.layout.markdown}
    )
    digest = sha256(draft.layout.markdown.encode("utf-8")).hexdigest()
    sealed = object.__new__(FinalizedPublicDocument)
    object.__setattr__(sealed, "segment", draft.segment)
    object.__setattr__(sealed, "target_date", draft.target_date)
    object.__setattr__(sealed, "briefing", final_briefing)
    object.__setattr__(sealed, "markdown_sha256", digest)
    object.__setattr__(sealed, "staged_artifact_ids", artifact_ids)
    object.__setattr__(sealed, "notification_summary", draft.notification_summary)
    object.__setattr__(sealed, "block_outcomes", draft.block_outcomes)
    object.__setattr__(sealed, "warnings", canonical_warnings)
    return sealed


@dataclass(frozen=True, slots=True)
class SegmentFinalizationOutcome:
    segment: MarketSegment
    state: SegmentFinalizationState
    issue_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.segment not in _SEGMENTS:
            raise ValueError("segment must be a known market segment")
        if self.state not in _FINALIZATION_STATES:
            raise ValueError("segment finalization state is not supported")
        object.__setattr__(self, "issue_codes", _canonical_issue_codes(self.issue_codes))


@dataclass(frozen=True, slots=True, init=False)
class FinalizedPublicBundle:
    target_date: date
    documents: tuple[FinalizedPublicDocument, ...]
    expected_segments: tuple[MarketSegment, ...]
    segment_outcomes: tuple[SegmentFinalizationOutcome, ...]
    promotion_manifest: tuple[StagedArtifact, ...] = ()

    def __new__(cls) -> Self:
        raise TypeError("FinalizedPublicBundle is created only by the bundle factory")


def _build_finalized_bundle(
    context: PublicDocumentContext,
    *,
    documents: Sequence[FinalizedPublicDocument],
    segment_outcomes: Sequence[SegmentFinalizationOutcome],
) -> FinalizedPublicBundle:
    canonical_documents = tuple(documents)
    outcomes = tuple(segment_outcomes)
    expected = context.expected_segments
    if not canonical_documents:
        raise ValueError("finalized bundle must contain at least one document")
    if tuple(outcome.segment for outcome in outcomes) != expected:
        raise ValueError("segment_outcomes must cover expected_segments in order")
    for outcome in outcomes:
        known_absence = outcome.segment in context.input_absences
        if known_absence != (outcome.state == "generation_absent"):
            raise ValueError("generation_absent outcomes must exactly match E1 input_absences")
    finalized_segments = tuple(
        outcome.segment for outcome in outcomes if outcome.state == "finalized"
    )
    if tuple(document.segment for document in canonical_documents) != finalized_segments:
        raise ValueError("documents must match finalized outcomes in expected order")
    if any(document.target_date != context.target_date for document in canonical_documents):
        raise ValueError("all finalized documents must share context target_date")

    artifact_by_id = {
        artifact.artifact_id: artifact
        for segment in expected
        for artifact in context.staged_artifacts_by_segment.get(segment, ())
    }
    manifest: list[StagedArtifact] = []
    for document in canonical_documents:
        for artifact_id in document.staged_artifact_ids:
            artifact = artifact_by_id.get(artifact_id)
            if artifact is None or artifact.segment != document.segment:
                raise ValueError("sealed document references an unknown E1 staged artifact")
            manifest.append(artifact)
    _require_unique(
        tuple(artifact.artifact_id for artifact in manifest),
        field_name="promotion_manifest artifact IDs",
    )

    bundle = object.__new__(FinalizedPublicBundle)
    object.__setattr__(bundle, "target_date", context.target_date)
    object.__setattr__(bundle, "documents", canonical_documents)
    object.__setattr__(bundle, "expected_segments", expected)
    object.__setattr__(bundle, "segment_outcomes", outcomes)
    object.__setattr__(bundle, "promotion_manifest", tuple(manifest))
    return bundle


class PublicDocumentFinalizationError(Exception):
    """Bounded, R13-safe error for finalization contract failures."""

    def __init__(
        self,
        *,
        target_date: date,
        segment: MarketSegment | None,
        phase: str,
        issue_codes: Sequence[str],
        cause: Exception | None = None,
    ) -> None:
        if not phase or len(phase) > 64 or re.fullmatch(r"[a-z0-9._-]+", phase) is None:
            raise ValueError("phase must be a bounded machine-readable value")
        self.target_date = target_date
        self.segment = segment
        self.phase = phase
        self.issue_codes = _canonical_issue_codes(issue_codes)
        self.cause = cause
        segment_label = segment if segment is not None else "bundle"
        codes = ",".join(self.issue_codes) if self.issue_codes else "unspecified"
        super().__init__(
            f"public document finalization failed: date={target_date.isoformat()} "
            f"segment={segment_label} phase={phase} codes={codes}"
        )


__all__ = [
    "FinalizedPublicBundle",
    "FinalizedPublicDocument",
]
