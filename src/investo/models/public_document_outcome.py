"""Shared public-document completeness and per-segment outcome types."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

from investo.models.segments import SEGMENT_LABELS, MarketSegment

ContentCompleteness = Literal["complete", "partial", "none"]
SegmentFinalizationState = Literal["finalized", "generation_absent", "trust_blocked"]

_FINALIZATION_STATES: Final[frozenset[str]] = frozenset(
    {"finalized", "generation_absent", "trust_blocked"}
)
_ISSUE_CODE_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


@dataclass(frozen=True, slots=True)
class SegmentFinalizationOutcome:
    """One canonical expected segment's terminal content disposition."""

    segment: MarketSegment
    state: SegmentFinalizationState
    issue_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.segment not in SEGMENT_LABELS:
            raise ValueError("segment must be a known market segment")
        if self.state not in _FINALIZATION_STATES:
            raise ValueError("segment finalization state is not supported")
        canonical = tuple(sorted(set(self.issue_codes)))
        if any(_ISSUE_CODE_RE.fullmatch(code) is None for code in canonical):
            raise ValueError("issue_codes must contain bounded machine-readable codes")
        object.__setattr__(self, "issue_codes", canonical)


__all__ = [
    "ContentCompleteness",
    "SegmentFinalizationOutcome",
    "SegmentFinalizationState",
]
