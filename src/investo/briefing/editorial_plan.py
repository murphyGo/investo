"""Parent-owned v3 eligibility, stable priority and exact protected budget."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime

from investo._internal.event_v3_contract import EventEditionValidationError
from investo.briefing.event_context import build_protected_context_buffer, event_context_refs
from investo.models.event_context import ContextEventDraft, EventContextDocument
from investo.models.event_document import EditorialEventPlan, EditorialPlan
from investo.models.event_identity import CanonicalEventBinding


def build_editorial_plan(
    events: Sequence[ContextEventDraft],
    bindings: Sequence[CanonicalEventBinding],
    documents: Sequence[EventContextDocument],
    *,
    required_item_ids: frozenset[int] = frozenset(),
    reference_item_ids: frozenset[int] = frozenset(),
    observed_at: datetime,
    max_articles: int = 5,
) -> tuple[EditorialPlan, tuple[CanonicalEventBinding, ...], str]:
    if len(events) != len(bindings):
        raise ValueError("edition.selection_mismatch")
    exclusions = []
    eligible = []
    references: set[int] = set()
    seen_ids: set[str] = set()
    for i, (event, binding) in enumerate(zip(events, bindings, strict=True)):
        required = bool(required_item_ids & set(event.item_ids))
        if binding.identity.event_id in seen_ids:
            # A same-run duplicate cannot produce a second article or receipt.
            # Divergent source facts are not silently discarded.
            previous = next(
                b for b in bindings[:i] if b.identity.event_id == binding.identity.event_id
            )
            if {f.fact_id for f in previous.facts} != {f.fact_id for f in binding.facts}:
                raise EventEditionValidationError("event.fact_unsupported")
            continue
        seen_ids.add(binding.identity.event_id)
        reason = None
        if binding.delta.unresolved_conflict_ids or binding.match_outcome == "conflict":
            raise EventEditionValidationError("event.fact_unsupported")
        elif not binding.facts:
            reason = "low_importance"
        elif binding.novelty == "repeat":
            reason = "repeat"
        elif (
            event.timing in {"scheduled", "background"}
            or event.relation
            in {
                "background",
                "unrelated",
            }
            or set(event.item_ids) <= reference_item_ids
        ):
            reason = "background"
        score = (
            {"systemic": 40, "sector": 25, "company": 15, "context": 0}[event.impact]
            + {"new": 20, "material_update": 15, "repeat": 0, "unknown": 0}[binding.novelty]
            + (15 if binding.facts else 5)
            + (15 if event.relation == "direct" else 8)
            + (10 if any(documents[j - 1].source_tier == "official" for j in event.item_ids) else 5)
        )
        if reason is None and score < 45:
            reason = "low_importance"
        if reason in {"repeat", "background"} and binding.facts and event.relation != "unrelated":
            references.add(i)
            exclusions.append((binding.identity.event_id, reason))
            eligible.append((not required, 100 - score, binding.identity.event_id, i))
        elif required and reason is not None:
            raise ValueError("context.required_missing")
        elif reason:
            exclusions.append((binding.identity.event_id, reason))
        else:
            eligible.append((not required, -score, binding.identity.event_id, i))
    ordered = [row[3] for row in sorted(eligible)]
    selected = ordered[:max_articles]
    exclusions.extend(
        (bindings[i].identity.event_id, "budget_deferred") for i in ordered[max_articles:]
    )
    proposed = tuple(events[i] for i in selected)
    protected = build_protected_context_buffer(
        proposed,
        documents,
        required_event_indices=frozenset(
            j for j, event in enumerate(proposed) if required_item_ids & set(event.item_ids)
        ),
        extra_required_refs={
            j: (
                *bindings[i].identity.stage_refs,
                *bindings[i].story_hint.explicit_thread_refs,
                *bindings[i].delta.evidence_refs,
            )
            for j, i in enumerate(selected)
        },
    )
    chosen = tuple(bindings[selected[j]] for j in protected.event_indices)
    plans = tuple(
        EditorialEventPlan(
            event_id=binding.identity.event_id,
            source_event=event,
            placement="reference" if selected[j] in references else "article",
            required_fact_ids=tuple(f.fact_id for f in binding.facts),
            assigned_refs=tuple(
                ref
                for ref in protected.refs
                if ref in event_context_refs(event)
                or ref in binding.identity.stage_refs
                or ref in binding.story_hint.explicit_thread_refs
                or ref in binding.delta.evidence_refs
                or any(
                    ref in point.source_refs
                    for k in event.item_ids
                    for point in (
                        documents[k - 1].time.occurred_at,
                        documents[k - 1].time.announced_at,
                    )
                )
            ),
        )
        for j, (event, binding) in zip(
            protected.event_indices, zip(protected.drafts, chosen, strict=True), strict=True
        )
    )
    exclusions.extend(
        (bindings[selected[j]].identity.event_id, "budget_deferred")
        for j in protected.deferred_event_indices
    )
    payload = json.dumps(
        {
            "context": json.loads(protected.text),
            "events": [
                {
                    "event_id": b.identity.event_id,
                    "fact_ids": [f.fact_id for f in b.facts],
                    "placement": p.placement,
                }
                for p, b in zip(plans, chosen, strict=True)
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    if len(payload.encode("utf-8")) > 16384:
        if max_articles <= 1 or any(
            required_item_ids & set(events[i].item_ids) for i in selected[max_articles - 1 :]
        ):
            raise ValueError("context.budget_exhausted")
        return build_editorial_plan(
            events,
            bindings,
            documents,
            required_item_ids=required_item_ids,
            reference_item_ids=reference_item_ids,
            observed_at=observed_at,
            max_articles=max_articles - 1,
        )
    return (
        EditorialPlan(
            events=plans, exclusions=tuple(exclusions), evidence_bytes=len(payload.encode("utf-8"))
        ),
        chosen,
        payload,
    )
