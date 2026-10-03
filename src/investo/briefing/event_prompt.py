"""One selection/accounting path for v2 evidence and later synthesis consumers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from investo.briefing._assembly.markdown_render import (
    _render_grouped_sections,
    _render_unassigned,
    _sort_for_story,
)
from investo.briefing._core.classification import EventClassificationResult
from investo.briefing._core.section_planning import SectionPlan
from investo.briefing.event_evidence import build_event_candidates
from investo.briefing.event_input import item_evidence_key
from investo.briefing.event_selection import select_events
from investo.models import NormalizedItem
from investo.models.events import EventIdentityReceipt, EventSelectionPlan, EvidenceDocument
from investo.models.segments import MarketSegment


@dataclass(frozen=True, slots=True)
class EventPromptEvidence:
    event_plan: EventSelectionPlan
    grouped_sections: str
    unassigned: str
    row_count: int
    section_two_row_count: int
    prompted_items: tuple[NormalizedItem, ...]


def prepare_event_selection(
    classification: EventClassificationResult,
    items: Sequence[NormalizedItem],
    documents: Sequence[EvidenceDocument],
    *,
    observed_at: datetime,
    window_start: datetime,
    window_end: datetime,
    segment: MarketSegment,
    baseline: Sequence[EventIdentityReceipt] = (),
    baseline_available: bool = True,
) -> EventSelectionPlan:
    candidates = build_event_candidates(
        classification.events,
        items,
        documents,
        observed_at=observed_at,
        baseline=baseline,
        baseline_available=baseline_available,
    )
    return select_events(
        candidates,
        documents,
        segment=segment,
        window_start=window_start,
        window_end=window_end,
    )


def render_event_prompt_evidence(
    plan: SectionPlan,
    events: EventSelectionPlan,
    items: Sequence[NormalizedItem],
    documents: Sequence[EvidenceDocument],
    *,
    segment: MarketSegment | None,
) -> EventPromptEvidence:
    """Reserve real evidence rows, then fill grouped/unassigned without duplicates."""
    if len(items) != len(documents):
        raise ValueError("event evidence requires item-aligned document buffers")
    total_limit, section_limit = (32, 8) if segment == "crypto" else (48, 14)
    if events.evidence_row_count > min(total_limit, section_limit):
        raise ValueError("event plan exceeds synthesis evidence budget")
    document_keys = {
        item_evidence_key(item): (doc.document_id, doc.revision_id)
        for item, doc in zip(items, documents, strict=True)
    }
    used = {(d.document_id, d.revision_id) for d in events.evidence_documents}
    available = set(document_keys.values())
    if not used <= available:
        raise ValueError("event plan includes evidence outside the transmitted input")
    remaining = total_limit - events.evidence_row_count
    grouped: dict[int, tuple[NormalizedItem, ...]] = {}
    for section in (2, 3, 4, 5):
        limit = min(remaining, section_limit - (events.evidence_row_count if section == 2 else 0))
        rows: list[NormalizedItem] = []
        for item in _sort_for_story(
            plan.items_by_section.get(section, ()), story_metadata=plan.story_metadata
        ):
            if len(rows) >= limit:
                break
            key = document_keys[item_evidence_key(item)]
            if key not in used:
                used.add(key)
                rows.append(item)
        grouped[section] = tuple(rows)
        remaining -= len(rows)
    unassigned: list[NormalizedItem] = []
    for item in plan.unassigned:
        if len(unassigned) >= min(remaining, 4 if segment == "crypto" else 8):
            break
        key = document_keys[item_evidence_key(item)]
        if key not in used:
            used.add(key)
            unassigned.append(item)
    return EventPromptEvidence(
        event_plan=events,
        grouped_sections=_render_grouped_sections(
            grouped, story_metadata=plan.story_metadata, segment=segment
        ),
        unassigned=_render_unassigned(tuple(unassigned), segment=segment),
        row_count=len(used),
        section_two_row_count=events.evidence_row_count + len(grouped[2]),
        prompted_items=tuple(
            item for item in items if document_keys[item_evidence_key(item)] in used
        ),
    )
