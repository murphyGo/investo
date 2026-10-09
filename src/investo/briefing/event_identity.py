"""Pure source-backed entity, fact, occurrence and delta resolution for schema three."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Literal, cast

from investo.briefing.event_context import (
    context_lookup,
    fact_context_refs,
    resolve_context_ref,
    validate_context_event,
    validate_context_fact,
)
from investo.models.event_context import (
    ContextEventDraft,
    ContextFactDraft,
    ContextRef,
    EventContextDocument,
)
from investo.models.event_evidence import event_digest
from investo.models.event_identity import (
    CanonicalEventBinding,
    CanonicalEventIdentity,
    CanonicalEventReceipt,
    CanonicalFact,
    EntityAliasProposal,
    EntityBinding,
    EntityIdentity,
    EventFactDelta,
    FactBinding,
    FactCorrection,
    IdentityMatchResult,
    OccurrenceBasis,
    OccurrenceStage,
    StoryIdentityHint,
)
from investo.models.event_story import SealedStorySourceRef


class EventIdentityError(ValueError):
    def __init__(
        self,
        code: Literal[
            "identity.alias_unbound",
            "identity.field_limited",
            "identity.fact_unbound",
            "identity.occurrence_conflict",
            "identity.correction_unbound",
            "identity.record_budget_exhausted",
        ],
    ) -> None:
        self.code = code
        super().__init__(code)


def normalized_label(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _source_label(refs: Sequence[ContextRef], documents: Sequence[EventContextDocument]) -> str:
    labels = {normalized_label(resolve_context_ref(ref, documents)) for ref in refs}
    if len(labels) != 1:
        raise EventIdentityError("identity.fact_unbound")
    label = next(iter(labels))
    if not 1 <= len(label) <= 240:
        raise EventIdentityError("identity.field_limited")
    return label


def normalize_entity_bindings(
    context_documents: Sequence[EventContextDocument],
    label_refs: Sequence[Sequence[ContextRef]],
    *,
    alias_proposals: Sequence[EntityAliasProposal] = (),
    approved_registry: Mapping[str, str] | None = None,
) -> tuple[EntityBinding, ...]:
    """Registry keys are reviewed identifiers, never guessed ticker/name aliases."""
    registry = approved_registry or {}
    aliases: dict[str, tuple[str, tuple[ContextRef, ...]]] = {}
    for proposal in alias_proposals:
        left = _source_label(proposal.label_refs, context_documents)
        right = _source_label(proposal.alias_refs, context_documents)
        alias_evidence = (*proposal.label_refs, *proposal.alias_refs, *proposal.relation_refs)
        if len(set(alias_evidence)) > 16:
            raise EventIdentityError("identity.record_budget_exhausted")
        if len({(r.document_id, r.revision_id) for r in alias_evidence}) != 1:
            raise EventIdentityError("identity.alias_unbound")
        relation = " ".join(
            resolve_context_ref(r, context_documents) for r in proposal.relation_refs
        )
        affirmative = (
            rf"{re.escape(left)}(?:,? (?:is |was )?(?:also known as|formerly known as) )"
            rf"{re.escape(right)}[.。]?",
            rf"{re.escape(left)}\s*\(약칭\s+{re.escape(right)}\)[.。]?",
            rf"{re.escape(left)}(?:은|는) {re.escape(right)}(?:이라고도|로도) "
            r"(?:불린다|알려져 있다)[.。]?",
        )
        if not any(re.fullmatch(pattern, normalized_label(relation)) for pattern in affirmative):
            raise EventIdentityError("identity.alias_unbound")
        root = min(left, right)
        for label in (left, right):
            if label in aliases and aliases[label][0] != root:
                raise EventIdentityError("identity.alias_unbound")
            aliases[label] = (root, tuple(dict.fromkeys(alias_evidence)))
    result: list[EntityBinding] = []
    for refs in label_refs:
        label = _source_label(refs, context_documents)
        raw_labels = tuple(
            dict.fromkeys(resolve_context_ref(ref, context_documents) for ref in refs)
        )
        if len(raw_labels) > 8:
            raise EventIdentityError("identity.field_limited")
        alias_refs: tuple[ContextRef, ...] = ()
        key = registry.get(label)
        if key is not None and not 1 <= len(key) <= 100:
            raise EventIdentityError("identity.alias_unbound")
        basis: Literal["approved_registry", "explicit_source_alias", "raw_label"] = "raw_label"
        root = label
        if key is not None:
            root, basis = key, "approved_registry"
        elif label in aliases:
            root, alias_refs = aliases[label]
            basis = "explicit_source_alias"
        result.append(
            EntityBinding(
                entity=EntityIdentity(
                    entity_id=event_digest("entity-v3", root),
                    source_labels=raw_labels,
                    display_label=label,
                    alias_refs=alias_refs,
                ),
                basis=basis,
                registry_key=key,
                identity_refs=tuple(refs),
            )
        )
    return tuple(result)


def normalize_fact_bindings(
    context_documents: Sequence[EventContextDocument],
    proposals: Sequence[ContextFactDraft],
    *,
    approved_registry: Mapping[str, str] | None = None,
) -> tuple[FactBinding, ...]:
    result: dict[str, FactBinding] = {}
    lookup = context_lookup(context_documents)
    for draft in proposals:
        validate_context_fact(draft, lookup)
        if not draft.status_refs:
            raise EventIdentityError("identity.fact_unbound")
        refs = [draft.subject_refs]
        if draft.object_refs:
            refs.append(draft.object_refs)
        entities = normalize_entity_bindings(
            context_documents, refs, approved_registry=approved_registry
        )
        original = resolve_context_ref(draft.value_refs[0], context_documents)
        value = _source_label(draft.value_refs, context_documents)
        if draft.value_kind == "numeric":
            # Preserve signs, decimal spelling and scale; remove thousands commas only.
            value = value.replace(",", "")
        metric = _source_label(draft.metric_refs, context_documents) if draft.metric_refs else None
        unit = _source_label(draft.unit_refs, context_documents) if draft.unit_refs else None
        period = _source_label(draft.period_refs, context_documents) if draft.period_refs else None
        if (unit is not None and len(unit) > 80) or (period is not None and len(period) > 80):
            raise EventIdentityError("identity.field_limited")
        canonical = CanonicalFact(
            subject_id=entities[0].entity.entity_id,
            predicate=draft.predicate,
            object_id=entities[1].entity.entity_id if len(entities) > 1 else None,
            metric_key_hash=event_digest("metric-v3", metric) if metric else None,
            value=value,
            unit=unit,
            period=period,
            status=draft.status,
        )
        fact_id = event_digest("canonical-fact-v3", canonical.model_dump(mode="json"))
        if len(fact_context_refs(draft)) > 16:
            raise EventIdentityError("identity.record_budget_exhausted")
        binding = FactBinding(
            fact_id=fact_id,
            canonical=canonical,
            original_value=original,
            source_refs=fact_context_refs(draft),
            normalization="normalized",
        )
        if fact_id in result:
            combined = tuple(dict.fromkeys((*result[fact_id].source_refs, *binding.source_refs)))
            if len(combined) > 16:
                raise EventIdentityError("identity.record_budget_exhausted")
            binding = binding.model_copy(update={"source_refs": combined})
        result[fact_id] = binding
    return tuple(result[key] for key in sorted(result))


def _metadata_value(doc: EventContextDocument, key: str) -> tuple[str, ContextRef] | None:
    for chunk in doc.chunks:
        if chunk.source_locator != "source_metadata":
            continue
        metadata = json.loads(chunk.text)
        value = metadata.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 240:
            continue
        prefix = json.dumps(key) + ":"
        start = chunk.text.index(prefix) + len(prefix) + 1
        encoded = json.dumps(value, ensure_ascii=False)[1:-1]
        if len(encoded) > 240:
            raise EventIdentityError("identity.field_limited")
        return value, ContextRef(
            document_id=doc.document_id,
            revision_id=doc.revision_id,
            chunk_id=chunk.chunk_id,
            start=start,
            end=start + len(encoded),
        )
    return None


def resolve_event_identity(
    proposal: ContextEventDraft,
    documents: Sequence[EventContextDocument],
    baseline: Sequence[CanonicalEventReceipt],
    *,
    observed_at: datetime,
    approved_registry: Mapping[str, str] | None = None,
) -> IdentityMatchResult:
    validate_context_event(proposal, documents, observed_at=observed_at)
    actors = normalize_entity_bindings(
        documents, [(ref,) for ref in proposal.actor_refs], approved_registry=approved_registry
    )
    objects = (
        normalize_entity_bindings(
            documents, [(ref,) for ref in proposal.object_refs], approved_registry=approved_registry
        )
        if proposal.object_refs
        else ()
    )
    action = _source_label(proposal.action_refs, documents)
    owners = tuple(documents[i - 1] for i in proposal.item_ids)
    stage: OccurrenceStage = "unknown"
    stage_refs: tuple[ContextRef, ...] = ()
    stage_values = [_metadata_value(doc, "event_occurrence_stage") for doc in owners]
    known_stages = [value for value in stage_values if value is not None]
    if known_stages:
        stages = {value[0] for value in known_stages}
        if len(stages) != 1 or next(iter(stages)) not in {
            "announcement",
            "decision",
            "result",
            "implementation",
            "correction",
            "statement",
        }:
            raise EventIdentityError("identity.occurrence_conflict")
        stage = cast(OccurrenceStage, next(iter(stages)))
        stage_refs = tuple(value[1] for value in known_stages)
    actor_ids = tuple(sorted({row.entity.entity_id for row in actors}))
    object_ids = tuple(sorted({row.entity.entity_id for row in objects}))
    if len(actor_ids) > 8 or len(object_ids) > 8:
        raise EventIdentityError("identity.field_limited")
    action_hash = event_digest("action-v3", action)
    tuple_hash = event_digest(
        "event-tuple-v3", proposal.event_kind, actor_ids, action_hash, object_ids, stage
    )
    documents_aliases = tuple(sorted({doc.document_id for doc in owners}))
    # Include timing in the conservative raw discriminator: schedules and outcomes
    # cannot share an occurrence just because their textual tuple is the same.
    source_periods = tuple(
        sorted(
            {
                doc.time.reference_period.value
                for doc in owners
                if doc.time.reference_period.value is not None
            }
        )
    )
    raw_keys = {
        event_digest("raw-occurrence-v3", document_id, tuple_hash, proposal.timing, source_periods)
        for document_id in documents_aliases
    }
    raw_key = min(raw_keys)
    keys: set[str] = set()
    basis: OccurrenceBasis = "raw_document"
    for key, candidate_basis in (
        ("official_release_id", "official_key"),
        ("event_cross_reference", "explicit_cross_reference"),
    ):
        values = [_metadata_value(doc, key) for doc in owners]
        keys = {
            event_digest("source-occurrence-v3", value[0], proposal.timing)
            for value in values
            if value is not None
        }
        if keys:
            if len(keys) != 1:
                raise EventIdentityError("identity.occurrence_conflict")
            basis = cast(OccurrenceBasis, candidate_basis)
            break
    occurrence = next(iter(keys)) if keys else raw_key
    identity = CanonicalEventIdentity(
        event_id=occurrence[:24],
        event_key_hash=tuple_hash,
        event_kind=proposal.event_kind,
        actor_ids=actor_ids,
        action_key_hash=action_hash,
        object_ids=object_ids,
        occurrence_key_hash=occurrence,
        document_aliases=documents_aliases,
        occurrence_basis=basis,
        occurrence_stage=stage,
        stage_refs=stage_refs,
    )
    matches = [
        row
        for row in baseline
        if any(alias.key_hash in {*raw_keys, occurrence} for alias in row.occurrence_aliases)
    ]
    if len(matches) > 1 or any(row.canonical_tuple_hash != tuple_hash for row in matches):
        return IdentityMatchResult(
            identity=identity,
            outcome="conflict",
            matched_receipt_ids=tuple(sorted(row.event_id for row in matches)),
        )
    if matches:
        return IdentityMatchResult(
            identity=identity.model_copy(update={"event_id": matches[0].event_id}),
            outcome="matched",
            matched_receipt_ids=(matches[0].event_id,),
        )
    uncertain = tuple(
        sorted(
            tuple(sorted((identity.event_id, row.event_id)))
            for row in baseline
            if row.canonical_tuple_hash == tuple_hash
        )
    )
    return IdentityMatchResult(
        identity=identity,
        outcome="uncertain_duplicate" if uncertain else "new",
        duplicate_pairs=uncertain,
    )


def compare_event_facts(
    identity: CanonicalEventIdentity,
    current_facts: Sequence[FactBinding],
    baseline: Sequence[CanonicalEventReceipt],
    *,
    corrections: Sequence[FactCorrection] = (),
    documents: Sequence[EventContextDocument] = (),
    prior_fact_bindings: Sequence[FactBinding] = (),
) -> EventFactDelta:
    old = next((row for row in baseline if row.event_id == identity.event_id), None)
    prior = set(old.cumulative_fact_hashes) if old else set()
    current = {fact.fact_id for fact in current_facts}
    pairs: list[tuple[str, str]] = []
    refs: list[ContextRef] = []
    for correction in corrections:
        if correction.old_fact_id not in prior or correction.new_fact_id not in current:
            raise EventIdentityError("identity.correction_unbound")
        before = next(
            (fact for fact in prior_fact_bindings if fact.fact_id == correction.old_fact_id), None
        )
        after = next(
            (fact for fact in current_facts if fact.fact_id == correction.new_fact_id), None
        )
        if before is None or after is None:
            raise EventIdentityError("identity.correction_unbound")
        if any(ref.document_id not in identity.document_aliases for ref in correction.source_refs):
            raise EventIdentityError("identity.correction_unbound")
        if not {ref.document_id for ref in correction.source_refs} & {
            ref.document_id for ref in after.source_refs
        }:
            raise EventIdentityError("identity.correction_unbound")
        for source_ref in (*before.source_refs, *after.source_refs):
            resolve_context_ref(source_ref, documents)
        component_text = {
            normalized_label(resolve_context_ref(ref, documents)) for ref in after.source_refs
        }
        subjects = {
            value
            for value in component_text
            if event_digest("entity-v3", value) == after.canonical.subject_id
        }
        metrics = {
            value
            for value in component_text
            if event_digest("metric-v3", value) == after.canonical.metric_key_hash
        }
        if not subjects or (after.canonical.metric_key_hash is not None and not metrics):
            raise EventIdentityError("identity.correction_unbound")
        claims = [resolve_context_ref(ref, documents) for ref in correction.source_refs]
        if not any(
            any(label in claim for label in subjects)
            and (not metrics or any(label in claim for label in metrics))
            and (
                re.search(
                    rf"corrected from {re.escape(before.original_value)} "
                    rf"to {re.escape(after.original_value)}(?:\b|$)",
                    claim,
                )
                or re.search(
                    rf"{re.escape(before.original_value)}에서 "
                    rf"{re.escape(after.original_value)}(?:으)?로 정정",
                    claim,
                )
            )
            for claim in claims
        ):
            raise EventIdentityError("identity.correction_unbound")
        pairs.append((correction.old_fact_id, correction.new_fact_id))
        refs.extend(correction.source_refs)
    conflicts: set[str] = set()
    for left in current_facts:
        for right in current_facts:
            a, b = left.canonical, right.canonical
            if (
                left.fact_id != right.fact_id
                and a.status == b.status == "actual"
                and a.model_dump(exclude={"value"}) == b.model_dump(exclude={"value"})
            ):
                conflicts.update((left.fact_id, right.fact_id))
    superseded = {old_id for old_id, _ in pairs}
    if old is not None:
        superseded.update(old_id for old_id, _ in old.supersession_pairs)
        for fact in current_facts:
            if fact.canonical.status != "actual":
                continue
            for slot in old.fact_slots:
                if (
                    slot.status == "actual"
                    and slot.slot_key_hash == fact.canonical.slot_key_hash
                    and slot.fact_hash != fact.fact_id
                    and slot.fact_hash not in superseded
                ):
                    conflicts.update((slot.fact_hash, fact.fact_id))
    added = tuple(sorted(current - prior))
    refs.extend(ref for fact in current_facts if fact.fact_id in added for ref in fact.source_refs)
    return EventFactDelta(
        added_fact_ids=added,
        superseded_fact_ids=tuple(sorted({old for old, _ in pairs})),
        unchanged_fact_ids=tuple(sorted(current & prior)),
        correction_pairs=tuple(sorted(set(pairs))),
        unresolved_conflict_ids=tuple(sorted(conflicts)),
        evidence_refs=tuple(dict.fromkeys(refs)),
    )


def canonical_event_binding(
    proposal: ContextEventDraft,
    documents: Sequence[EventContextDocument],
    baseline: Sequence[CanonicalEventReceipt],
    *,
    observed_at: datetime,
    baseline_available: bool,
    approved_registry: Mapping[str, str] | None = None,
) -> CanonicalEventBinding:
    match = resolve_event_identity(
        proposal, documents, baseline, observed_at=observed_at, approved_registry=approved_registry
    )
    facts = normalize_fact_bindings(documents, proposal.facts, approved_registry=approved_registry)
    entities = normalize_entity_bindings(
        documents,
        [proposal.actor_refs, *([proposal.object_refs] if proposal.object_refs else [])],
        approved_registry=approved_registry,
    )
    delta = compare_event_facts(match.identity, facts, baseline)
    novelty: Literal["new", "material_update", "repeat", "unknown"] = "unknown"
    if baseline_available and match.outcome != "conflict" and not delta.unresolved_conflict_ids:
        novelty = (
            "new"
            if match.outcome in {"new", "uncertain_duplicate"}
            else "material_update"
            if delta.added_fact_ids or delta.correction_pairs
            else "repeat"
        )
    thread = [_metadata_value(documents[i - 1], "event_thread_id") for i in proposal.item_ids]
    linked = [value for value in thread if value is not None]
    if len({value[0] for value in linked}) > 1:
        raise EventIdentityError("identity.occurrence_conflict")
    hint = StoryIdentityHint(
        story_key_hash=event_digest("story-thread-v3", linked[0][0])
        if linked
        else event_digest("standalone-story-v3", match.identity.event_id),
        entity_ids=match.identity.actor_ids,
        event_kind=proposal.event_kind,
        explicit_thread_refs=tuple(value[1] for value in linked),
        confidence="explicit" if linked else "unlinked",
    )
    return CanonicalEventBinding(
        identity=match.identity,
        entities=entities,
        facts=facts,
        delta=delta,
        novelty=novelty,
        match_outcome=match.outcome,
        story_hint=hint,
    )


def source_receipt(
    ref: ContextRef, documents: Sequence[EventContextDocument]
) -> SealedStorySourceRef:
    text = resolve_context_ref(ref, documents)
    doc = context_lookup(documents)[(ref.document_id, ref.revision_id)]
    return SealedStorySourceRef(
        **ref.model_dump(),
        ref_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        source_href=doc.url,
    )
