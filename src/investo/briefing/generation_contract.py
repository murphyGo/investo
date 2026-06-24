"""Structured briefing generation boundary contracts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from investo.briefing._core.orchestration import GenerationPolicy
from investo.briefing.claude_code import ClaudeRunner, RetryBudget
from investo.briefing.context import RecentBriefingsContext
from investo.briefing.lineage import MacroLineageTrace
from investo.briefing.market_anchor import MarketAnchor
from investo.briefing.segments import MarketSegment
from investo.briefing.watchlist import WatchlistConfig
from investo.models import Briefing, BriefingCarryover, NormalizedItem, SourceOutcome
from investo.models.bundle_context import BundleContext


@dataclass(frozen=True, slots=True)
class GenerationInput:
    target_date: date
    items: tuple[NormalizedItem, ...]
    watchlist_config: WatchlistConfig
    runner: ClaudeRunner | None = None
    budget: RetryBudget | None = None
    segment: MarketSegment | None = None
    data_limited: bool = False
    source_outcomes: tuple[SourceOutcome, ...] = ()
    recent_context: RecentBriefingsContext | None = None
    carryover: BriefingCarryover | None = None
    market_anchors: tuple[MarketAnchor, ...] = ()
    generation_policy: GenerationPolicy | None = None
    bundle_context: BundleContext | None = None
    fact_context_block: str = ""
    archive_root: Path | None = None
    macro_lineage_all_items: tuple[NormalizedItem, ...] | None = None

    def __init__(
        self,
        *,
        target_date: date,
        items: Sequence[NormalizedItem],
        watchlist_config: WatchlistConfig,
        runner: ClaudeRunner | None = None,
        budget: RetryBudget | None = None,
        segment: MarketSegment | None = None,
        data_limited: bool = False,
        source_outcomes: Sequence[SourceOutcome] = (),
        recent_context: RecentBriefingsContext | None = None,
        carryover: BriefingCarryover | None = None,
        market_anchors: Sequence[MarketAnchor] = (),
        generation_policy: GenerationPolicy | None = None,
        bundle_context: BundleContext | None = None,
        fact_context_block: str = "",
        archive_root: Path | None = None,
        macro_lineage_all_items: Sequence[NormalizedItem] | None = None,
    ) -> None:
        object.__setattr__(self, "target_date", target_date)
        object.__setattr__(self, "items", tuple(items))
        object.__setattr__(self, "watchlist_config", watchlist_config)
        object.__setattr__(self, "runner", runner)
        object.__setattr__(self, "budget", budget)
        object.__setattr__(self, "segment", segment)
        object.__setattr__(self, "data_limited", data_limited)
        object.__setattr__(self, "source_outcomes", tuple(source_outcomes))
        object.__setattr__(self, "recent_context", recent_context)
        object.__setattr__(self, "carryover", carryover)
        object.__setattr__(self, "market_anchors", tuple(market_anchors))
        object.__setattr__(self, "generation_policy", generation_policy)
        object.__setattr__(self, "bundle_context", bundle_context)
        object.__setattr__(self, "fact_context_block", fact_context_block)
        object.__setattr__(self, "archive_root", archive_root)
        object.__setattr__(
            self,
            "macro_lineage_all_items",
            None if macro_lineage_all_items is None else tuple(macro_lineage_all_items),
        )


@dataclass(frozen=True, slots=True)
class GenerationResult:
    briefing: Briefing
    macro_lineage: tuple[MacroLineageTrace, ...] = ()


__all__ = [
    "GenerationInput",
    "GenerationResult",
]
