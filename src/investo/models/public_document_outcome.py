"""Shared public-document completeness and per-segment outcome types."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

from investo.models.segments import SEGMENT_LABELS, MarketSegment

ContentCompleteness = Literal["complete", "partial", "none"]
SegmentFinalizationState = Literal[
    "finalized",
    "finalized_degraded",
    "generation_absent",
    "trust_blocked",
]
NumericClaimLineKind = Literal[
    "prose_sentence",
    "list_or_callout",
    "table_row",
    "h3_subtree",
    "structural_region",
]
NumericContainmentAction = Literal[
    "corrected",
    "rewritten",
    "excluded",
    "replaced",
    "omitted",
    "minimal_fallback",
]

_FINALIZATION_STATES: Final[frozenset[str]] = frozenset(
    {"finalized", "finalized_degraded", "generation_absent", "trust_blocked"}
)
_LINE_KINDS: Final[frozenset[str]] = frozenset(
    {"prose_sentence", "list_or_callout", "table_row", "h3_subtree", "structural_region"}
)
_CONTAINMENT_ACTIONS: Final[frozenset[str]] = frozenset(
    {"corrected", "rewritten", "excluded", "replaced", "omitted", "minimal_fallback"}
)
_ISSUE_CODE_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SYMBOL_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9^][A-Za-z0-9.^=_:-]{0,127}$")
_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class NumericContainmentOutcome:
    """Bounded sealed witness for one domestic numeric containment action."""

    target_date: date
    segment: MarketSegment
    symbol: str
    region_id: str
    line_kind: NumericClaimLineKind
    action: NumericContainmentAction
    issue_codes: tuple[str, ...]
    claim_digest: str

    def __post_init__(self) -> None:
        if self.segment not in SEGMENT_LABELS:
            raise ValueError("segment must be a known market segment")
        if _SYMBOL_RE.fullmatch(self.symbol) is None:
            raise ValueError("symbol must be a bounded identifier")
        if _IDENTIFIER_RE.fullmatch(self.region_id) is None:
            raise ValueError("region_id must be a bounded identifier")
        if self.line_kind not in _LINE_KINDS:
            raise ValueError("line_kind is not supported")
        if self.action not in _CONTAINMENT_ACTIONS:
            raise ValueError("action is not supported")
        canonical = tuple(sorted(set(self.issue_codes)))
        if not canonical or any(_ISSUE_CODE_RE.fullmatch(code) is None for code in canonical):
            raise ValueError("issue_codes must contain bounded machine-readable codes")
        if _SHA256_RE.fullmatch(self.claim_digest) is None:
            raise ValueError("claim_digest must be a lowercase SHA-256 digest")
        object.__setattr__(self, "issue_codes", canonical)


@dataclass(frozen=True, slots=True)
class SegmentFinalizationOutcome:
    """One canonical expected segment's terminal content disposition."""

    segment: MarketSegment
    state: SegmentFinalizationState
    issue_codes: tuple[str, ...] = ()
    numeric_containment_outcomes: tuple[NumericContainmentOutcome, ...] = ()

    def __post_init__(self) -> None:
        if self.segment not in SEGMENT_LABELS:
            raise ValueError("segment must be a known market segment")
        if self.state not in _FINALIZATION_STATES:
            raise ValueError("segment finalization state is not supported")
        canonical = tuple(sorted(set(self.issue_codes)))
        if any(_ISSUE_CODE_RE.fullmatch(code) is None for code in canonical):
            raise ValueError("issue_codes must contain bounded machine-readable codes")
        numeric_outcomes = tuple(self.numeric_containment_outcomes)
        if any(outcome.segment != self.segment for outcome in numeric_outcomes):
            raise ValueError("numeric containment outcome segment must match")
        if self.state == "finalized" and numeric_outcomes:
            raise ValueError("finalized state cannot carry numeric containment outcomes")
        if self.state == "finalized_degraded":
            if not numeric_outcomes:
                raise ValueError("finalized_degraded requires numeric containment outcomes")
            if "numeric.anchor_assertion" not in canonical:
                raise ValueError("finalized_degraded requires numeric.anchor_assertion")
        elif numeric_outcomes:
            raise ValueError("numeric containment outcomes require finalized_degraded")
        object.__setattr__(self, "issue_codes", canonical)
        object.__setattr__(self, "numeric_containment_outcomes", numeric_outcomes)


__all__ = [
    "ContentCompleteness",
    "NumericClaimLineKind",
    "NumericContainmentAction",
    "NumericContainmentOutcome",
    "SegmentFinalizationOutcome",
    "SegmentFinalizationState",
]
