"""Operator-only macro event lineage diagnostics for u59.

The builder is pure and intentionally detached from persistence. The
orchestrator can feed it stage-by-stage booleans and then decide where
to write/log the resulting primitive dicts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from investo.models import NormalizedItem
from investo.models.macro import macro_event_key
from investo.models.segments import MarketSegment

MacroLineageDiagnosis = Literal[
    "missing_at_source",
    "dropped_by_segment_routing",
    "dropped_by_stage1_candidate_cap",
    "dropped_by_stage1_classification",
    "dropped_by_stage2_prompt_cap",
    "llm_omitted",
    "published",
]
MacroLineageStage1State = Literal["not_selected", "unassigned", "assigned"]


@dataclass(frozen=True, slots=True)
class MacroLineageSignal:
    """One watched macro event's stage-by-stage pipeline signals."""

    item: NormalizedItem
    collected: bool = True
    routed_segment: MarketSegment | None = None
    selected_stage1_id: int | None = None
    stage1_assignment: int | None = None
    rendered_in_stage2_grouped_sections: bool = False
    rendered_in_lookahead_block: bool = False
    final_body_mentions: bool = False
    final_body_has_source_link: bool = False


@dataclass(frozen=True, slots=True)
class MacroLineageTrace:
    """Primitive-safe operator trace for one watched macro event."""

    event_key: str
    label: str
    source_name: str
    release_id: str | None
    scheduled_date: str | None
    collected: bool
    routed_segment: MarketSegment | None
    selected_for_stage1: bool
    selected_stage1_id: int | None
    stage1_assignment: int | None
    stage1_state: MacroLineageStage1State
    rendered_in_stage2_grouped_sections: bool
    rendered_in_lookahead_block: bool
    final_body_mentions: bool
    final_body_has_source_link: bool
    diagnosis: MacroLineageDiagnosis

    def to_json_dict(self) -> dict[str, object]:
        return {
            "event_key": self.event_key,
            "label": self.label,
            "source_name": self.source_name,
            "release_id": self.release_id,
            "scheduled_date": self.scheduled_date,
            "collected": self.collected,
            "routed_segment": self.routed_segment,
            "selected_for_stage1": self.selected_for_stage1,
            "selected_stage1_id": self.selected_stage1_id,
            "stage1_assignment": self.stage1_assignment,
            "stage1_state": self.stage1_state,
            "rendered_in_stage2_grouped_sections": self.rendered_in_stage2_grouped_sections,
            "rendered_in_lookahead_block": self.rendered_in_lookahead_block,
            "final_body_mentions": self.final_body_mentions,
            "final_body_has_source_link": self.final_body_has_source_link,
            "diagnosis": self.diagnosis,
        }


def build_macro_lineage_traces(
    signals: Sequence[MacroLineageSignal],
    *,
    target_segment: MarketSegment,
) -> tuple[MacroLineageTrace, ...]:
    """Build deterministic per-event lineage traces for one segment."""
    return tuple(_build_trace(signal, target_segment=target_segment) for signal in signals)


def _build_trace(
    signal: MacroLineageSignal,
    *,
    target_segment: MarketSegment,
) -> MacroLineageTrace:
    stage1_state = _stage1_state(signal)
    diagnosis = _diagnose(signal, target_segment=target_segment)
    return MacroLineageTrace(
        event_key=macro_event_key(signal.item) or _fallback_event_key(signal.item),
        label=_label(signal.item),
        source_name=signal.item.source_name,
        release_id=_metadata_str(signal.item.raw_metadata, "release_id"),
        scheduled_date=_metadata_str(signal.item.raw_metadata, "scheduled_date"),
        collected=signal.collected,
        routed_segment=signal.routed_segment,
        selected_for_stage1=signal.selected_stage1_id is not None,
        selected_stage1_id=signal.selected_stage1_id,
        stage1_assignment=signal.stage1_assignment,
        stage1_state=stage1_state,
        rendered_in_stage2_grouped_sections=signal.rendered_in_stage2_grouped_sections,
        rendered_in_lookahead_block=signal.rendered_in_lookahead_block,
        final_body_mentions=signal.final_body_mentions,
        final_body_has_source_link=signal.final_body_has_source_link,
        diagnosis=diagnosis,
    )


def _diagnose(
    signal: MacroLineageSignal,
    *,
    target_segment: MarketSegment,
) -> MacroLineageDiagnosis:
    if not signal.collected:
        return "missing_at_source"
    if signal.routed_segment != target_segment:
        return "dropped_by_segment_routing"
    if signal.selected_stage1_id is None:
        return "dropped_by_stage1_candidate_cap"
    if signal.stage1_assignment is None:
        return "dropped_by_stage1_classification"
    if not (signal.rendered_in_stage2_grouped_sections or signal.rendered_in_lookahead_block):
        return "dropped_by_stage2_prompt_cap"
    if not signal.final_body_mentions or not signal.final_body_has_source_link:
        return "llm_omitted"
    return "published"


def _stage1_state(signal: MacroLineageSignal) -> MacroLineageStage1State:
    if signal.selected_stage1_id is None:
        return "not_selected"
    if signal.stage1_assignment is None:
        return "unassigned"
    return "assigned"


def _fallback_event_key(item: NormalizedItem) -> str:
    return f"{item.source_name}:{item.published_at.isoformat()}:{item.title}"


def _label(item: NormalizedItem) -> str:
    return (
        _metadata_str(item.raw_metadata, "macro_event_label")
        or _metadata_str(item.raw_metadata, "release_name")
        or item.title
    )


def _metadata_str(metadata: Mapping[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, int | float):
        return str(value)
    return None


__all__ = [
    "MacroLineageDiagnosis",
    "MacroLineageSignal",
    "MacroLineageStage1State",
    "MacroLineageTrace",
    "build_macro_lineage_traces",
]
