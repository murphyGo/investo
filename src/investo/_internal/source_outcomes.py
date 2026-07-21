"""Neutral source-outcome scoping shared by briefing and publisher."""

from __future__ import annotations

from collections.abc import Sequence
from typing import NewType

from investo._internal.source_specs import source_names_for_outcome_segment
from investo.models import MarketSegment, SourceOutcome

SegmentScopedOutcomes = NewType("SegmentScopedOutcomes", tuple[SourceOutcome, ...])


def scope_source_outcomes(
    outcomes: Sequence[SourceOutcome],
    segment: MarketSegment,
) -> SegmentScopedOutcomes:
    """Return outcomes whose canonical source descriptor includes ``segment``."""

    allow_list = source_names_for_outcome_segment(segment)
    return SegmentScopedOutcomes(
        tuple(outcome for outcome in outcomes if outcome.source_name in allow_list)
    )


def segment_source_outcomes(
    segment: MarketSegment,
    outcomes: Sequence[SourceOutcome],
) -> SegmentScopedOutcomes:
    """Compatibility-order wrapper for segment-level outcome scoping."""

    return scope_source_outcomes(outcomes, segment)


__all__ = [
    "SegmentScopedOutcomes",
    "scope_source_outcomes",
    "segment_source_outcomes",
]
