"""Bounded hash-only receipts for observed event inputs and generation stages."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

from investo.briefing.event_input import is_event_candidate_item, item_evidence_key
from investo.models import NormalizedItem, SourceOutcome
from investo.models.event_quality import EventStage, EventStageReceipt, EventTraceEntry
from investo.models.events import EventSelectionPlan

_TRACE_LIMIT = 512


def input_stage_receipt(
    stage: EventStage,
    items: Sequence[NormalizedItem],
    *,
    excluded_from: Sequence[NormalizedItem] = (),
) -> EventStageReceipt:
    """Count all observed rows; trace only a fixed, explicitly bounded subset."""
    event_items = [item for item in items if is_event_candidate_item(item)]
    keys = {item_evidence_key(item) for item in event_items}
    trace: list[EventTraceEntry] = []
    for item in sorted(event_items, key=item_evidence_key)[:_TRACE_LIMIT]:
        trace.append(_entry(item, stage=stage))
    for item in sorted(excluded_from, key=item_evidence_key):
        if len(trace) >= _TRACE_LIMIT:
            break
        if is_event_candidate_item(item) and item_evidence_key(item) not in keys:
            trace.append(_entry(item, stage=stage, rejected=True))
    return EventStageReceipt(
        stage=stage, status="completed", count=len(event_items), trace=tuple(trace)
    )


def collection_stage_receipt(
    items: Sequence[NormalizedItem], outcomes: Sequence[SourceOutcome]
) -> EventStageReceipt:
    receipt = input_stage_receipt("collected", items)
    event_sources = {item.source_name for item in items if is_event_candidate_item(item)}
    relevant = tuple(
        outcome
        for outcome in outcomes
        if outcome.category in {"news", "earnings"} or outcome.source_name in event_sources
    )
    completed = bool(event_sources) or any(outcome.status != "failed" for outcome in relevant)
    failures = tuple(
        EventTraceEntry(
            hash_id=hashlib.sha256(outcome.source_name.encode()).hexdigest(),
            stage="collected",
            reason="source_unavailable",
            source_name=outcome.source_name
            if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", outcome.source_name)
            else None,
        )
        for outcome in sorted(relevant, key=lambda value: value.source_name)
        if outcome.status == "failed"
    )
    if not completed:
        return EventStageReceipt(
            stage="collected", status="failed", count=None, trace=failures[:_TRACE_LIMIT]
        )
    return receipt.model_copy(update={"trace": (*failures, *receipt.trace)[:_TRACE_LIMIT]})


def selection_stage_receipt(plan: EventSelectionPlan) -> EventStageReceipt:
    return EventStageReceipt(
        stage="selected",
        status="completed",
        count=len(plan.selected),
        trace=(
            *(EventTraceEntry(hash_id=e.event_id, stage="selected") for e in plan.selected),
            *(
                EventTraceEntry(
                    hash_id=e.event_id,
                    stage="selected",
                    reason="evidence_conflict" if e.reason == "unsupported" else e.reason,
                )
                for e in plan.excluded
            ),
        ),
    )


def _entry(item: NormalizedItem, *, stage: EventStage, rejected: bool = False) -> EventTraceEntry:
    return EventTraceEntry(
        hash_id=hashlib.sha256(item_evidence_key(item).encode()).hexdigest(),
        stage=stage,
        reason=("candidate_cap" if stage == "candidate" else "routing_rejected")
        if rejected
        else None,
        source_name=item.source_name
        if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", item.source_name)
        else None,
    )
