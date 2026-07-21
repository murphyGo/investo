"""Typed public-document lifecycle and sealed output contracts.

This module is the canonical publisher boundary introduced by u144.  It owns
only immutable in-process values and pure construction checks in this slice;
the phase algorithms and production switch land in later construction steps.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from hashlib import sha256
from itertools import pairwise
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Final, Literal, Self, TypeVar
from unicodedata import name as unicode_name

from investo._internal.disclaimer import ensure_canonical_disclaimer
from investo._internal.summary_quality import repair_first_viewport_summary
from investo._internal.surface_quality import find_surface_quality_issues
from investo.models.briefing import Briefing
from investo.models.bundle_context import BundleContext
from investo.models.coverage import SourceOutcome
from investo.models.facts import VerifiedFactBundle
from investo.models.items import NormalizedItem
from investo.models.market_anchor import MarketAnchor
from investo.models.public_artifact import PublicArtifactKind, StagedArtifact
from investo.models.public_notification import PublicNotificationSummary
from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    SEGMENT_LABELS,
    US_EQUITY,
    MarketSegment,
    SegmentCoverage,
)
from investo.publisher._public_document_policy import PUBLIC_BLOCK_KINDS, PublicBlockKind
from investo.publisher.errors import SurfaceQualityError
from investo.publisher.evidence_accounting import count_rendered_evidence, render_body_used_count
from investo.publisher.reader_format import emit_first_viewport_disclaimer, project_public_markdown
from investo.publisher.segment_reader_format import apply_reader_format_to_segments
from investo.publisher.watchpoint_matrix import WatchpointRenderResult

PublicDocumentPhase = Literal["generated", "assembled", "projected", "repaired", "validated"]
PublicBlockDisposition = Literal["kept", "repaired", "replaced", "omitted"]
PublicProjectionPolicy = Literal[
    "reader_visible",
    "protected_diagnostics",
    "exact_disclaimer",
]
PublicRegionRequirement = Literal["always", "conditional", "optional"]
PublicSupplementKind = PublicArtifactKind
SegmentInputAbsence = Literal["generation_failed"]
PublicLimitationReason = Literal[
    "limited_coverage",
    "core_price_missing",
    "source_count_unavailable",
    "watchpoint_unavailable",
]
SegmentFinalizationState = Literal["finalized", "generation_absent", "trust_blocked"]
PublicNotificationSummaryIssueCode = Literal[
    "summary.missing_conclusion",
    "summary.invalid_conclusion",
    "summary.invalid_coverage_label",
    "summary.invalid_watchlist",
]

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
_NOTIFICATION_SUMMARY_ISSUE_CODES: Final[frozenset[str]] = frozenset(
    {
        "summary.missing_conclusion",
        "summary.invalid_conclusion",
        "summary.invalid_coverage_label",
        "summary.invalid_watchlist",
    }
)
_FINALIZATION_STATES: Final[frozenset[str]] = frozenset(
    {"finalized", "generation_absent", "trust_blocked"}
)
_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_ISSUE_CODE_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_MARKER_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^<!-- investo:block (chart|visual|carryover):([a-z0-9][a-z0-9._-]{0,127}) -->$"
)
_MARKER_CLOSE_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^<!-- /investo:block (chart|visual|carryover):([a-z0-9][a-z0-9._-]{0,127}) -->$"
)
_SECTION_HEADINGS: Final[tuple[str, ...]] = (
    "## ① 요약",
    "## ② 전일 핵심 이슈",
    "## ③ 섹터/수급 동향",
    "## ④ 지표·이벤트",
    "## ⑤ 주요 종목",
)
_WATCHPOINT_HEADING: Final[str] = "## ⑥ 오늘의 관전 포인트"
_CANONICAL_DISCLAIMER_HEADING: Final[str] = "## ⑦ 면책조항"
_DIAGNOSTICS_OPEN: Final[str] = "<details><summary>수집/품질 진단</summary>"
_DIAGNOSTICS_CLOSE: Final[str] = "</details>"
_SHARED_MACRO_HEADING: Final[str] = "## ⓪ 오늘의 매크로"
_CRYPTO_INDICATOR_HEADING: Final[str] = "## ⓪-A 크립토 지표 (UTC 24h 스냅샷)"
_CHANNEL_ANCHOR_HEADING: Final[str] = "## ⓪-B 채널 기준선"
_CAUSE_PREFIX: Final[str] = "> **크로스마켓 연결 고리**:"
_THESIS_PREFIX: Final[str] = "> **오늘의 큰 그림:**"
_NAVIGATION_PREFIX: Final[str] = "**세그먼트**:"
_NAVIGATION_LINE_RE: Final[re.Pattern[str]] = re.compile(
    rf"^{re.escape(_NAVIGATION_PREFIX)} .*$",
    re.MULTILINE,
)
_SHORT_DISCLAIMER_EQUITY: Final[str] = "> 정보 제공용 자동 시황이며 매매 권유가 아닙니다."
_SHORT_DISCLAIMER_CRYPTO: Final[str] = (
    "> 정보 제공용 자동 시황이며 가상자산 매매 권유가 아닙니다. "
    "가상자산은 가격 변동성이 매우 큽니다."
)
_EQUITY_ANCHOR_HEADER: Final[str] = "| 종목 | 종가 | 변동 | 비고 |"
_CRYPTO_ANCHOR_HEADER: Final[str] = "| 종목 | 스냅샷(UTC 24h) | 구간 변동 | 비고 |"
_ANCHOR_DELIMITER: Final[str] = "|------|------|------|------|"
_K = TypeVar("_K")
_V = TypeVar("_V")
_surface_logger = logging.getLogger("investo.publisher.segment_reader_format")


def _canonical_active_segments(
    active_segments: Sequence[MarketSegment],
) -> tuple[MarketSegment, ...]:
    active = tuple(active_segments)
    if len(set(active)) != len(active) or any(segment not in _SEGMENTS for segment in active):
        raise ValueError("active_segments must contain unique known segments")
    canonical = tuple(segment for segment in _CANONICAL_SEGMENT_ORDER if segment in active)
    if active != canonical:
        raise ValueError("active_segments must use canonical segment order")
    if not active:
        raise ValueError("active_segments must not be empty")
    return active


def _active_segment_nav_line(
    target_date: date,
    *,
    current_segment: MarketSegment,
    active_segments: Sequence[MarketSegment],
) -> str:
    active = set(_canonical_active_segments(active_segments))
    if current_segment not in active:
        raise ValueError("current_segment must be active")
    filename = f"{target_date.isoformat()}.md"
    parts: list[str] = []
    for segment in _CANONICAL_SEGMENT_ORDER:
        label = SEGMENT_LABELS[segment]
        if segment not in active:
            parts.append(f"{label}(미발행)")
            continue
        href = (
            filename
            if segment == current_segment
            else f"../../../{segment}/{target_date.year}/{target_date.month:02d}/{filename}"
        )
        parts.append(f"[{label}]({href})")
    return f"{_NAVIGATION_PREFIX} {' | '.join(parts)}"


def _assemble_phase_one_presentation_briefings(
    briefings: Mapping[MarketSegment, Briefing],
    *,
    target_date: date,
    active_segments: Sequence[MarketSegment],
) -> dict[MarketSegment, Briefing]:
    """Run nav/disclaimer/summary text producers in phase 1 (pure)."""

    active = _canonical_active_segments(active_segments)
    if set(briefings) != set(active):
        raise ValueError("briefing keys must exactly match active_segments")
    assembled: dict[MarketSegment, Briefing] = {}
    for segment in active:
        briefing = briefings[segment]
        if briefing.target_date != target_date:
            raise ValueError("briefing target_date must match assembly target_date")
        markdown = _NAVIGATION_LINE_RE.sub(
            _active_segment_nav_line(
                target_date,
                current_segment=segment,
                active_segments=active,
            ),
            briefing.rendered_markdown,
            count=1,
        )
        markdown = emit_first_viewport_disclaimer(markdown, segment)
        markdown = ensure_canonical_disclaimer(markdown, segment)
        markdown = repair_first_viewport_summary(markdown)
        assembled[segment] = (
            briefing
            if markdown == briefing.rendered_markdown
            else briefing.model_copy(update={"rendered_markdown": markdown})
        )
    return assembled


def _assemble_phase_one_body_evidence(
    briefing: Briefing,
    *,
    segment: MarketSegment,
    source_outcomes: Sequence[SourceOutcome],
    verified_facts: Sequence[object],
) -> Briefing:
    """Render the u123 body-used producer inside phase 1 (pure)."""

    counts = count_rendered_evidence(
        briefing.rendered_markdown,
        segment=segment,
        source_outcomes=tuple(source_outcomes),
        verified_facts=tuple(verified_facts),
    )
    markdown = render_body_used_count(briefing.rendered_markdown, counts)
    return (
        briefing
        if markdown == briefing.rendered_markdown
        else briefing.model_copy(update={"rendered_markdown": markdown})
    )


def _assemble_phase_one_reader_briefings(
    segment_briefings: dict[MarketSegment, Briefing],
    *,
    anchors_by_segment: Mapping[MarketSegment, Sequence[MarketAnchor]],
    bundle_context: BundleContext | None = None,
    items_by_segment: Mapping[MarketSegment, Sequence[NormalizedItem]] | None = None,
    _watchpoint_result_observer: Callable[[MarketSegment, WatchpointRenderResult], None]
    | None = None,
) -> dict[MarketSegment, Briefing]:
    """Run the legacy reader transform as a phase-1 internal collaborator.

    Surface repair remains a text-producing assembly pass. The old transform
    module no longer claims terminal validation ownership; this compatibility
    boundary preserves the current fail-close behavior until the read-only
    terminal validator lands in the finalized lifecycle.
    """

    assembled = apply_reader_format_to_segments(
        segment_briefings,
        anchors_by_segment=anchors_by_segment,
        bundle_context=bundle_context,
        items_by_segment=items_by_segment,
        _surface_repair_observer=_enforce_phase_one_surface_compatibility,
        _watchpoint_result_observer=_watchpoint_result_observer,
    )
    return assembled


def _enforce_phase_one_surface_compatibility(
    segment: MarketSegment,
    before_repair: str,
    after_repair: str,
) -> None:
    """Preserve the legacy per-segment fail-close order until Step 4."""

    issues_before = find_surface_quality_issues(before_repair)
    issues_after = find_surface_quality_issues(after_repair)
    for issue in (*issues_before, *issues_after):
        if issue.severity == "warn":
            _surface_logger.warning(
                "surface_quality.%s segment=%s",
                issue.code,
                segment,
                extra={
                    "segment": segment,
                    "code": issue.code,
                    "region": issue.region,
                    "evidence_len": len(issue.evidence),
                },
            )
    blocking_issues = tuple(issue for issue in issues_after if issue.severity == "block")
    if blocking_issues:
        raise SurfaceQualityError(segment=segment, issues=blocking_issues)


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
        boolean_fields = (
            self.segmented_mode,
            self.shared_macro_required,
            self.crypto_indicators_required,
            self.channel_anchors_required,
            self.daily_thesis_required,
            self.anchor_table_required,
        )
        if any(type(value) is not bool for value in boolean_fields):
            raise TypeError("public region expectation flags must be bool")
        if self.crypto_indicators_required and self.segment != CRYPTO:
            raise ValueError("crypto indicators are forbidden on non-crypto segments")
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

    def replace_region_body(
        self,
        region_id: str,
        replacement_body: str,
    ) -> PublicDocumentLayout:
        """Replace one owned body by its indexed offsets, then fully reindex."""

        region = _require_layout_region(self, region_id)
        if not isinstance(replacement_body, str):
            raise TypeError("replacement_body must be str")
        markdown = (
            self.markdown[: region.content_start]
            + replacement_body
            + self.markdown[region.content_end :]
        )
        reindexed = type(self).reindex(markdown, expectation=self.expectation)
        _require_stable_region_ids(
            before=self.regions,
            after=reindexed.regions,
            operation="replacement",
        )
        return reindexed

    def omit_optional_region(self, region_id: str) -> PublicDocumentLayout:
        """Omit one degradable region without weakening structural ownership."""

        region = _require_layout_region(self, region_id)
        if region.block in {"visual", "chart", "carryover"}:
            if region.content_start == region.content_end:
                raise ValueError("marker-backed region is already omitted")
            return self.replace_region_body(region_id, "")
        if region.block != "cause_map" or region.required:
            raise ValueError("region is not an optional omittable block")
        markdown = self.markdown[: region.start] + self.markdown[region.end :]
        reindexed = type(self).reindex(markdown, expectation=self.expectation)
        expected_ids = tuple(
            existing.region_id
            for existing in self.regions
            if existing.region_id != region_id and existing.block != "first_viewport"
        )
        actual_ids = tuple(
            existing.region_id
            for existing in reindexed.regions
            if existing.block != "first_viewport"
        )
        if actual_ids != expected_ids:
            raise ValueError("region IDs changed outside the omitted optional block")
        return reindexed

    @classmethod
    def reindex(
        cls,
        markdown: str,
        *,
        expectation: PublicRegionExpectation,
    ) -> PublicDocumentLayout:
        """Build the exhaustive FD region partition for one active pass."""

        return _reindex_public_document(markdown, expectation=expectation)


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


_REGION_SPECS: Final[tuple[RegionSpec, ...]] = (
    RegionSpec(
        "disclaimer:canonical",
        "disclaimer",
        f"line exactly {_CANONICAL_DISCLAIMER_HEADING!r}",
        "EOF",
        "always",
        "exact_disclaimer",
    ),
    RegionSpec(
        "diagnostics:quality",
        "diagnostics",
        f"line exactly {_DIAGNOSTICS_OPEN!r}",
        f"matching {_DIAGNOSTICS_CLOSE!r} inclusive",
        "always",
        "protected_diagnostics",
    ),
    RegionSpec(
        "chart:{supplement_id}",
        "chart",
        "exact investo:block chart:{supplement_id} open marker",
        "matching exact close marker inclusive",
        "conditional",
        "reader_visible",
        True,
    ),
    RegionSpec(
        "visual:{supplement_id}",
        "visual",
        "exact investo:block visual:{supplement_id} open marker",
        "matching exact close marker inclusive",
        "conditional",
        "reader_visible",
        True,
    ),
    RegionSpec(
        "carryover:{supplement_id}",
        "carryover",
        "exact investo:block carryover:{supplement_id} open marker",
        "matching exact close marker inclusive",
        "conditional",
        "reader_visible",
        True,
    ),
    RegionSpec(
        "macro:shared",
        "shared_macro",
        f"line exactly {_SHARED_MACRO_HEADING!r}",
        "next H2 or EOF",
        "conditional",
        "reader_visible",
    ),
    RegionSpec(
        "indicator:crypto",
        "crypto_indicators",
        f"line exactly {_CRYPTO_INDICATOR_HEADING!r}",
        "next H2 or EOF",
        "conditional",
        "reader_visible",
    ),
    RegionSpec(
        "anchor:channel",
        "channel_anchors",
        f"line exactly {_CHANNEL_ANCHOR_HEADING!r}",
        "next H2 or EOF",
        "conditional",
        "reader_visible",
    ),
    RegionSpec(
        "cause:cross_market",
        "cause_map",
        f"line prefix {_CAUSE_PREFIX!r}",
        "newline",
        "optional",
        "reader_visible",
    ),
    RegionSpec(
        "thesis:daily",
        "daily_thesis",
        f"line prefix {_THESIS_PREFIX!r}",
        "newline",
        "conditional",
        "reader_visible",
    ),
    RegionSpec(
        "navigation:segments",
        "navigation",
        f"line prefix {_NAVIGATION_PREFIX!r}",
        "newline",
        "conditional",
        "reader_visible",
    ),
    RegionSpec(
        "disclaimer:short",
        "disclaimer",
        "segment-exact short disclaimer line",
        "newline",
        "always",
        "exact_disclaimer",
    ),
    RegionSpec(
        "anchor:market",
        "anchor_table",
        "segment-exact anchor table header line",
        "first non-table line after exact delimiter",
        "conditional",
        "reader_visible",
    ),
    RegionSpec(
        "watchpoints:section[`:continuation:{ordinal}`]",
        "watchpoints",
        f"primary: line exactly {_WATCHPOINT_HEADING!r}; continuation: residual after marker",
        "next marker, diagnostics start, or canonical disclaimer",
        "always",
        "reader_visible",
        True,
    ),
    RegionSpec(
        "section:{n}[`:continuation:{ordinal}`]",
        "section_body",
        "primary: exact canonical section H2; continuation: residual after marker",
        "next marker, numbered H2, or special owned H2",
        "always",
        "reader_visible",
        True,
    ),
    RegionSpec(
        "header:title",
        "header",
        "first line exact target-date segment title",
        "newline",
        "always",
        "reader_visible",
    ),
    RegionSpec(
        "first_viewport:{ordinal}",
        "first_viewport",
        "remaining non-empty unclaimed span before section 1",
        "next claimed span or section 1",
        "conditional",
        "reader_visible",
        True,
    ),
)


@dataclass(frozen=True, slots=True)
class _MarkdownLine:
    start: int
    end: int
    content_end: int
    text: str


@dataclass(frozen=True, slots=True)
class _RegionCandidate:
    priority: int
    region: PublicDocumentRegion


def _layout_error(issue_code: str) -> ValueError:
    return ValueError(f"public document layout invalid: {issue_code}")


def _markdown_lines(markdown: str) -> tuple[_MarkdownLine, ...]:
    lines: list[_MarkdownLine] = []
    for match in re.finditer(r"[^\r\n]*(?:\r\n|\r|\n|$)", markdown):
        raw = match.group(0)
        if not raw:
            continue
        if raw.endswith("\r\n"):
            content_end = match.end() - 2
        elif raw.endswith(("\r", "\n")):
            content_end = match.end() - 1
        else:
            content_end = match.end()
        lines.append(
            _MarkdownLine(
                start=match.start(),
                end=match.end(),
                content_end=content_end,
                text=markdown[match.start() : content_end],
            )
        )
    return tuple(lines)


def _candidate(
    *,
    priority: int,
    region_id: str,
    block: PublicBlockKind,
    required: bool,
    projection_policy: PublicProjectionPolicy,
    start: int,
    end: int,
    content_start: int,
    content_end: int,
) -> _RegionCandidate:
    return _RegionCandidate(
        priority=priority,
        region=PublicDocumentRegion(
            region_id=region_id,
            block=block,
            required=required,
            projection_policy=projection_policy,
            start=start,
            end=end,
            content_start=content_start,
            content_end=content_end,
        ),
    )


def _matching_line_indices(lines: Sequence[_MarkdownLine], text: str) -> tuple[int, ...]:
    return tuple(index for index, line in enumerate(lines) if line.text == text)


def _prefix_line_indices(lines: Sequence[_MarkdownLine], prefix: str) -> tuple[int, ...]:
    return tuple(index for index, line in enumerate(lines) if line.text.startswith(prefix))


def _one_line_index(
    indices: Sequence[int],
    *,
    region_id: str,
    expected: bool,
) -> int | None:
    if len(indices) > 1:
        raise _layout_error(f"structure.duplicate.{region_id}")
    if expected and not indices:
        raise _layout_error(f"structure.missing.{region_id}")
    if not expected and indices:
        raise _layout_error(f"structure.unexpected.{region_id}")
    return indices[0] if indices else None


def _next_h2_start(
    lines: Sequence[_MarkdownLine],
    *,
    after_index: int,
    markdown_length: int,
) -> int:
    return next(
        (line.start for line in lines[after_index + 1 :] if line.text.startswith("## ")),
        markdown_length,
    )


def _render_supplement_block(supplement: PublicDocumentSupplement) -> str:
    """Wrap one typed E1 supplement in its canonical invisible marker pair."""

    region_id = f"{supplement.kind}:{supplement.supplement_id}"
    body = supplement.markdown
    separator = "" if body.endswith(("\n", "\r")) else "\n"
    return (
        f"<!-- investo:block {region_id} -->\n{body}{separator}<!-- /investo:block {region_id} -->"
    )


def _apply_pre_finalization_supplements(
    briefing: Briefing,
    *,
    supplements: Sequence[PublicDocumentSupplement],
    place: Callable[[str, tuple[str, ...]], str],
    owned_regions: Sequence[tuple[PublicSupplementKind, str]] = (),
) -> Briefing:
    """Apply already-rendered E1 supplements through one mutation boundary.

    Producers retain their existing kind-specific placement algorithm by
    supplying ``place``. This adapter owns canonical marker wrapping and the
    sole ``Briefing.rendered_markdown`` replacement for visual, chart, and
    carryover producers while the complete pure finalizer is wired in.

    An empty supplement tuple still invokes ``place``. Carryover uses that
    branch to remove a stale legacy block when today's typed input is empty.
    """

    ordered = tuple(supplements)
    ordering = tuple(
        (supplement.stable_order, supplement.kind, supplement.supplement_id)
        for supplement in ordered
    )
    if ordering != tuple(sorted(ordering)):
        raise ValueError("supplements must use stable (order, kind, id) ordering")
    _require_unique(
        tuple(supplement.supplement_id for supplement in ordered),
        field_name="supplement_id",
    )
    order_kind = tuple((supplement.stable_order, supplement.kind) for supplement in ordered)
    if len(set(order_kind)) != len(order_kind):
        raise ValueError("supplements must not duplicate (stable_order, kind)")

    rendered = tuple(_render_supplement_block(supplement) for supplement in ordered)
    rendered_by_region = {
        (supplement.kind, supplement.supplement_id): block
        for supplement, block in zip(ordered, rendered, strict=True)
    }
    region_order = tuple(dict.fromkeys((*rendered_by_region, *owned_regions)))
    for kind, supplement_id in region_order:
        if kind not in _SUPPLEMENT_KINDS:
            raise ValueError("owned supplement kind must be visual, chart, or carryover")
        _require_identifier(supplement_id, field_name="owned supplement_id")

    markdown = briefing.rendered_markdown
    for kind, supplement_id in region_order:
        _validate_existing_supplement_region(
            markdown,
            kind=kind,
            supplement_id=supplement_id,
        )
    if (
        rendered
        and all(block in markdown for block in rendered)
        and len(region_order) == len(rendered_by_region)
    ):
        return briefing
    placement_input = markdown
    for region in region_order:
        expected = rendered_by_region.get(region)
        if expected is not None and expected in placement_input:
            continue
        placement_input = _remove_existing_supplement_region(
            placement_input,
            kind=region[0],
            supplement_id=region[1],
        )
    placed = place(placement_input, rendered)
    return (
        briefing
        if placed == markdown
        else briefing.model_copy(update={"rendered_markdown": placed})
    )


def _remove_existing_supplement_region(
    markdown: str,
    *,
    kind: PublicSupplementKind,
    supplement_id: str,
) -> str:
    """Remove one complete typed marker pair before replacement/omission."""

    pattern = _validate_existing_supplement_region(
        markdown,
        kind=kind,
        supplement_id=supplement_id,
    )
    if pattern is None:
        return markdown
    return pattern.sub("", markdown, count=1)


def _validate_existing_supplement_region(
    markdown: str,
    *,
    kind: PublicSupplementKind,
    supplement_id: str,
) -> re.Pattern[str] | None:
    """Return the unique balanced marker pattern or fail closed."""

    region_id = f"{kind}:{supplement_id}"
    opening = f"<!-- investo:block {region_id} -->"
    closing = f"<!-- /investo:block {region_id} -->"
    opening_count = len(re.findall(rf"^{re.escape(opening)}$", markdown, re.MULTILINE))
    closing_count = len(re.findall(rf"^{re.escape(closing)}$", markdown, re.MULTILINE))
    if opening_count == closing_count == 0:
        return None
    if opening_count != 1 or closing_count != 1:
        raise ValueError("existing supplement marker must be one balanced pair")
    pattern = re.compile(
        rf"^{re.escape(opening)}(?:\r?\n|\r).*?^{re.escape(closing)}(?:\r?\n|\r)?",
        re.MULTILINE | re.DOTALL,
    )
    matches = tuple(pattern.finditer(markdown))
    if len(matches) != 1:
        raise ValueError("existing supplement marker must be one balanced pair")
    return pattern


def _marker_candidates(
    markdown: str,
    *,
    lines: Sequence[_MarkdownLine],
    expectation: PublicRegionExpectation,
) -> tuple[_RegionCandidate, ...]:
    open_marker: tuple[int, str, str] | None = None
    candidates: list[_RegionCandidate] = []
    supplement_ids: list[str] = []
    priorities = {"chart": 3, "visual": 4, "carryover": 5}
    for index, line in enumerate(lines):
        if "investo:block" not in line.text:
            continue
        opening = _MARKER_LINE_RE.fullmatch(line.text)
        closing = _MARKER_CLOSE_LINE_RE.fullmatch(line.text)
        if opening is not None:
            if open_marker is not None:
                raise _layout_error("structure.nested_supplement_marker")
            open_marker = (index, opening.group(1), opening.group(2))
            continue
        if closing is None:
            raise _layout_error("structure.malformed_supplement_marker")
        if open_marker is None:
            raise _layout_error("structure.unmatched_supplement_marker")
        open_index, kind, supplement_id = open_marker
        if (closing.group(1), closing.group(2)) != (kind, supplement_id):
            raise _layout_error("structure.mismatched_supplement_marker")
        opening_line = lines[open_index]
        body = markdown[opening_line.end : line.start]
        if kind == "carryover" and body.strip():
            carryover_headings = sum(
                child.text == "## Watchlist Carryover" for child in lines[open_index + 1 : index]
            )
            if carryover_headings != 1:
                raise _layout_error("structure.carryover_heading")
        region_id = f"{kind}:{supplement_id}"
        candidates.append(
            _candidate(
                priority=priorities[kind],
                region_id=region_id,
                block=kind,  # type: ignore[arg-type]
                required=True,
                projection_policy="reader_visible",
                start=opening_line.start,
                end=line.end,
                content_start=opening_line.end,
                content_end=line.start,
            )
        )
        supplement_ids.append(supplement_id)
        open_marker = None
    if open_marker is not None:
        raise _layout_error("structure.unmatched_supplement_marker")
    if len(set(supplement_ids)) != len(supplement_ids):
        raise _layout_error("structure.duplicate_supplement_id")
    if set(supplement_ids) != set(expectation.supplement_ids):
        raise _layout_error("structure.supplement_expectation")
    return tuple(candidates)


def _heading_candidate(
    *,
    lines: Sequence[_MarkdownLine],
    markdown_length: int,
    heading: str,
    expected: bool,
    priority: int,
    region_id: str,
    block: PublicBlockKind,
) -> _RegionCandidate | None:
    index = _one_line_index(
        _matching_line_indices(lines, heading),
        region_id=region_id,
        expected=expected,
    )
    if index is None:
        return None
    line = lines[index]
    return _candidate(
        priority=priority,
        region_id=region_id,
        block=block,
        required=True,
        projection_policy="reader_visible",
        start=line.start,
        end=_next_h2_start(lines, after_index=index, markdown_length=markdown_length),
        content_start=line.end,
        content_end=_next_h2_start(
            lines,
            after_index=index,
            markdown_length=markdown_length,
        ),
    )


def _line_candidate(
    *,
    line: _MarkdownLine,
    priority: int,
    region_id: str,
    block: PublicBlockKind,
    required: bool,
    projection_policy: PublicProjectionPolicy = "reader_visible",
    prefix: str | None = None,
) -> _RegionCandidate:
    content_start = line.content_end if prefix is None else line.start + len(prefix)
    return _candidate(
        priority=priority,
        region_id=region_id,
        block=block,
        required=required,
        projection_policy=projection_policy,
        start=line.start,
        end=line.end,
        content_start=content_start,
        content_end=line.content_end,
    )


def _is_numbered_h2(line: str) -> bool:
    if not line.startswith("## ") or len(line) <= 3:
        return False
    character_name = unicode_name(line[3], "")
    return character_name.startswith(("CIRCLED DIGIT", "CIRCLED NUMBER"))


def _marker_regions_within(
    candidates: Sequence[_RegionCandidate],
    *,
    start: int,
    end: int,
) -> tuple[PublicDocumentRegion, ...]:
    return tuple(
        candidate.region
        for candidate in sorted(candidates, key=lambda item: item.region.start)
        if candidate.region.block in {"visual", "chart", "carryover"}
        and start <= candidate.region.start
        and candidate.region.end <= end
    )


def _container_residual_candidates(
    *,
    priority: int,
    primary_region_id: str,
    block: PublicBlockKind,
    start: int,
    end: int,
    primary_content_start: int,
    exclusions: Sequence[PublicDocumentRegion],
) -> tuple[_RegionCandidate, ...]:
    """Partition one H2-owned body around higher-priority marker spans."""

    residuals: list[_RegionCandidate] = []
    cursor = start
    continuation_ordinal = 1
    for exclusion in exclusions:
        if exclusion.start < cursor or exclusion.end > end:
            raise _layout_error("structure.overlapping_supplement_markers")
        if exclusion.start > cursor:
            is_primary = cursor == start
            region_id = (
                primary_region_id
                if is_primary
                else f"{primary_region_id}:continuation:{continuation_ordinal}"
            )
            residuals.append(
                _candidate(
                    priority=priority,
                    region_id=region_id,
                    block=block,
                    required=True,
                    projection_policy="reader_visible",
                    start=cursor,
                    end=exclusion.start,
                    content_start=primary_content_start if is_primary else cursor,
                    content_end=exclusion.start,
                )
            )
            if not is_primary:
                continuation_ordinal += 1
        cursor = exclusion.end
    if cursor < end:
        is_primary = cursor == start
        region_id = (
            primary_region_id
            if is_primary
            else f"{primary_region_id}:continuation:{continuation_ordinal}"
        )
        residuals.append(
            _candidate(
                priority=priority,
                region_id=region_id,
                block=block,
                required=True,
                projection_policy="reader_visible",
                start=cursor,
                end=end,
                content_start=primary_content_start if is_primary else cursor,
                content_end=end,
            )
        )
    if not residuals or residuals[0].region.region_id != primary_region_id:
        raise _layout_error(f"structure.missing.{primary_region_id}")
    return tuple(residuals)


def _trim_fully_claimed_container_suffixes(
    markdown: str,
    candidates: Sequence[_RegionCandidate],
) -> tuple[_RegionCandidate, ...]:
    """End H2 augmentation regions before fully owned trailing line regions."""

    trimmable = {"shared_macro", "crypto_indicators", "channel_anchors"}
    result = list(candidates)
    for index, container in enumerate(result):
        region = container.region
        if region.block not in trimmable:
            continue
        nested = sorted(
            (
                candidate.region
                for candidate in result
                if candidate is not container
                and region.content_start <= candidate.region.start
                and candidate.region.end <= region.end
            ),
            key=lambda child: child.start,
        )
        if not nested:
            continue
        cursor = nested[0].start
        suffix_is_claimed = True
        for child in nested:
            if child.start < cursor or markdown[cursor : child.start].strip():
                suffix_is_claimed = False
                break
            cursor = child.end
        if not suffix_is_claimed or markdown[cursor : region.end].strip():
            continue
        trimmed = replace(
            region,
            end=nested[0].start,
            content_end=min(region.content_end, nested[0].start),
        )
        result[index] = replace(container, region=trimmed)
    return tuple(result)


def _require_layout_region(
    layout: PublicDocumentLayout,
    region_id: str,
) -> PublicDocumentRegion:
    matches = tuple(region for region in layout.regions if region.region_id == region_id)
    if len(matches) != 1:
        raise ValueError("region_id must identify exactly one indexed region")
    return matches[0]


def _require_stable_region_ids(
    *,
    before: Sequence[PublicDocumentRegion],
    after: Sequence[PublicDocumentRegion],
    operation: str,
) -> None:
    if tuple(region.region_id for region in before) != tuple(region.region_id for region in after):
        raise ValueError(f"region IDs changed during {operation}")


def _reindex_public_document(
    markdown: str,
    *,
    expectation: PublicRegionExpectation,
) -> PublicDocumentLayout:
    if not isinstance(markdown, str):
        raise TypeError("markdown must be str")
    if not markdown:
        raise _layout_error("structure.empty")
    lines = _markdown_lines(markdown)
    candidates: list[_RegionCandidate] = []

    canonical_index = _one_line_index(
        _matching_line_indices(lines, _CANONICAL_DISCLAIMER_HEADING),
        region_id="disclaimer:canonical",
        expected=True,
    )
    assert canonical_index is not None
    canonical_line = lines[canonical_index]
    candidates.append(
        _candidate(
            priority=1,
            region_id="disclaimer:canonical",
            block="disclaimer",
            required=True,
            projection_policy="exact_disclaimer",
            start=canonical_line.start,
            end=len(markdown),
            content_start=canonical_line.end,
            content_end=len(markdown),
        )
    )

    diagnostics_index = _one_line_index(
        _matching_line_indices(lines, _DIAGNOSTICS_OPEN),
        region_id="diagnostics:quality",
        expected=True,
    )
    assert diagnostics_index is not None
    diagnostics_closes = tuple(
        index
        for index in range(diagnostics_index + 1, len(lines))
        if lines[index].text == _DIAGNOSTICS_CLOSE
    )
    if not diagnostics_closes:
        raise _layout_error("structure.unmatched_diagnostics")
    diagnostics_close_index = diagnostics_closes[0]
    if any(
        line.text.startswith("<details")
        for line in lines[diagnostics_index + 1 : diagnostics_close_index + 1]
    ):
        raise _layout_error("structure.nested_diagnostics")
    if len(diagnostics_closes) > 1:
        raise _layout_error("structure.duplicate_diagnostics_close")
    diagnostics_line = lines[diagnostics_index]
    diagnostics_close = lines[diagnostics_close_index]
    candidates.append(
        _candidate(
            priority=2,
            region_id="diagnostics:quality",
            block="diagnostics",
            required=True,
            projection_policy="protected_diagnostics",
            start=diagnostics_line.start,
            end=diagnostics_close.end,
            content_start=diagnostics_line.end,
            content_end=diagnostics_close.start,
        )
    )
    candidates.extend(_marker_candidates(markdown, lines=lines, expectation=expectation))

    conditional_headings = (
        (
            _SHARED_MACRO_HEADING,
            expectation.shared_macro_required,
            6,
            "macro:shared",
            "shared_macro",
        ),
        (
            _CRYPTO_INDICATOR_HEADING,
            expectation.crypto_indicators_required,
            7,
            "indicator:crypto",
            "crypto_indicators",
        ),
        (
            _CHANNEL_ANCHOR_HEADING,
            expectation.channel_anchors_required,
            8,
            "anchor:channel",
            "channel_anchors",
        ),
    )
    for heading, expected, priority, region_id, block in conditional_headings:
        found = _heading_candidate(
            lines=lines,
            markdown_length=len(markdown),
            heading=heading,
            expected=expected,
            priority=priority,
            region_id=region_id,
            block=block,  # type: ignore[arg-type]
        )
        if found is not None:
            candidates.append(found)

    cause_indices = _prefix_line_indices(lines, _CAUSE_PREFIX)
    if len(cause_indices) > 1:
        raise _layout_error("structure.duplicate.cause:cross_market")
    cause_index = cause_indices[0] if cause_indices else None
    if cause_index is not None:
        candidates.append(
            _line_candidate(
                line=lines[cause_index],
                priority=9,
                region_id="cause:cross_market",
                block="cause_map",
                required=False,
                prefix=_CAUSE_PREFIX,
            )
        )

    thesis_index = _one_line_index(
        _prefix_line_indices(lines, _THESIS_PREFIX),
        region_id="thesis:daily",
        expected=expectation.daily_thesis_required,
    )
    if thesis_index is not None:
        candidates.append(
            _line_candidate(
                line=lines[thesis_index],
                priority=10,
                region_id="thesis:daily",
                block="daily_thesis",
                required=True,
                prefix=_THESIS_PREFIX,
            )
        )

    navigation_index = _one_line_index(
        _prefix_line_indices(lines, _NAVIGATION_PREFIX),
        region_id="navigation:segments",
        expected=expectation.segmented_mode,
    )
    if navigation_index is not None:
        candidates.append(
            _line_candidate(
                line=lines[navigation_index],
                priority=11,
                region_id="navigation:segments",
                block="navigation",
                required=True,
                prefix=_NAVIGATION_PREFIX,
            )
        )

    short_disclaimer = (
        _SHORT_DISCLAIMER_CRYPTO if expectation.segment == CRYPTO else _SHORT_DISCLAIMER_EQUITY
    )
    other_short_disclaimer = (
        _SHORT_DISCLAIMER_EQUITY if expectation.segment == CRYPTO else _SHORT_DISCLAIMER_CRYPTO
    )
    if _matching_line_indices(lines, other_short_disclaimer):
        raise _layout_error("structure.wrong_segment_short_disclaimer")
    short_index = _one_line_index(
        _matching_line_indices(lines, short_disclaimer),
        region_id="disclaimer:short",
        expected=True,
    )
    assert short_index is not None
    candidates.append(
        _line_candidate(
            line=lines[short_index],
            priority=12,
            region_id="disclaimer:short",
            block="disclaimer",
            required=True,
            projection_policy="exact_disclaimer",
        )
    )

    expected_anchor_header = (
        _CRYPTO_ANCHOR_HEADER if expectation.segment == CRYPTO else _EQUITY_ANCHOR_HEADER
    )
    other_anchor_header = (
        _EQUITY_ANCHOR_HEADER if expectation.segment == CRYPTO else _CRYPTO_ANCHOR_HEADER
    )
    if _matching_line_indices(lines, other_anchor_header):
        raise _layout_error("structure.wrong_segment_anchor_header")
    anchor_index = _one_line_index(
        _matching_line_indices(lines, expected_anchor_header),
        region_id="anchor:market",
        expected=expectation.anchor_table_required,
    )
    if anchor_index is not None:
        if anchor_index + 1 >= len(lines) or lines[anchor_index + 1].text != _ANCHOR_DELIMITER:
            raise _layout_error("structure.anchor_delimiter")
        end_index = anchor_index + 2
        while end_index < len(lines) and lines[end_index].text.startswith("|"):
            end_index += 1
        if end_index == anchor_index + 2:
            raise _layout_error("structure.anchor_rows")
        anchor_end = lines[end_index].start if end_index < len(lines) else len(markdown)
        candidates.append(
            _candidate(
                priority=13,
                region_id="anchor:market",
                block="anchor_table",
                required=True,
                projection_policy="reader_visible",
                start=lines[anchor_index].start,
                end=anchor_end,
                content_start=lines[anchor_index + 1].end,
                content_end=anchor_end,
            )
        )

    watchpoint_index = _one_line_index(
        _matching_line_indices(lines, _WATCHPOINT_HEADING),
        region_id="watchpoints:section",
        expected=True,
    )
    assert watchpoint_index is not None
    watchpoint_line = lines[watchpoint_index]
    watchpoint_boundaries = tuple(
        position
        for position in (diagnostics_line.start, canonical_line.start)
        if position > watchpoint_line.start
    )
    if not watchpoint_boundaries:
        raise _layout_error("structure.watchpoint_order")
    watchpoint_end = min(watchpoint_boundaries)
    candidates.extend(
        _container_residual_candidates(
            priority=14,
            primary_region_id="watchpoints:section",
            block="watchpoints",
            start=watchpoint_line.start,
            end=watchpoint_end,
            primary_content_start=watchpoint_line.end,
            exclusions=_marker_regions_within(
                candidates,
                start=watchpoint_line.start,
                end=watchpoint_end,
            ),
        )
    )

    allowed_numbered = {
        *_SECTION_HEADINGS,
        _WATCHPOINT_HEADING,
        _CANONICAL_DISCLAIMER_HEADING,
        _SHARED_MACRO_HEADING,
        _CRYPTO_INDICATOR_HEADING,
        _CHANNEL_ANCHOR_HEADING,
    }
    if any(_is_numbered_h2(line.text) and line.text not in allowed_numbered for line in lines):
        raise _layout_error("structure.unexpected_numbered_h2")
    section_indices: list[int] = []
    for number, heading in enumerate(_SECTION_HEADINGS, start=1):
        section_index = _one_line_index(
            _matching_line_indices(lines, heading),
            region_id=f"section:{number}",
            expected=True,
        )
        assert section_index is not None
        section_indices.append(section_index)
    if section_indices != sorted(section_indices):
        raise _layout_error("structure.section_order")
    owned_h2s = {
        *_SECTION_HEADINGS,
        _WATCHPOINT_HEADING,
        _CANONICAL_DISCLAIMER_HEADING,
        _SHARED_MACRO_HEADING,
        _CRYPTO_INDICATOR_HEADING,
        _CHANNEL_ANCHOR_HEADING,
    }
    for number, section_index in enumerate(section_indices, start=1):
        section_line = lines[section_index]
        section_end = next(
            (line.start for line in lines[section_index + 1 :] if line.text in owned_h2s),
            len(markdown),
        )
        candidates.extend(
            _container_residual_candidates(
                priority=15,
                primary_region_id=f"section:{number}",
                block="section_body",
                start=section_line.start,
                end=section_end,
                primary_content_start=section_line.end,
                exclusions=_marker_regions_within(
                    candidates,
                    start=section_line.start,
                    end=section_end,
                ),
            )
        )

    expected_title = (
        f"# {expectation.target_date.isoformat()} {SEGMENT_LABELS[expectation.segment]} 시황"
    )
    if not lines or lines[0].text != expected_title:
        raise _layout_error("structure.header_title")
    candidates.append(
        _line_candidate(
            line=lines[0],
            priority=16,
            region_id="header:title",
            block="header",
            required=True,
        )
    )

    candidates = list(_trim_fully_claimed_container_suffixes(markdown, candidates))
    ordered = sorted(candidates, key=lambda item: (item.region.start, item.priority))
    region_ids = tuple(candidate.region.region_id for candidate in ordered)
    if len(set(region_ids)) != len(region_ids):
        raise _layout_error("structure.duplicate_region_id")
    for previous, current in pairwise(ordered):
        if current.region.start < previous.region.end:
            raise _layout_error("structure.overlapping_regions")

    first_section_start = lines[section_indices[0]].start
    first_viewport: list[_RegionCandidate] = []
    cursor = 0
    ordinal = 1
    for claimed in ordered:
        if claimed.region.start >= first_section_start:
            break
        if claimed.region.start > cursor:
            first_viewport.append(
                _candidate(
                    priority=17,
                    region_id=f"first_viewport:{ordinal}",
                    block="first_viewport",
                    required=True,
                    projection_policy="reader_visible",
                    start=cursor,
                    end=claimed.region.start,
                    content_start=cursor,
                    content_end=claimed.region.start,
                )
            )
            ordinal += 1
        cursor = claimed.region.end
    if cursor < first_section_start:
        first_viewport.append(
            _candidate(
                priority=17,
                region_id=f"first_viewport:{ordinal}",
                block="first_viewport",
                required=True,
                projection_policy="reader_visible",
                start=cursor,
                end=first_section_start,
                content_start=cursor,
                content_end=first_section_start,
            )
        )

    partition = sorted((*ordered, *first_viewport), key=lambda item: item.region.start)
    normalized: list[PublicDocumentRegion] = []
    cursor = 0
    for claimed in partition:
        region = claimed.region
        if region.start < cursor:
            raise _layout_error("structure.overlapping_regions")
        if region.start > cursor:
            gap = markdown[cursor : region.start]
            if cursor < first_section_start:
                raise _layout_error("structure.first_viewport_partition")
            if gap.strip() or not normalized:
                raise _layout_error("structure.unclaimed_bytes")
            normalized[-1] = replace(normalized[-1], end=region.start)
        normalized.append(region)
        cursor = region.end
    if cursor < len(markdown):
        gap = markdown[cursor:]
        if gap.strip() or not normalized:
            raise _layout_error("structure.unclaimed_bytes")
        normalized[-1] = replace(normalized[-1], end=len(markdown))
        cursor = len(markdown)
    if not normalized or normalized[0].start != 0 or cursor != len(markdown):
        raise _layout_error("structure.partition")
    if any(left.end != right.start for left, right in pairwise(normalized)):
        raise _layout_error("structure.partition")
    return PublicDocumentLayout(
        markdown=markdown,
        regions=tuple(normalized),
        expectation=expectation,
    )


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


def _accumulate_watchpoint_result(
    draft: PublicDocumentDraft,
    result: WatchpointRenderResult,
) -> PublicDocumentDraft:
    """Carry a typed phase-1 watchpoint outcome on E2 before projection.

    The assembly caller owns ``result.markdown`` and advances the reindexed
    layout separately. This helper prevents later phases from rediscovering
    watchpoint availability by parsing the reader-facing Korean copy.
    """

    if draft.phase != "generated":
        raise ValueError("watchpoint result can only be accumulated during assembly")
    limitation_reasons = tuple(
        dict.fromkeys((*draft.limitation_reasons, *result.limitation_reasons))
    )
    if limitation_reasons == draft.limitation_reasons:
        return draft
    return _construct_draft(
        segment=draft.segment,
        target_date=draft.target_date,
        source_briefing=draft.source_briefing,
        layout=draft.layout,
        phase=draft.phase,
        limitation_reasons=limitation_reasons,
        block_outcomes=draft.block_outcomes,
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


def _assemble_phase_one_reader_draft(
    draft: PublicDocumentDraft,
    context: PublicDocumentContext,
) -> PublicDocumentDraft:
    """Run the typed reader collaborator and advance one E2 draft.

    This is the concrete phase-handler slice used by the sealed lifecycle. The
    default orchestrator still reaches the dict compatibility wrapper until
    the Step 5 finalizer switch, but the E2 assembly path cannot discard the
    typed watchpoint result: exactly one result is required for this segment
    and accumulated before the ``assembled`` transition.
    """

    if draft.target_date != context.target_date or draft.segment not in context.expected_segments:
        raise ValueError("reader assembly context identity must match draft")
    observed: list[WatchpointRenderResult] = []

    def observe(segment: MarketSegment, result: WatchpointRenderResult) -> None:
        if segment != draft.segment or observed:
            raise ValueError("reader assembly must produce exactly one matching watchpoint result")
        observed.append(result)

    rewritten = _assemble_phase_one_reader_briefings(
        {draft.segment: draft.source_briefing},
        anchors_by_segment=context.anchors_by_segment,
        bundle_context=context.bundle_context,
        items_by_segment=context.items_by_segment,
        _watchpoint_result_observer=observe,
    )
    if len(observed) != 1 or set(rewritten) != {draft.segment}:
        raise ValueError("reader assembly must produce exactly one segment result")
    accumulated = _accumulate_watchpoint_result(draft, observed[0])
    layout = PublicDocumentLayout.reindex(
        rewritten[draft.segment].rendered_markdown,
        expectation=draft.layout.expectation,
    )
    return _transition_draft(
        accumulated,
        next_phase="assembled",
        layout=layout,
    )


def _project_assembled_draft(
    draft: PublicDocumentDraft,
    context: PublicDocumentContext,
) -> PublicDocumentDraft:
    """Run the canonical u108 projection at the E2 phase boundary."""

    if draft.target_date != context.target_date or draft.segment not in context.expected_segments:
        raise ValueError("projection context identity must match draft")
    layout = project_public_markdown(
        draft.layout,
        limitation_reasons=draft.limitation_reasons,
    )
    return _transition_draft(
        draft,
        next_phase="projected",
        layout=layout,
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


def _select_surviving_supplement_artifact_ids(
    draft: PublicDocumentDraft,
    context: PublicDocumentContext,
) -> tuple[str, ...]:
    """Join typed E1 supplements to E5 artifacts by owned region identity."""

    regions = {region.region_id: region for region in draft.layout.regions}
    outcomes = {outcome.region_id: outcome for outcome in draft.block_outcomes}
    selected: list[str] = []
    for supplement in context.supplements_by_segment.get(draft.segment, ()):
        region_id = f"{supplement.kind}:{supplement.supplement_id}"
        region = regions.get(region_id)
        if region is None or region.block != supplement.kind:
            raise _FinalizationInvariantError(
                phase="validated",
                issue_code="invariant.supplement_region",
            )
        outcome = outcomes.get(region_id)
        if outcome is not None and outcome.block != supplement.kind:
            raise _FinalizationInvariantError(
                phase="validated",
                issue_code="invariant.supplement_outcome",
            )
        is_empty = region.content_start == region.content_end
        is_omitted = outcome is not None and outcome.disposition == "omitted"
        if is_empty != is_omitted:
            raise _FinalizationInvariantError(
                phase="validated",
                issue_code="invariant.supplement_omission",
            )
        if not is_omitted:
            selected.extend(supplement.artifact_ids)
    return tuple(selected)


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


class PublicNotificationSummaryError(ValueError):
    """Publisher-private bounded terminal-summary validation error."""

    def __init__(self, issue_code: PublicNotificationSummaryIssueCode) -> None:
        if issue_code not in _NOTIFICATION_SUMMARY_ISSUE_CODES:
            raise ValueError("unsupported public notification summary issue code")
        self.issue_code = issue_code
        super().__init__(f"public notification summary invalid: code={issue_code}")


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

    artifact_ids = _select_surviving_supplement_artifact_ids(current, context)
    handler_artifact_ids = tuple(handlers.artifact_ids(current, context))
    if handler_artifact_ids != artifact_ids:
        raise _FinalizationInvariantError(
            phase="validated",
            issue_code="invariant.artifact_selection",
        )
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
