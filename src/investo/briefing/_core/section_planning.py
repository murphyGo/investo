"""Stage 1.5 section planning: group classified items into sections.

References:
    Functional Design E3 (`domain-entities.md`) — SectionPlan
    Functional Design L1.5 — section grouping

Moved verbatim from ``briefing/pipeline.py`` in the u83 decomposition;
behavior-preserving (move-only). ``SectionPlan`` + ``build_section_plan``
keep their import path via re-export from ``briefing/pipeline.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from investo.briefing._core.classification import ClassificationResult
from investo.models import NormalizedItem
from investo.models.macro import is_required_macro_actual

StoryTier = Literal["core", "supporting", "context", "watchlist_only"]
_TIER_BASE: dict[StoryTier, int] = {
    "core": 300,
    "supporting": 200,
    "context": 100,
    "watchlist_only": 50,
}
_MARKET_STATE_SOURCES = (
    "anchor",
    "price",
    "market",
    "stooq",
    "yfinance",
    "fred",
    "fomc",
    "coingecko",
    "derivatives",
    "fng",
)
_SUPPORTING_TERMS = (
    "sector",
    "섹터",
    "company",
    "earnings",
    "실적",
    "수급",
    "flow",
    "fund",
    "ETF",
)
_CROSS_MARKET_TERMS = (
    "shared_macro",
    "cross_market",
    "cross-segment",
    "bundle_context",
    "geopolitical_oil_macro",
    "fed_policy_event",
    "global_systemic_risk",
)


@dataclass(frozen=True, slots=True)
class StoryMetadata:
    tier: StoryTier
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SectionPlan:
    """Intermediate fed to Stage 2's prompt builder (FD E3)."""

    target_date: date
    items_by_section: dict[int, tuple[NormalizedItem, ...]]
    unassigned: tuple[NormalizedItem, ...]
    required_macro_items: tuple[NormalizedItem, ...] = ()
    story_metadata: dict[str, StoryMetadata] = field(default_factory=dict)


def story_identity(item: NormalizedItem) -> str:
    """Stable key for per-item prompt metadata."""

    return "|".join(
        (
            item.source_name,
            item.title,
            str(item.url) if item.url is not None else "",
            item.published_at.isoformat(),
        )
    )


def assign_story_metadata(
    items: Sequence[NormalizedItem],
    *,
    target_date: date,
) -> dict[str, StoryMetadata]:
    """Assign deterministic story hierarchy metadata for Stage 2 inputs."""

    return {story_identity(item): _story_metadata(item, target_date=target_date) for item in items}


def build_section_plan(
    items: Sequence[NormalizedItem],
    classification: ClassificationResult,
    target_date: date,
) -> SectionPlan:
    """Group items by section per Stage 1's classification (FD E3, L1.5).

    Items within each section preserve ``published_at`` descending order
    (newest first) — most recent context lands at the top of each Stage
    2 section. Items in ``unassigned`` are forwarded as-is for Stage 2
    to use as context for sections ① and ⑥.
    """
    items_by_id = {idx + 1: item for idx, item in enumerate(items)}

    buckets: dict[int, list[NormalizedItem]] = {2: [], 3: [], 4: [], 5: []}
    for item_id, section_id in classification.assignments.items():
        if item_id in items_by_id and section_id in buckets:
            buckets[section_id].append(items_by_id[item_id])

    story_metadata = assign_story_metadata(items, target_date=target_date)

    for section_id in buckets:
        buckets[section_id].sort(
            key=lambda it: _story_sort_key(it, story_metadata=story_metadata),
        )

    unassigned_items = tuple(items_by_id[i] for i in classification.unassigned if i in items_by_id)

    return SectionPlan(
        target_date=target_date,
        items_by_section={k: tuple(v) for k, v in buckets.items()},
        unassigned=unassigned_items,
        required_macro_items=tuple(item for item in items if is_required_macro_actual(item)),
        story_metadata=story_metadata,
    )


def _story_sort_key(
    item: NormalizedItem,
    *,
    story_metadata: dict[str, StoryMetadata],
) -> tuple[int, float, str, str, str]:
    metadata = story_metadata[story_identity(item)]
    return (
        -metadata.score,
        -item.published_at.timestamp(),
        item.source_name,
        item.title,
        story_identity(item),
    )


def _story_metadata(item: NormalizedItem, *, target_date: date) -> StoryMetadata:
    reasons = _story_reasons(item)
    tier = _story_tier(reasons)
    score = _TIER_BASE[tier]
    if "required_macro_actual" in reasons:
        score += 80
    if "approved_cross_market_core" in reasons:
        score += 40
    if item.published_at.date() == target_date:
        score += 20
    elif (target_date - item.published_at.date()).days == 1:
        score += 10
    if item.category in ("macro", "price") or _metadata_value(item, "source_tier") == "primary":
        score += 10
    return StoryMetadata(tier=tier, score=score, reasons=tuple(reasons))


def _story_reasons(item: NormalizedItem) -> list[str]:
    reasons: list[str] = []
    if is_required_macro_actual(item):
        reasons.append("required_macro_actual")
    if _is_approved_cross_market_core(item):
        reasons.append("approved_cross_market_core")
    if _is_segment_native_market_state(item):
        reasons.append("segment_native_market_state")
    if _is_watchlist_only(item):
        reasons.append("watchlist_only")
    if not reasons and _supports_core(item):
        reasons.append("supports_core")
    if not reasons:
        reasons.append("background_context")
    return reasons


def _story_tier(reasons: Sequence[str]) -> StoryTier:
    if any(
        reason in reasons
        for reason in (
            "required_macro_actual",
            "segment_native_market_state",
            "approved_cross_market_core",
        )
    ):
        return "core"
    if "supports_core" in reasons:
        return "supporting"
    if "watchlist_only" in reasons:
        return "watchlist_only"
    return "context"


def _is_segment_native_market_state(item: NormalizedItem) -> bool:
    if item.category in ("macro", "price"):
        return True
    haystack = _item_haystack(item)
    return any(term in haystack for term in _MARKET_STATE_SOURCES)


def _is_approved_cross_market_core(item: NormalizedItem) -> bool:
    metadata = item.raw_metadata
    for key in ("cross_market_core_allowed", "cross_market_core", "shared_macro"):
        if _metadata_value(item, key) in ("1", "true", "yes", "allowed", "approved"):
            return True
    haystack = " ".join(str(value).casefold() for value in metadata.values())
    return any(term in haystack for term in _CROSS_MARKET_TERMS)


def _is_watchlist_only(item: NormalizedItem) -> bool:
    metadata = item.raw_metadata
    if _metadata_value(item, "story_tier") == "watchlist_only":
        return True
    if _metadata_value(item, "watchlist_only") in ("1", "true", "yes"):
        return True
    has_watchlist = any("watchlist" in key or "public_impact" in key for key in metadata)
    return has_watchlist and item.category == "news" and not _supports_core(item)


def _supports_core(item: NormalizedItem) -> bool:
    haystack = _item_haystack(item)
    return item.category == "earnings" or any(
        term.casefold() in haystack for term in _SUPPORTING_TERMS
    )


def _item_haystack(item: NormalizedItem) -> str:
    return " ".join(
        (
            item.source_name,
            item.category,
            item.title,
            item.summary or "",
            " ".join(f"{key}={value}" for key, value in item.raw_metadata.items()),
        )
    ).casefold()


def _metadata_value(item: NormalizedItem, key: str) -> str:
    value = item.raw_metadata.get(key)
    return str(value).strip().casefold() if value is not None else ""


def _required_macro_item_ids(items: Sequence[NormalizedItem]) -> frozenset[int]:
    """Return Stage 1 synthetic ids for required macro actuals."""

    return frozenset(
        idx for idx, item in enumerate(items, start=1) if is_required_macro_actual(item)
    )


__all__ = [
    "SectionPlan",
    "StoryMetadata",
    "StoryTier",
    "_required_macro_item_ids",
    "assign_story_metadata",
    "build_section_plan",
    "story_identity",
]
