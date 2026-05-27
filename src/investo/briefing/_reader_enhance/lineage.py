"""Macro-lineage signal extraction from pipeline state (u59).

These helpers compute the stage-by-stage booleans that the existing
:mod:`investo.briefing.lineage` trace *builder* consumes. They are
pipeline-coupled (they read ``ClassificationResult`` / ``SectionPlan`` /
the selected llm-items + final markdown), so they live adjacent to the
pipeline rather than in the pure trace builder.

Moved verbatim from ``briefing/pipeline.py`` in the u83 decomposition;
behavior-preserving (move-only).
"""

from __future__ import annotations

from collections.abc import Sequence

from investo.briefing._assembly.markdown_render import _grouped_stage2_rendered_items
from investo.briefing._core.classification import ClassificationResult
from investo.briefing._core.section_planning import SectionPlan
from investo.briefing.lineage import MacroLineageSignal
from investo.briefing.segments import (
    MarketSegment,
    SegmentedItems,
    filter_lookahead_items,
    segment_items,
)
from investo.models import NormalizedItem
from investo.models.macro import macro_event_key


def _macro_lineage_signals_for_segment(
    *,
    all_items: Sequence[NormalizedItem],
    llm_items: Sequence[NormalizedItem],
    classification: ClassificationResult,
    plan: SectionPlan,
    segment: MarketSegment,
    final_markdown: str,
) -> tuple[MacroLineageSignal, ...]:
    routed = segment_items(all_items)
    grouped_rendered = _grouped_stage2_rendered_items(plan, segment=segment)
    lookahead_rendered = filter_lookahead_items(llm_items)
    signals: list[MacroLineageSignal] = []
    for item in all_items:
        if macro_event_key(item) is None:
            continue
        routed_segment = _lineage_routed_segment(item, routed, preferred_segment=segment)
        selected_id = _lineage_item_id(item, llm_items)
        stage1_assignment = (
            classification.assignments.get(selected_id) if selected_id is not None else None
        )
        signals.append(
            MacroLineageSignal(
                item=item,
                collected=True,
                routed_segment=routed_segment,
                selected_stage1_id=selected_id,
                stage1_assignment=stage1_assignment,
                rendered_in_stage2_grouped_sections=_lineage_contains_item(item, grouped_rendered)
                or _lineage_contains_item(item, plan.required_macro_items),
                rendered_in_lookahead_block=_lineage_contains_item(item, lookahead_rendered),
                final_body_mentions=_lineage_body_mentions(item, final_markdown),
                final_body_has_source_link=_lineage_body_has_source_link(item, final_markdown),
            )
        )
    return tuple(signals)


def _lineage_routed_segment(
    item: NormalizedItem,
    routed: SegmentedItems,
    *,
    preferred_segment: MarketSegment,
) -> MarketSegment | None:
    all_segments: tuple[MarketSegment, ...] = ("domestic-equity", "us-equity", "crypto")
    ordered_segments = (
        preferred_segment,
        *(segment for segment in all_segments if segment != preferred_segment),
    )
    for segment in ordered_segments:
        if _lineage_contains_item(item, routed.for_segment(segment)):
            return segment
    return None


def _lineage_item_id(
    item: NormalizedItem,
    items: Sequence[NormalizedItem],
) -> int | None:
    for idx, candidate in enumerate(items, start=1):
        if candidate is item or candidate == item:
            return idx
    return None


def _lineage_contains_item(
    item: NormalizedItem,
    items: Sequence[NormalizedItem],
) -> bool:
    return _lineage_item_id(item, items) is not None


def _lineage_body_mentions(item: NormalizedItem, markdown: str) -> bool:
    candidates = [
        macro_event_key(item),
        item.raw_metadata.get("macro_event_label"),
        item.raw_metadata.get("release_name"),
        item.title,
    ]
    return any(isinstance(candidate, str) and candidate in markdown for candidate in candidates)


def _lineage_body_has_source_link(item: NormalizedItem, markdown: str) -> bool:
    if item.url is not None and str(item.url) in markdown:
        return True
    return item.source_name in markdown


__all__ = [
    "_lineage_body_has_source_link",
    "_lineage_body_mentions",
    "_lineage_contains_item",
    "_lineage_item_id",
    "_lineage_routed_segment",
    "_macro_lineage_signals_for_segment",
]
