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
from dataclasses import dataclass
from datetime import date

from investo.briefing._core.classification import ClassificationResult
from investo.models import NormalizedItem
from investo.models.macro import is_required_macro_actual


@dataclass(frozen=True, slots=True)
class SectionPlan:
    """Intermediate fed to Stage 2's prompt builder (FD E3)."""

    target_date: date
    items_by_section: dict[int, tuple[NormalizedItem, ...]]
    unassigned: tuple[NormalizedItem, ...]
    required_macro_items: tuple[NormalizedItem, ...] = ()


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

    for section_id in buckets:
        buckets[section_id].sort(key=lambda it: it.published_at, reverse=True)

    unassigned_items = tuple(items_by_id[i] for i in classification.unassigned if i in items_by_id)

    return SectionPlan(
        target_date=target_date,
        items_by_section={k: tuple(v) for k, v in buckets.items()},
        unassigned=unassigned_items,
        required_macro_items=tuple(item for item in items if is_required_macro_actual(item)),
    )


def _required_macro_item_ids(items: Sequence[NormalizedItem]) -> frozenset[int]:
    """Return Stage 1 synthetic ids for required macro actuals."""

    return frozenset(
        idx for idx, item in enumerate(items, start=1) if is_required_macro_actual(item)
    )


__all__ = [
    "SectionPlan",
    "_required_macro_item_ids",
    "build_section_plan",
]
