"""Pure validation and exact-byte accounting for the v3 context boundary."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import ValidationError

from investo.briefing.event_evidence import evidence_document_from_item
from investo.models.event_context import (
    ContextClassificationResult,
    ContextEventDraft,
    ContextFactDraft,
    ContextReason,
    ContextRef,
    ContextRule,
    EventContextDocument,
    EventSupportVector,
)
from investo.models.event_evidence import event_digest, make_event_context_document
from investo.models.items import NormalizedItem

STAGE_ONE_CONTEXT_BYTES = 24 * 1024
STAGE_TWO_CONTEXT_BYTES = 16 * 1024
ContextLookup = Mapping[tuple[str, str], EventContextDocument]


class ContextEvidenceError(ValueError):
    """Only a closed token crosses the exception/log boundary."""

    def __init__(self, rule_code: ContextRule) -> None:
        super().__init__(rule_code)
        self.rule_code = rule_code


def context_lookup(
    documents: Sequence[EventContextDocument],
) -> dict[tuple[str, str], EventContextDocument]:
    result: dict[tuple[str, str], EventContextDocument] = {}
    for doc in documents:
        key = (doc.document_id, doc.revision_id)
        if key in result and result[key] != doc:
            raise ContextEvidenceError("context.buffer_conflict")
        result[key] = doc
    return result


def resolve_context_ref(
    ref: ContextRef, documents: Sequence[EventContextDocument] | ContextLookup
) -> str:
    lookup = documents if isinstance(documents, Mapping) else context_lookup(documents)
    doc = lookup.get((ref.document_id, ref.revision_id))
    if doc is None:
        raise ContextEvidenceError("context.unknown_document")
    if doc.source_status in {"failed", "unavailable"}:
        raise ContextEvidenceError("context.source_unavailable")
    chunk = next((chunk for chunk in doc.chunks if chunk.chunk_id == ref.chunk_id), None)
    if chunk is None:
        raise ContextEvidenceError("context.unknown_chunk")
    if ref.end > len(chunk.text):
        raise ContextEvidenceError("context.span_out_of_bounds")
    text = chunk.text[ref.start : ref.end]
    if not text.strip():
        raise ContextEvidenceError("context.blank_span")
    return text


def fact_context_refs(fact: ContextFactDraft) -> tuple[ContextRef, ...]:
    return tuple(
        dict.fromkeys(
            (
                *fact.subject_refs,
                *fact.predicate_refs,
                *fact.object_refs,
                *fact.metric_refs,
                *fact.value_refs,
                *fact.unit_refs,
                *fact.period_refs,
                *fact.status_refs,
            )
        )
    )


def event_context_refs(
    draft: ContextEventDraft, *, optional: bool = True
) -> tuple[ContextRef, ...]:
    refs = (
        *draft.actor_refs,
        *draft.action_refs,
        *draft.object_refs,
        *draft.relation_refs,
        *draft.impact_refs,
        *(ref for fact in draft.facts for ref in fact_context_refs(fact)),
    )
    if optional:
        refs += (
            *draft.meaning_refs,
            *draft.reaction_refs,
            *draft.background_refs,
            *draft.comparison_refs,
            *draft.follow_up_refs,
        )
    return tuple(dict.fromkeys(refs))


def validate_context_event(
    draft: ContextEventDraft, documents: Sequence[EventContextDocument], *, observed_at: datetime
) -> None:
    if observed_at.utcoffset() is None:
        raise ValueError("context observation must be timezone-aware")
    if max(draft.item_ids) > len(documents):
        raise ContextEvidenceError("context.item_mismatch")
    owners = _validate_owners(draft, documents)
    lookup = context_lookup(documents)
    for ref in event_context_refs(draft):
        if (ref.document_id, ref.revision_id) not in owners:
            raise ContextEvidenceError("context.item_mismatch")
        resolve_context_ref(ref, lookup)
    for fact in draft.facts:
        validate_context_fact(fact, lookup)
    if draft.timing == "occurred":
        for item_id in draft.item_ids:
            for point in (
                documents[item_id - 1].time.occurred_at.value,
                documents[item_id - 1].time.announced_at.value,
            ):
                if point is not None and (
                    point > observed_at
                    if isinstance(point, datetime)
                    else point > observed_at.date()
                ):
                    raise ContextEvidenceError("context.future_occurred")


def _validate_owners(
    draft: ContextEventDraft, documents: Sequence[EventContextDocument]
) -> set[tuple[str, str]]:
    if max(draft.item_ids) > len(documents):
        raise ContextEvidenceError("context.item_mismatch")
    docs = tuple(documents[i - 1] for i in draft.item_ids)
    if any(doc.source_status in {"failed", "unavailable"} for doc in docs):
        raise ContextEvidenceError("context.source_unavailable")
    owners = {(doc.document_id, doc.revision_id) for doc in docs}
    if any((ref.document_id, ref.revision_id) not in owners for ref in event_context_refs(draft)):
        raise ContextEvidenceError("context.item_mismatch")
    return owners


_NUMERIC_TOKEN = re.compile(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
_STATUS_MARKERS = {
    "actual": {"actual", "reported", "실제", "실적", "발표치", "확정"},
    "forecast": {"forecast", "estimate", "estimated", "예상", "전망"},
    "scheduled": {"scheduled", "schedule", "예정"},
    "quoted_opinion": {"quoted_opinion", "opinion", "의견"},
}


def validate_context_fact(fact: ContextFactDraft, documents: ContextLookup) -> None:
    """Validate literal source components; absence never becomes semantic proof."""
    if len({(ref.document_id, ref.revision_id) for ref in fact_context_refs(fact)}) != 1:
        raise ContextEvidenceError("context.item_mismatch")
    for ref in fact_context_refs(fact):
        resolve_context_ref(ref, documents)
    component_fields = {
        "subject_refs": {"fact_subject", "issuer", "company_name"},
        "predicate_refs": {"fact_predicate", "fact_action"},
        "object_refs": {"fact_object", "product_name"},
        "metric_refs": {
            "fact_metric",
            "macro_event_metric",
            "macro_event_key",
            "macro_label",
            "series_id",
        },
        "unit_refs": {"unit", "fact_unit", "macro_event_unit", "macro_unit"},
        "period_refs": {
            "reference_period",
            "macro_release_period",
            "macro_event_period",
            "fact_period",
        },
    }
    for component, allowed in component_fields.items():
        for ref in getattr(fact, component):
            field = metadata_ref_field(ref, documents)
            if field is not None and field not in allowed:
                raise ContextEvidenceError("context.fact_invalid")
    if fact.value_kind == "numeric":
        for ref in fact.value_refs:
            value = unicodedata.normalize("NFKC", resolve_context_ref(ref, documents)).strip()
            if not _NUMERIC_TOKEN.fullmatch(value):
                raise ContextEvidenceError("context.fact_invalid")
    if fact.status_refs:
        for ref in fact.status_refs:
            field = metadata_ref_field(ref, documents)
            if field is None and not any(
                (value.document_id, value.revision_id, value.chunk_id)
                == (ref.document_id, ref.revision_id, ref.chunk_id)
                and max(value.end, ref.end) - min(value.start, ref.start) <= 240
                for value in fact.value_refs
            ):
                raise ContextEvidenceError("context.status_unbound")
            if field is not None and field not in {
                "fact_status",
                "macro_status",
                "macro_event_status",
                "macro_actual_status",
                "macro_forecast_status",
                "macro_consensus_status",
            }:
                raise ContextEvidenceError("context.status_unbound")
        values = {
            resolve_context_ref(ref, documents).strip().casefold() for ref in fact.status_refs
        }
        if not values <= _STATUS_MARKERS[fact.status]:
            raise ContextEvidenceError("context.status_unbound")
    status_fields = {"fact_status", "macro_status", "macro_event_status"}
    for owner_key in {(ref.document_id, ref.revision_id) for ref in fact.value_refs}:
        owner = documents[owner_key]
        fields: dict[str, object] = {}
        for chunk in owner.chunks:
            if chunk.source_locator == "source_metadata":
                fields.update(json.loads(chunk.text))
        values = {
            normalized_numeric_literal(resolve_context_ref(ref, documents))
            for ref in fact.value_refs
            if (ref.document_id, ref.revision_id) == owner_key
        }
        matched_slots = {
            slot
            for slot in ("actual", "forecast", "consensus")
            if f"macro_{slot}" in fields
            and values == {normalized_numeric_literal(str(fields[f"macro_{slot}"]))}
        }
        slot_for_status = (
            {"actual"}
            if fact.status == "actual"
            else {"forecast", "consensus"}
            if fact.status == "forecast"
            else set()
        )
        eligible_slots = matched_slots & slot_for_status
        if eligible_slots:
            statuses = {
                str(fields.get(f"macro_{slot}_status", fields.get("macro_status", "unknown")))
                for slot in eligible_slots
            }
            if fact.status not in statuses or not fact.status_refs:
                raise ContextEvidenceError("context.status_unbound")
            for component in ("metric_refs", "unit_refs", "period_refs"):
                expected_values = {
                    normalized_context_literal(str(fields[key]))
                    for key in component_fields[component]
                    if key in fields
                }
                if expected_values and any(
                    normalized_context_literal(resolve_context_ref(ref, documents))
                    not in expected_values
                    for ref in getattr(fact, component)
                ):
                    raise ContextEvidenceError("context.fact_invalid")
            for ref in fact.status_refs:
                field = metadata_ref_field(ref, documents)
                if field is not None and field not in status_fields | {
                    f"macro_{slot}_status" for slot in eligible_slots
                }:
                    raise ContextEvidenceError("context.status_unbound")
            continue
        if fact.status == "actual" and "macro_actual" in fields:
            raise ContextEvidenceError("context.fact_invalid")
        declared = {str(fields[key]).strip().casefold() for key in status_fields if key in fields}
        if declared and (
            declared != {fact.status}
            or not any(
                (ref.document_id, ref.revision_id) == owner_key
                and metadata_ref_field(ref, documents) in status_fields
                for ref in fact.status_refs
            )
        ):
            raise ContextEvidenceError("context.status_unbound")


def normalized_numeric_literal(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().replace(",", "")


def normalized_context_literal(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def metadata_ref_field(ref: ContextRef, documents: ContextLookup) -> str | None:
    doc = documents[(ref.document_id, ref.revision_id)]
    chunk = next(chunk for chunk in doc.chunks if chunk.chunk_id == ref.chunk_id)
    if chunk.source_locator != "source_metadata":
        return None
    try:
        fields = json.loads(chunk.text)
        for key, value in fields.items():
            prefix = json.dumps(key) + ":"
            encoded = json.dumps(value, ensure_ascii=False)
            text = encoded[1:-1] if isinstance(value, str) else encoded
            start = chunk.text.index(prefix) + len(prefix) + int(isinstance(value, str))
            if (ref.start, ref.end) == (start, start + len(text)):
                return str(key)
    except (ValueError, AttributeError):
        pass
    raise ContextEvidenceError("context.fact_invalid")


def parse_context_classification(
    stdout: str,
    documents: Sequence[EventContextDocument],
    *,
    observed_at: datetime,
    required_item_ids: frozenset[int] = frozenset(),
) -> ContextClassificationResult:
    if len(stdout.encode("utf-8")) > 128 * 1024:
        raise ContextEvidenceError("context.invalid_schema")
    try:
        result = ContextClassificationResult.model_validate_json(stdout)
    except ValidationError:
        raise ContextEvidenceError("context.invalid_schema") from None
    for draft in result.events:
        validate_context_event(draft, documents, observed_at=observed_at)
    assigned = {i for draft in result.events for i in draft.item_ids}
    if not required_item_ids <= assigned:
        raise ContextEvidenceError("context.required_missing")
    for item_id in required_item_ids:
        owner = documents[item_id - 1]
        lookup = context_lookup(documents)
        has_typed_actual = any(
            chunk.source_locator == "source_metadata" and '"macro_actual":' in chunk.text
            for chunk in owner.chunks
        )
        if not any(
            fact.status == "actual"
            and fact.status_refs
            and fact.metric_refs
            and fact.unit_refs
            and fact.period_refs
            and any(ref.document_id == owner.document_id for ref in fact.value_refs)
            and (
                not has_typed_actual
                or any(
                    ref.document_id == owner.document_id
                    and metadata_ref_field(ref, lookup) == "macro_actual"
                    for ref in fact.value_refs
                )
            )
            for draft in result.events
            if item_id in draft.item_ids
            for fact in draft.facts
        ):
            raise ContextEvidenceError("context.required_missing")
    return result


def prepare_context_documents(
    items: Sequence[NormalizedItem], *, received_at: datetime
) -> tuple[EventContextDocument, ...]:
    return tuple(
        make_event_context_document(
            evidence_document_from_item(item, received_at=received_at),
            metadata=item.raw_metadata,
            item=item,
        )
        for item in items
    )


def support_vector(
    draft: ContextEventDraft, documents: Sequence[EventContextDocument], *, baseline_available: bool
) -> EventSupportVector:
    if max(draft.item_ids) > len(documents):
        raise ContextEvidenceError("context.item_mismatch")
    docs = tuple(documents[i - 1] for i in draft.item_ids)
    owners = _validate_owners(draft, documents)
    for ref in event_context_refs(draft):
        if (ref.document_id, ref.revision_id) not in owners:
            raise ContextEvidenceError("context.item_mismatch")
        resolve_context_ref(ref, docs)
    for fact in draft.facts:
        validate_context_fact(fact, context_lookup(docs))
    facts: Literal["complete", "limited", "missing"] = "complete"
    reasons: list[ContextReason] = []
    if not draft.facts:
        facts = "missing"
        reasons.append("facts.required_missing")
    elif any(doc.evidence_budget_limited for doc in docs) or any(
        not fact.status_refs
        or (fact.value_kind == "numeric" and (not fact.unit_refs or not fact.period_refs))
        for fact in draft.facts
    ):
        facts = "limited"
        reasons.append("facts.content_shallow")
    required = {
        "monetary_policy": {"decision"},
        "earnings_result": {"result"},
        "product_service": {"launch", "status_change"},
        "public_statement": {"statement"},
    }.get(draft.event_kind, {"agreement", "result", "status_change", "decision"})
    if draft.facts and not any(
        fact.predicate in required
        and (draft.event_kind != "earnings_result" or fact.status == "actual")
        for fact in draft.facts
    ):
        facts = "limited"
        reasons.append("facts.required_missing")
    points = tuple(point for doc in docs for point in (doc.time.occurred_at, doc.time.announced_at))
    time: Literal["exact", "date", "publication_only", "unknown"] = "unknown"
    if any(point.precision == "exact" for point in points):
        time = "exact"
    elif any(point.precision == "date" for point in points):
        time = "date"
    elif any(doc.time.published_at.precision != "unknown" for doc in docs):
        time = "publication_only"
    if time in {"publication_only", "unknown"}:
        reasons.append("time.event_unknown")
    if not baseline_available:
        reasons.append("history.unavailable")
    locator: Literal["complete", "missing"] = (
        "complete" if all(doc.url for doc in docs) else "missing"
    )
    if locator == "missing":
        reasons.append("source.locator_missing")
    if not draft.meaning_refs:
        reasons.append("meaning.ref_missing")
    if not draft.reaction_refs:
        reasons.append("reaction.ref_missing")
    return EventSupportVector(
        facts=facts,
        time=time,
        novelty="known" if baseline_available else "unknown",
        locator=locator,
        reason_codes=tuple(reasons),
    )


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class ContextPromptBuffer:
    text: str
    documents: tuple[EventContextDocument, ...]
    item_ids: tuple[int, ...]
    deferred_item_ids: tuple[int, ...]
    required_prompt_item_ids: frozenset[int]


def build_context_prompt_buffer(
    documents: Sequence[EventContextDocument], *, required_item_ids: frozenset[int] = frozenset()
) -> ContextPromptBuffer:
    """Reserve required source rows; count IDs, headers, time and all chunk bytes."""
    if len(documents) > 96 or any(not 1 <= i <= len(documents) for i in required_item_ids):
        raise ContextEvidenceError("context.budget_exhausted")
    ordered = sorted(range(1, len(documents) + 1), key=lambda i: (i not in required_item_ids, i))
    rows: list[dict[str, object]] = []
    selected: list[int] = []
    counts: Counter[str] = Counter()
    for i in ordered:
        source = documents[i - 1].source_name
        if counts[source] >= 24:
            if i in required_item_ids:
                raise ContextEvidenceError("context.budget_exhausted")
            continue
        row = {"item_id": len(rows) + 1, "context": documents[i - 1].model_dump(mode="json")}
        proposed = _json({"schema_version": 3, "documents": [*rows, row]})
        if len(proposed.encode("utf-8")) > STAGE_ONE_CONTEXT_BYTES:
            if i in required_item_ids:
                raise ContextEvidenceError("context.budget_exhausted")
            continue
        rows.append(row)
        selected.append(i)
        counts[source] += 1
    return ContextPromptBuffer(
        text=_json({"schema_version": 3, "documents": rows}),
        documents=tuple(documents[i - 1] for i in selected),
        item_ids=tuple(selected),
        deferred_item_ids=tuple(i for i in range(1, len(documents) + 1) if i not in selected),
        required_prompt_item_ids=frozenset(
            n + 1 for n, i in enumerate(selected) if i in required_item_ids
        ),
    )


@dataclass(frozen=True, slots=True)
class ProtectedContextBuffer:
    text: str
    event_indices: tuple[int, ...]
    deferred_event_indices: tuple[int, ...]
    refs: tuple[ContextRef, ...]
    drafts: tuple[ContextEventDraft, ...]


def build_protected_context_buffer(
    drafts: Sequence[ContextEventDraft],
    documents: Sequence[EventContextDocument],
    *,
    required_event_indices: frozenset[int] = frozenset(),
) -> ProtectedContextBuffer:
    """Whole-event deferral, optional-role pruning; never trim required spans."""
    if len(drafts) > 5 or any(not 0 <= i < len(drafts) for i in required_event_indices):
        raise ContextEvidenceError("context.budget_exhausted")
    lookup = context_lookup(documents)
    selected: dict[int, ContextEventDraft] = {}
    refs_by_event: dict[int, tuple[ContextRef, ...]] = {}
    optional_fields = (
        "meaning_refs",
        "reaction_refs",
        "background_refs",
        "comparison_refs",
        "follow_up_refs",
    )

    def payload() -> tuple[str, tuple[ContextRef, ...]]:
        spans: dict[str, dict[str, object]] = {}
        rows: list[dict[str, object]] = []
        all_refs: list[ContextRef] = []
        for index in sorted(selected):
            refs = refs_by_event[index]
            ids: list[str] = []
            for ref in refs:
                key = event_digest(ref.model_dump(mode="json"))[:24]
                ids.append(key)
                spans[key] = {
                    "ref": ref.model_dump(mode="json"),
                    "text": resolve_context_ref(ref, lookup),
                }
            rows.append(
                {
                    "event_index": index,
                    "draft": selected[index].model_dump(mode="json"),
                    "ref_ids": ids,
                }
            )
            all_refs.extend(refs)
        return _json({"schema_version": 3, "events": rows, "spans": spans}), tuple(
            dict.fromkeys(all_refs)
        )

    # Reserve essential identity, facts and source times for all mandatory events
    # before any optional evidence can spend the shared budget.
    for index in sorted(range(len(drafts)), key=lambda i: (i not in required_event_indices, i)):
        draft = drafts[index]
        _validate_owners(draft, documents)
        for fact in draft.facts:
            validate_context_fact(fact, lookup)
        essential = tuple(
            dict.fromkeys(
                (
                    *event_context_refs(draft, optional=False),
                    *(
                        ref
                        for i in draft.item_ids
                        for point in (
                            documents[i - 1].time.occurred_at,
                            documents[i - 1].time.announced_at,
                        )
                        for ref in point.source_refs
                    ),
                )
            )
        )
        selected[index] = draft.model_copy(update={name: () for name in optional_fields})
        refs_by_event[index] = essential
        if len(payload()[0].encode("utf-8")) > STAGE_TWO_CONTEXT_BYTES:
            del selected[index]
            del refs_by_event[index]
            if index in required_event_indices:
                raise ContextEvidenceError("context.budget_exhausted")

    # Preserve meaning and reaction before spending bytes on lower-priority roles.
    for name in optional_fields:
        for index in sorted(selected):
            for ref in getattr(drafts[index], name):
                previous = selected[index]
                old_refs = refs_by_event[index]
                selected[index] = previous.model_copy(
                    update={name: (*getattr(previous, name), ref)}
                )
                refs_by_event[index] = tuple(dict.fromkeys((*old_refs, ref)))
                if len(payload()[0].encode("utf-8")) > STAGE_TWO_CONTEXT_BYTES:
                    selected[index] = previous
                    refs_by_event[index] = old_refs
    text, retained_refs = payload()
    return ProtectedContextBuffer(
        text=text,
        event_indices=tuple(sorted(selected)),
        deferred_event_indices=tuple(i for i in range(len(drafts)) if i not in selected),
        refs=retained_refs,
        drafts=tuple(selected[i] for i in sorted(selected)),
    )
