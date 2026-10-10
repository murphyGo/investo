"""Frozen canonical identities and hash-only remote history for event schema three."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from investo.models.event_context import ContextRef, ContextRefs, RequiredContextRefs
from investo.models.event_evidence import event_digest
from investo.models.events import (
    Digest,
    EventId,
    EventKind,
    EventModel,
    EventNovelty,
    FactPredicate,
    FactStatus,
)
from investo.models.segments import MarketSegment

Label = Annotated[str, Field(strict=True, min_length=1, max_length=240)]
OccurrenceStage = Literal[
    "announcement", "decision", "result", "implementation", "correction", "statement", "unknown"
]
OccurrenceBasis = Literal["official_key", "explicit_cross_reference", "raw_document"]


class EntityIdentity(EventModel):
    entity_id: Digest
    source_labels: Annotated[tuple[Label, ...], Field(min_length=1, max_length=8)]
    display_label: Label
    alias_refs: ContextRefs = ()

    @model_validator(mode="after")
    def unique_labels(self) -> Self:
        if len(set(self.source_labels)) != len(self.source_labels):
            raise ValueError("identity.entity_invalid")
        return self


class EntityBinding(EventModel):
    entity: EntityIdentity
    basis: Literal["approved_registry", "explicit_source_alias", "raw_label"]
    registry_key: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    identity_refs: RequiredContextRefs

    @model_validator(mode="after")
    def registry_authority(self) -> Self:
        if (self.basis == "approved_registry") != (self.registry_key is not None):
            raise ValueError("identity.entity_invalid")
        if self.basis == "explicit_source_alias" and not self.entity.alias_refs:
            raise ValueError("identity.alias_unbound")
        return self


class EntityAliasProposal(EventModel):
    label_refs: RequiredContextRefs
    alias_refs: RequiredContextRefs
    relation_refs: RequiredContextRefs


class CanonicalFact(EventModel):
    subject_id: Digest
    predicate: FactPredicate
    object_id: Digest | None = None
    metric_key_hash: Digest | None = None
    value: Label
    unit: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    period: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    status: FactStatus

    @property
    def slot_key_hash(self) -> str:
        return event_digest("fact-slot-v3", self.model_dump(mode="json", exclude={"value"}))


class FactSlotReceipt(EventModel):
    slot_key_hash: Digest
    fact_hash: Digest
    status: FactStatus


class FactBinding(EventModel):
    fact_id: Digest
    canonical: CanonicalFact
    original_value: Label
    source_refs: Annotated[tuple[ContextRef, ...], Field(min_length=1, max_length=16)]
    normalization: Literal["normalized", "raw"]

    @model_validator(mode="after")
    def canonical_hash(self) -> Self:
        if self.fact_id != event_digest(
            "canonical-fact-v3", self.canonical.model_dump(mode="json")
        ):
            raise ValueError("identity.fact_hash_mismatch")
        return self


class FactCorrection(EventModel):
    old_fact_id: Digest
    new_fact_id: Digest
    source_refs: RequiredContextRefs

    @model_validator(mode="after")
    def changed(self) -> Self:
        if self.old_fact_id == self.new_fact_id:
            raise ValueError("identity.correction_invalid")
        return self


class EventFactDelta(EventModel):
    added_fact_ids: tuple[Digest, ...] = ()
    superseded_fact_ids: tuple[Digest, ...] = ()
    unchanged_fact_ids: tuple[Digest, ...] = ()
    correction_pairs: tuple[tuple[Digest, Digest], ...] = ()
    unresolved_conflict_ids: tuple[Digest, ...] = ()
    evidence_refs: tuple[ContextRef, ...] = ()

    @model_validator(mode="after")
    def disjoint(self) -> Self:
        if set(self.added_fact_ids) & set(self.unchanged_fact_ids):
            raise ValueError("identity.delta_invalid")
        if self.correction_pairs and not self.evidence_refs:
            raise ValueError("identity.correction_unbound")
        if set(self.superseded_fact_ids) != {old for old, _ in self.correction_pairs}:
            raise ValueError("identity.correction_invalid")
        return self


class OccurrenceAlias(EventModel):
    key_hash: Digest
    basis: OccurrenceBasis
    stage: OccurrenceStage


class CanonicalEventIdentity(EventModel):
    event_id: EventId
    event_key_hash: Digest
    event_kind: EventKind
    actor_ids: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=8)]
    action_key_hash: Digest
    object_ids: Annotated[tuple[Digest, ...], Field(max_length=8)] = ()
    occurrence_key_hash: Digest
    document_aliases: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=32)]
    occurrence_basis: OccurrenceBasis
    occurrence_stage: OccurrenceStage
    stage_refs: ContextRefs = ()

    @model_validator(mode="after")
    def backed_stage(self) -> Self:
        if (self.occurrence_stage == "unknown") != (not self.stage_refs):
            raise ValueError("identity.stage_unbound")
        return self

    @property
    def canonical_tuple_hash(self) -> str:
        return event_digest(
            "event-tuple-v3",
            self.event_kind,
            tuple(sorted(self.actor_ids)),
            self.action_key_hash,
            tuple(sorted(self.object_ids)),
            self.occurrence_stage,
        )


class CanonicalEventReceipt(EventModel):
    event_id: EventId
    event_key_hash: Digest
    occurrence_key_hash: Digest
    canonical_tuple_hash: Digest
    occurrence_aliases: Annotated[tuple[OccurrenceAlias, ...], Field(min_length=1, max_length=32)]
    entity_ids: tuple[Digest, ...]
    event_kind: EventKind
    document_aliases: Annotated[tuple[Digest, ...], Field(max_length=32)]
    revision_hashes: tuple[Digest, ...]
    cumulative_fact_hashes: tuple[Digest, ...]
    fact_slots: tuple[FactSlotReceipt, ...]
    supersession_pairs: tuple[tuple[Digest, Digest], ...] = ()
    first_published_at: datetime
    last_evidence_at: datetime

    @field_validator("first_published_at", "last_evidence_at")
    @classmethod
    def utc_clock(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("identity.clock_invalid")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def unique_and_ordered(self) -> Self:
        if self.last_evidence_at < self.first_published_at:
            raise ValueError("identity.clock_invalid")
        if {slot.fact_hash for slot in self.fact_slots} != set(self.cumulative_fact_hashes):
            raise ValueError("identity.receipt_invalid")
        if len(set(self.fact_slots)) != len(self.fact_slots):
            raise ValueError("identity.receipt_invalid")
        if len({(a.key_hash, a.basis, a.stage) for a in self.occurrence_aliases}) != len(
            self.occurrence_aliases
        ):
            raise ValueError("identity.alias_conflict")
        for values in (
            self.entity_ids,
            self.document_aliases,
            self.revision_hashes,
            self.cumulative_fact_hashes,
            self.supersession_pairs,
        ):
            if len(set(values)) != len(values):
                raise ValueError("identity.receipt_invalid")
        return self


class CanonicalEventLedger(EventModel):
    schema_version: Literal[3] = 3
    segment: MarketSegment
    records: Annotated[tuple[CanonicalEventReceipt, ...], Field(max_length=5000)] = ()

    @model_validator(mode="after")
    def unique_records(self) -> Self:
        if len({row.event_id for row in self.records}) != len(self.records):
            raise ValueError("identity.ledger_invalid")
        return self


class IdentityMatchResult(EventModel):
    identity: CanonicalEventIdentity
    outcome: Literal["matched", "new", "uncertain_duplicate", "conflict"]
    matched_receipt_ids: tuple[EventId, ...] = ()
    duplicate_pairs: tuple[tuple[EventId, EventId], ...] = ()


class StoryIdentityHint(EventModel):
    story_key_hash: Digest
    entity_ids: tuple[Digest, ...]
    event_kind: EventKind
    explicit_thread_refs: ContextRefs = ()
    confidence: Literal["explicit", "unlinked"]


class CanonicalEventBinding(EventModel):
    identity: CanonicalEventIdentity
    entities: Annotated[tuple[EntityBinding, ...], Field(min_length=1, max_length=16)]
    facts: Annotated[tuple[FactBinding, ...], Field(max_length=8)]
    delta: EventFactDelta
    novelty: EventNovelty
    match_outcome: Literal["matched", "new", "uncertain_duplicate", "conflict"]
    story_hint: StoryIdentityHint


class EventIdentityBaseline(EventModel):
    baseline_sha: Annotated[str, Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")]
    metadata_hash: Digest | None
    metadata_paths: tuple[str, ...]
    availability: Literal["available", "unavailable"]
    segment: MarketSegment
    segment_receipts: tuple[CanonicalEventReceipt, ...] = ()

    @model_validator(mode="after")
    def baseline_authority(self) -> Self:
        if self.availability == "available" and self.metadata_hash is None:
            raise ValueError("identity.baseline_invalid")
        if self.availability == "unavailable" and self.segment_receipts:
            raise ValueError("identity.baseline_invalid")
        return self


class LegacyEventReplayInspection(EventModel):
    """Inspection only: legacy hashes contain no canonical fact or story authority."""

    basis: Literal["legacy_hash_only"] = "legacy_hash_only"
    event_id: EventId
    document_aliases: tuple[Digest, ...]
    revision_hashes: tuple[Digest, ...]
    fact_hashes: tuple[Digest, ...]
    published_at: datetime
