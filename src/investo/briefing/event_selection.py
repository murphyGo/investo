"""Deterministic event eligibility and exact protected Stage 2 budgeting."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime

from investo.briefing.event_evidence import evidence_lookup, resolve_evidence_ref
from investo.models.events import (
    EventCandidate,
    EventExclusion,
    EventSelectionPlan,
    EvidenceDocument,
    EvidenceRef,
)
from investo.models.segments import MarketSegment

_IMPACT = {"systemic": 40, "sector": 25, "company": 15, "context": 0}
_NOVELTY = {"new": 20, "material_update": 15, "repeat": 0, "unknown": 0}


def event_score(candidate: EventCandidate) -> int:
    return (
        _IMPACT[candidate.impact]
        + _NOVELTY[candidate.novelty]
        + (15 if candidate.evidence_state == "supported" else 5)
        + (15 if candidate.relation == "direct" else 8)
        + (10 if candidate.source_official else 5)
    )


def _excluded_reason(
    candidate: EventCandidate,
    documents: Sequence[EvidenceDocument],
    window_start: datetime,
    window_end: datetime,
) -> str | None:
    lookup = evidence_lookup(documents)
    for ref in candidate.evidence_refs:
        resolve_evidence_ref(ref, lookup)
    if any(
        lookup[(ref.document_id, ref.revision_id)].source_status in {"failed", "unavailable"}
        for ref in candidate.evidence_refs
    ):
        return "source_unavailable"
    if candidate.evidence_state in {"conflicting", "unsupported"}:
        return "evidence_conflict"
    if candidate.relation not in {"direct", "linked"}:
        return "background"
    if candidate.timing in {"scheduled", "background"} or candidate.novelty == "repeat":
        return "background"
    if not window_start <= candidate.published_at < window_end:
        return "outside_window"
    if candidate.timing == "occurred" and (
        candidate.effective_date is not None and candidate.effective_date > window_end.date()
    ):
        return "unsupported"
    if event_score(candidate) < 45:
        return "low_importance"
    return None


def _doc_key(ref: EvidenceRef) -> tuple[str, str]:
    return ref.document_id, ref.revision_id


def _mandatory_keys(candidate: EventCandidate) -> set[tuple[str, str]]:
    refs = (
        *candidate.actor_refs,
        *candidate.action_refs,
        *candidate.object_refs,
        *candidate.relation_refs,
        *candidate.impact_refs,
        *(
            fact.evidence_ref
            for fact in candidate.change_facts
            if fact.fact_id in candidate.required_fact_ids
        ),
    )
    return {_doc_key(ref) for ref in refs}


def _render_block(
    selected: Sequence[EventCandidate],
    documents: Sequence[EvidenceDocument],
) -> str:
    if not selected:
        return ""
    lookup = evidence_lookup(documents)
    refs = sorted(
        {ref for event in selected for ref in event.evidence_refs if _doc_key(ref) in lookup},
        key=lambda ref: (
            ref.document_id,
            ref.revision_id,
            ref.field,
            ref.start,
            ref.end,
        ),
    )
    ref_ids = {ref: index for index, ref in enumerate(refs, start=1)}
    rows: list[dict[str, object]] = []
    for doc in sorted(documents, key=lambda d: (d.document_id, d.revision_id)):
        rows.append(
            {
                "document_id": doc.document_id,
                "revision_id": doc.revision_id,
                "source": doc.source_name,
                "url": doc.url,
                "published_at": doc.published_at.isoformat(),
                "event_time": doc.event_time.isoformat() if doc.event_time else None,
                "time_basis": doc.event_time_basis,
                "spans": [
                    {
                        "id": ref_ids[ref],
                        "field": ref.field,
                        "start": ref.start,
                        "end": ref.end,
                        "text": resolve_evidence_ref(ref, lookup),
                    }
                    for ref in refs
                    if _doc_key(ref) == (doc.document_id, doc.revision_id)
                ],
            }
        )
    events: list[dict[str, object]] = []
    for event in selected:
        events.append(
            {
                "event_id": event.event_id,
                "kind": event.event_kind,
                "timing": event.timing,
                "novelty": event.novelty,
                "evidence_state": event.evidence_state,
                "actor_refs": [ref_ids[r] for r in event.actor_refs],
                "action_refs": [ref_ids[r] for r in event.action_refs],
                "object_refs": [ref_ids[r] for r in event.object_refs],
                "required_fact_ids": event.required_fact_ids,
                "facts": [
                    {
                        "fact_id": f.fact_id,
                        "predicate": f.predicate,
                        "status": f.status,
                        "period": f.period,
                        "unit": f.unit,
                        "ref": ref_ids[f.evidence_ref],
                    }
                    for f in event.change_facts
                    if f.evidence_ref in ref_ids
                ],
            }
        )
    return json.dumps(
        {"events": events, "evidence_rows": rows}, ensure_ascii=False, separators=(",", ":")
    )


def select_events(
    candidates: Sequence[EventCandidate],
    documents: Sequence[EvidenceDocument],
    *,
    segment: MarketSegment,
    window_start: datetime,
    window_end: datetime,
    total_row_budget: int | None = None,
    section_row_budget: int | None = None,
) -> EventSelectionPlan:
    """Reserve all required rows before optional evidence; never drop selected IDs.

    Caller reserves ``evidence_row_count`` from both section 2 and total grouped
    budgets. A document shared by selected events counts once. The exact returned
    block is the prompt payload; renderers must not re-truncate it.
    """
    if window_start.utcoffset() is None or window_end.utcoffset() is None:
        raise ValueError("event observation window must be timezone-aware")
    if window_start >= window_end:
        raise ValueError("event observation window must be non-empty")
    total = 32 if segment == "crypto" else 48
    section = 8 if segment == "crypto" else 14
    for budget in (total_row_budget, section_row_budget):
        if budget is not None and (type(budget) is not int or budget < 0):
            raise ValueError("event row budgets must be non-negative integers")
    row_cap = min(
        total,
        section,
        total if total_row_budget is None else total_row_budget,
        section if section_row_budget is None else section_row_budget,
    )
    lookup = evidence_lookup(documents)
    selected: list[EventCandidate] = []
    exclusions: list[EventExclusion] = []
    keys: set[tuple[str, str]] = set()
    seen: set[str] = set()
    ordered = sorted(
        candidates, key=lambda c: (-event_score(c), -c.published_at.timestamp(), c.event_id)
    )
    for candidate in ordered:
        if candidate.event_id in seen:
            exclusions.append(EventExclusion(event_id=candidate.event_id, reason="duplicate"))
            continue
        seen.add(candidate.event_id)
        reason = _excluded_reason(candidate, documents, window_start, window_end)
        if reason is not None:
            exclusions.append(
                EventExclusion.model_validate({"event_id": candidate.event_id, "reason": reason})
            )
            continue
        proposed_keys = keys | _mandatory_keys(candidate)
        proposed = [*selected, candidate]
        block = _render_block(proposed, [lookup[key] for key in sorted(proposed_keys)])
        if len(selected) >= 5 or len(proposed_keys) > row_cap or len(block.encode("utf-8")) > 8192:
            exclusions.append(EventExclusion(event_id=candidate.event_id, reason="budget_deferred"))
            continue
        selected.append(candidate)
        keys = proposed_keys
    # Only after every selected event's mandatory evidence is safe may optional
    # rows consume remaining bytes/slots. They cannot evict a higher-priority event.
    for candidate in selected:
        optional = sorted({_doc_key(ref) for ref in candidate.evidence_refs} - keys)
        for key in optional:
            proposed_keys = keys | {key}
            block = _render_block(selected, [lookup[k] for k in sorted(proposed_keys)])
            if len(proposed_keys) <= row_cap and len(block.encode("utf-8")) <= 8192:
                keys = proposed_keys
    kept_docs = tuple(lookup[key] for key in sorted(keys))
    block = _render_block(selected, kept_docs)
    return EventSelectionPlan(
        selected=tuple(selected),
        excluded=tuple(exclusions),
        evidence_documents=kept_docs,
        protected_block=block,
        evidence_row_count=len(keys),
        protected_byte_count=len(block.encode("utf-8")),
    )


def render_protected_event_block(plan: EventSelectionPlan) -> str:
    return plan.protected_block
