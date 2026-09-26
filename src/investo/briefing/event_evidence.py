"""Pure normalization, span validation, and canonical event construction."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import cast
from urllib.parse import unquote_plus, urlsplit, urlunsplit

from investo.models.events import (
    EventCandidate,
    EventCandidateDraft,
    EventFact,
    EventIdentityReceipt,
    EventNovelty,
    EvidenceDocument,
    EvidenceRef,
    EvidenceState,
    FactPredicate,
)
from investo.models.items import NormalizedItem
from investo.models.macro import macro_event_key

EvidenceLookup = Mapping[tuple[str, str], EvidenceDocument]


def event_digest(*values: object) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_evidence_url(url: str | None) -> str | None:
    """Remove fragments/tracking only; preserve meaningful query ordering."""
    if url is None:
        return None
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username:
        raise ValueError("event evidence URL must be a public HTTP source locator")
    query = "&".join(
        part
        for part in parsed.query.split("&")
        if not unquote_plus(part.split("=", 1)[0]).casefold().startswith("utm_")
    )
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def _normal(value: str) -> str:
    return unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n")


def _aware(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("event clock must be timezone-aware")
    return value.astimezone(UTC)


def make_evidence_document(
    *,
    source_name: str,
    title: str,
    summary: str = "",
    detail_excerpt: str = "",
    url: str | None = None,
    published_at: datetime,
    received_at: datetime,
    published_date: date | None = None,
    event_time: date | datetime | None = None,
    event_time_basis: str = "unknown",
    source_tier: str = "unknown",
    source_status: str = "ok",
) -> EvidenceDocument:
    """Build source-owned evidence before prompt bounding; never infer event time."""
    canonical_url = canonical_evidence_url(url)
    identity = canonical_url or (title, _aware(published_at).isoformat())
    title, summary, detail_excerpt = map(_normal, (title, summary, detail_excerpt))
    return EvidenceDocument.model_validate(
        {
            "document_id": event_digest(source_name, identity),
            "revision_id": event_digest(title, summary, detail_excerpt),
            "source_name": source_name,
            "url": canonical_url,
            "published_at": published_at,
            "published_date": published_date,
            "received_at": received_at,
            "event_time": event_time,
            "event_time_basis": event_time_basis,
            "source_tier": source_tier,
            "source_status": source_status,
            "title": title,
            "summary": summary,
            "detail_excerpt": detail_excerpt,
        }
    )


def evidence_document_from_item(item: NormalizedItem, *, received_at: datetime) -> EvidenceDocument:
    """Validate attached evidence, or construct a limited title/summary fallback."""
    attached = cast(EvidenceDocument | None, getattr(item, "event_evidence", None))
    url = str(item.url) if item.url is not None else None
    publication_day: date | None = None
    event_day: date | None = None
    if item.raw_metadata.get("published_at_precision") == "date":
        try:
            raw_day = item.raw_metadata["published_date"]
            if not isinstance(raw_day, str):
                raise ValueError("source date must be text")
            publication_day = date.fromisoformat(raw_day)
            if item.raw_metadata.get("event_time_basis") == "source_date":
                raw_event_day = item.raw_metadata["event_date"]
                if not isinstance(raw_event_day, str):
                    raise ValueError("source event date must be text")
                event_day = date.fromisoformat(raw_event_day)
        except (KeyError, TypeError, ValueError):
            raise ValueError("date precision evidence requires a valid source date") from None
    fallback = make_evidence_document(
        source_name=item.source_name,
        title=item.title,
        summary=item.summary or "",
        url=url,
        published_at=item.published_at,
        received_at=received_at,
        published_date=publication_day,
        event_time=event_day,
        event_time_basis="source_date" if event_day is not None else "unknown",
        source_tier=(
            "official"
            if item.raw_metadata.get("official_source") == "true"
            else "primary"
            if item.raw_metadata.get("source_tier") == "primary"
            else "unknown"
        ),
    )
    if attached is None:
        return fallback
    if (
        attached.source_name != item.source_name
        or attached.document_id != fallback.document_id
        or attached.url != fallback.url
        or attached.published_at != item.published_at
        or attached.published_date != publication_day
        or attached.revision_id
        != event_digest(attached.title, attached.summary, attached.detail_excerpt)
    ):
        raise ValueError("event evidence does not match its routed source item")
    return attached


def _truncate_ascii(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 3] + "..."


def prepare_evidence_documents(
    items: Sequence[NormalizedItem],
    *,
    received_at: datetime,
) -> tuple[EvidenceDocument, ...]:
    """Return item-aligned exact Stage 1 buffers under the shared 24KiB detail cap.

    Allocation order is stable across input permutations. Each distinct document
    revision consumes the detail budget once, even when routed more than once.
    """
    docs = tuple(evidence_document_from_item(item, received_at=received_at) for item in items)
    lookup = evidence_lookup(docs)
    remaining = 24 * 1024
    bounded: dict[tuple[str, str], EvidenceDocument] = {}
    for key, doc in sorted(
        lookup.items(),
        key=lambda pair: (
            -pair[1].published_at.timestamp(),
            pair[1].source_name,
            *pair[0],
        ),
    ):
        detail = doc.detail_excerpt[:1200].encode("utf-8")[:remaining].decode("utf-8", "ignore")
        remaining -= len(detail.encode("utf-8"))
        title = _truncate_ascii(doc.title, 180)
        summary = _truncate_ascii(doc.summary, 320)
        bounded[key] = doc.model_copy(
            update={
                "title": title,
                "summary": summary,
                "detail_excerpt": detail,
                "revision_id": event_digest(title, summary, detail),
                "origin_revision_id": doc.origin_revision_id or doc.revision_id,
                "evidence_budget_limited": doc.evidence_budget_limited
                or ((title, summary, detail) != (doc.title, doc.summary, doc.detail_excerpt)),
            }
        )
    return tuple(bounded[(doc.document_id, doc.revision_id)] for doc in docs)


def evidence_lookup(
    documents: Sequence[EvidenceDocument],
) -> dict[tuple[str, str], EvidenceDocument]:
    result: dict[tuple[str, str], EvidenceDocument] = {}
    for doc in documents:
        key = (doc.document_id, doc.revision_id)
        if key in result and result[key] != doc:
            raise ValueError("conflicting evidence buffers for the same document revision")
        result[key] = doc
    return result


def resolve_evidence_ref(
    ref: EvidenceRef,
    documents: Sequence[EvidenceDocument] | EvidenceLookup,
) -> str:
    lookup = documents if isinstance(documents, Mapping) else evidence_lookup(documents)
    doc = lookup.get((ref.document_id, ref.revision_id))
    if doc is None:
        raise ValueError("event reference has an unknown document or revision")
    buffer = cast(str, getattr(doc, ref.field))
    if ref.end > len(buffer):
        raise ValueError("event span exceeds the transmitted evidence buffer")
    quote = buffer[ref.start : ref.end]
    if not quote.strip():
        raise ValueError("event evidence span must not be whitespace-only")
    return quote


def _refs(draft: EventCandidateDraft) -> tuple[EvidenceRef, ...]:
    refs = (
        *draft.actor_refs,
        *draft.action_refs,
        *draft.object_refs,
        *draft.relation_refs,
        *draft.impact_refs,
        *(fact.evidence_ref for fact in draft.facts),
    )
    return tuple(sorted(set(refs), key=_ref_sort_key))


def _ref_sort_key(ref: EvidenceRef) -> tuple[str, str, str, int, int]:
    return ref.document_id, ref.revision_id, ref.field, ref.start, ref.end


def required_fact_ids(event_kind: str, facts: Sequence[EventFact]) -> tuple[str, ...]:
    """Recompute E10 requirements; a model cannot omit required IDs."""
    predicates: set[FactPredicate]
    if event_kind == "monetary_policy":
        predicates = {"decision"}
    elif event_kind == "earnings_result":
        predicates = {"result", "guidance"}
    elif event_kind == "product_service":
        predicates = {"launch", "status_change"}
    elif event_kind == "public_statement":
        predicates = {"statement"}
    else:
        predicates = {"agreement", "result", "status_change"}
    return tuple(
        f.fact_id
        for f in facts
        if f.predicate in predicates or (event_kind == "earnings_result" and f.status == "actual")
    )


def _span_key(refs: Sequence[EvidenceRef], lookup: EvidenceLookup) -> str:
    return "|".join(
        sorted({_normal(resolve_evidence_ref(ref, lookup)).strip().casefold() for ref in refs})
    )


def _date_of(doc: EvidenceDocument) -> date | None:
    if isinstance(doc.event_time, datetime):
        return doc.event_time.astimezone(UTC).date()
    return doc.event_time


def _recent_receipts(
    baseline: Sequence[EventIdentityReceipt],
    observed_at: datetime,
) -> tuple[EventIdentityReceipt, ...]:
    return tuple(
        r for r in baseline if observed_at - timedelta(days=7) <= r.published_at <= observed_at
    )


def _match_receipt(
    *,
    key_hash: str,
    semantic_hash: str,
    official_hashes: tuple[str, ...],
    document_aliases: tuple[str, ...],
    effective_date: date | None,
    baseline: Sequence[EventIdentityReceipt],
) -> EventIdentityReceipt | None:
    matches: list[EventIdentityReceipt] = []
    for receipt in baseline:
        official_match = bool(set(official_hashes) & set(receipt.official_key_hashes))
        semantic_match = receipt.semantic_key_hash == semantic_hash
        dates_conflict = (
            receipt.effective_date is not None
            and effective_date is not None
            and receipt.effective_date != effective_date
        )
        if official_match and (not semantic_match or dates_conflict):
            raise ValueError("event identity_conflict: official alias has a conflicting tuple")
        document_match = (
            bool(set(document_aliases) & set(receipt.document_aliases))
            and semantic_match
            and not dates_conflict
        )
        if receipt.event_key_hash == key_hash or official_match or document_match:
            matches.append(receipt)
    if len({r.event_id for r in matches}) > 1:
        raise ValueError("event identity_conflict: baseline canonical IDs disagree")
    if not matches:
        return None
    latest = max(matches, key=lambda r: (r.published_at, r.event_key_hash))
    return latest.model_copy(
        update={
            name: tuple(sorted({value for receipt in matches for value in getattr(receipt, name)}))
            for name in (
                "official_key_hashes",
                "document_aliases",
                "revision_hashes",
            )
        }
    )


def _novelty(
    fact_hashes: Sequence[str],
    *,
    event_id: str,
    baseline: Sequence[EventIdentityReceipt],
    baseline_available: bool,
) -> EventNovelty:
    """Compare the complete current fact set to committed canonical history."""
    if not baseline_available:
        return "unknown"
    previous = [receipt for receipt in baseline if receipt.event_id == event_id]
    if not previous:
        return "new"
    known = {value for receipt in previous for value in receipt.fact_hashes}
    return "repeat" if set(fact_hashes) <= known else "material_update"


def _unique_facts(facts: Sequence[EventFact]) -> tuple[EventFact, ...]:
    """Collapse identical facts, never choose between conflicting interpretations."""
    unique: dict[str, EventFact] = {}
    for fact in facts:
        existing = unique.get(fact.fact_id)
        if existing is not None and existing != fact:
            raise ValueError("event fact_conflict: same fact ID has conflicting payloads")
        unique[fact.fact_id] = fact
    return tuple(unique[key] for key in sorted(unique))


def build_event_candidates(
    drafts: Sequence[EventCandidateDraft],
    items: Sequence[NormalizedItem],
    documents: Sequence[EvidenceDocument],
    *,
    observed_at: datetime,
    baseline: Sequence[EventIdentityReceipt] = (),
    baseline_available: bool = True,
) -> tuple[EventCandidate, ...]:
    """Validate bounded Stage 1 proposals against their exact same-run sources."""
    if len(drafts) > 12 or len(items) != len(documents):
        raise ValueError("event drafts/items exceed the aligned Stage 1 contract")
    now = _aware(observed_at)
    lookup = evidence_lookup(documents)
    recent = _recent_receipts(baseline, now) if baseline_available else ()
    candidates = [
        _build_candidate(d, items, documents, lookup, now, recent, baseline_available)
        for d in drafts
    ]
    # Identical drafts collapse; uncertain cross-document tuples retain distinct
    # IDs. Same canonical ID with conflicting semantic content is never merged.
    grouped: dict[str, EventCandidate] = {}
    for candidate in sorted(
        candidates,
        key=lambda c: (
            c.event_id,
            c.document_aliases,
            c.fact_hashes,
            c.model_dump_json(),
        ),
    ):
        old = grouped.get(candidate.event_id)
        if old is None:
            grouped[candidate.event_id] = candidate
        else:
            grouped[candidate.event_id] = _merge_candidates(
                old, candidate, baseline=recent, baseline_available=baseline_available
            )
    return tuple(grouped[key] for key in sorted(grouped))


def _build_candidate(
    draft: EventCandidateDraft,
    items: Sequence[NormalizedItem],
    documents: Sequence[EvidenceDocument],
    lookup: EvidenceLookup,
    now: datetime,
    baseline: Sequence[EventIdentityReceipt],
    baseline_available: bool,
) -> EventCandidate:
    if any(i > len(items) for i in draft.item_ids):
        raise ValueError("event item_id is outside the same-run item set")
    owned = tuple(documents[i - 1] for i in draft.item_ids)
    owned_keys = {(doc.document_id, doc.revision_id) for doc in owned}
    refs = _refs(draft)
    if any((r.document_id, r.revision_id) not in owned_keys for r in refs):
        raise ValueError("event reference does not belong to its item_ids")
    for ref in refs:
        resolve_evidence_ref(ref, lookup)
    if draft.relation in {"direct", "linked"} and not draft.relation_refs:
        raise ValueError("event relation requires source evidence")
    if draft.impact != "context" and not draft.impact_refs:
        raise ValueError("event impact requires source evidence")
    if draft.event_kind == "product_service" and not draft.object_refs:
        raise ValueError("product event identity requires an object")
    dates = {_date_of(doc) for doc in owned if _date_of(doc) is not None}
    if len(dates) > 1:
        raise ValueError("event identity_conflict: source event dates disagree")
    effective_date = next(iter(dates), None)
    if draft.timing == "occurred" and (
        (effective_date is not None and effective_date > now.date())
        or any(isinstance(doc.event_time, datetime) and doc.event_time > now for doc in owned)
        or any(
            items[i - 1].scheduled_at is not None
            and cast(datetime, items[i - 1].scheduled_at) > now
            for i in draft.item_ids
        )
        or any(f.status == "scheduled" for f in draft.facts)
    ):
        raise ValueError("future scheduled evidence cannot be an occurred event")
    actor = _span_key(draft.actor_refs, lookup)
    action = _span_key(draft.action_refs, lookup)
    object_key = _span_key(draft.object_refs, lookup)
    semantic_hash = event_digest(actor, action, object_key)
    aliases = tuple(sorted({doc.document_id for doc in owned}))
    official_keys = tuple(
        sorted(
            {
                event_digest(key)
                for i in draft.item_ids
                if (key := macro_event_key(items[i - 1])) is not None
            }
        )
    )
    # Known dates, rather than an "official" source's arrival, establish ID.
    discriminator = (
        effective_date.isoformat()
        if effective_date
        else official_keys[0]
        if official_keys
        else aliases[0]
    )
    key_hash = event_digest(actor, action, object_key, discriminator)
    previous = _match_receipt(
        key_hash=key_hash,
        semantic_hash=semantic_hash,
        official_hashes=official_keys,
        document_aliases=aliases,
        effective_date=effective_date,
        baseline=baseline,
    )
    event_id = previous.event_id if previous else key_hash[:24]
    facts: list[EventFact] = []
    fact_hashes: list[str] = []
    for fact in draft.facts:
        value = resolve_evidence_ref(fact.evidence_ref, lookup)
        doc = lookup[(fact.evidence_ref.document_id, fact.evidence_ref.revision_id)]
        corpus = " ".join((doc.title, doc.summary, doc.detail_excerpt))
        if any(label is not None and label not in corpus for label in (fact.period, fact.unit)):
            raise ValueError("event fact period/unit must be present in its source")
        fact_hashes.append(event_digest(fact.predicate, value, fact.status, fact.period, fact.unit))
        facts.append(
            EventFact(
                fact_id=event_digest(event_id, fact.predicate, fact.evidence_ref.model_dump()),
                predicate=fact.predicate,
                evidence_ref=fact.evidence_ref,
                value_text=value,
                status=fact.status,
                period=fact.period,
                unit=fact.unit,
            )
        )
    # Duplicate fact references cannot inflate completion/accounting.
    unique_facts = _unique_facts(facts)
    required = required_fact_ids(draft.event_kind, unique_facts)
    state: EvidenceState = draft.evidence_state
    if state == "supported" and (
        not required
        or not any(d.summary.strip() or d.detail_excerpt.strip() for d in owned)
        or effective_date is None
        or draft.timing == "unknown"
        or not baseline_available
    ):
        state = "detail_limited"
    hashes = tuple(sorted(set(fact_hashes)))
    novelty = _novelty(
        hashes,
        event_id=event_id,
        baseline=baseline,
        baseline_available=baseline_available,
    )
    return EventCandidate(
        event_id=event_id,
        event_key_hash=key_hash,
        semantic_key_hash=semantic_hash,
        event_kind=draft.event_kind,
        evidence_refs=refs,
        actor_refs=draft.actor_refs,
        action_refs=draft.action_refs,
        object_refs=draft.object_refs,
        relation_refs=draft.relation_refs,
        impact_refs=draft.impact_refs,
        change_facts=unique_facts,
        required_fact_ids=required,
        timing=draft.timing,
        relation=draft.relation,
        impact=draft.impact,
        novelty=novelty,
        evidence_state=state,
        published_at=max(d.published_at for d in owned),
        effective_date=effective_date,
        official_key_hashes=tuple(
            sorted(set(official_keys) | set(previous.official_key_hashes if previous else ()))
        ),
        document_aliases=tuple(
            sorted(set(aliases) | set(previous.document_aliases if previous else ()))
        ),
        revision_hashes=tuple(
            sorted(
                {d.origin_revision_id or d.revision_id for d in owned}
                | set(previous.revision_hashes if previous else ())
            )
        ),
        fact_hashes=hashes,
        source_official=any(d.source_tier == "official" for d in owned),
        selection_reason="source_backed_event" if state == "supported" else state,
    )


def _merge_candidates(
    left: EventCandidate,
    right: EventCandidate,
    *,
    baseline: Sequence[EventIdentityReceipt],
    baseline_available: bool,
) -> EventCandidate:
    if (
        left.semantic_key_hash != right.semantic_key_hash
        or (
            left.effective_date is not None
            and right.effective_date is not None
            and left.effective_date != right.effective_date
        )
        or left.event_kind != right.event_kind
    ):
        raise ValueError("event identity_conflict: proposed tuples disagree")
    refs = tuple(sorted(set((*left.evidence_refs, *right.evidence_refs)), key=_ref_sort_key))
    facts = _unique_facts((*left.change_facts, *right.change_facts))
    if len({r.document_id for r in refs}) > 3 or len(facts) > 4:
        raise ValueError("merged event exceeds document/fact bounds")
    data = left.model_dump()
    hashes = tuple(sorted(set((*left.fact_hashes, *right.fact_hashes))))
    data.update(
        evidence_refs=refs,
        change_facts=facts,
        required_fact_ids=required_fact_ids(left.event_kind, facts),
        published_at=max(left.published_at, right.published_at),
        effective_date=left.effective_date or right.effective_date,
        event_key_hash=(
            right.event_key_hash
            if left.effective_date is None and right.effective_date is not None
            else left.event_key_hash
        ),
        source_official=left.source_official or right.source_official,
        novelty=_novelty(
            hashes,
            event_id=left.event_id,
            baseline=baseline,
            baseline_available=baseline_available,
        ),
    )
    for name in (
        "actor_refs",
        "action_refs",
        "object_refs",
        "relation_refs",
        "impact_refs",
        "official_key_hashes",
        "document_aliases",
        "revision_hashes",
        "fact_hashes",
    ):
        values = set((*getattr(left, name), *getattr(right, name)))
        data[name] = (
            tuple(sorted(values, key=_ref_sort_key))
            if name.endswith("_refs")
            else (tuple(sorted(values)))
        )
    if {left.evidence_state, right.evidence_state} & {"conflicting", "unsupported"}:
        data["evidence_state"] = "conflicting"
    elif "detail_limited" in {left.evidence_state, right.evidence_state}:
        data["evidence_state"] = "detail_limited"
    data["selection_reason"] = (
        "source_backed_event" if data["evidence_state"] == "supported" else data["evidence_state"]
    )
    return EventCandidate.model_validate(data)


def make_identity_receipt(
    candidate: EventCandidate,
    *,
    published_at: datetime,
) -> EventIdentityReceipt:
    """Project hashes only. Caller must restrict this to sealed survivors."""
    return EventIdentityReceipt(
        event_id=candidate.event_id,
        event_key_hash=candidate.event_key_hash,
        semantic_key_hash=candidate.semantic_key_hash,
        effective_date=candidate.effective_date,
        official_key_hashes=candidate.official_key_hashes,
        document_aliases=candidate.document_aliases,
        revision_hashes=candidate.revision_hashes,
        fact_hashes=candidate.fact_hashes,
        published_at=published_at,
    )
