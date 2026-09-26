"""Immutable, source-addressed event contracts shared across pipeline layers.

This foundation deliberately does not import ``NormalizedItem``. All buffers
are private generation inputs; publication receipts contain hashes only.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

Digest = Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]
EventId = Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{24}$")]
Text = Annotated[str, Field(strict=True, min_length=1)]
EventKind = Literal[
    "geopolitical",
    "monetary_policy",
    "macro_release",
    "earnings_result",
    "product_service",
    "public_statement",
    "corporate_action",
    "regulation",
    "market_structure",
]
EventTiming = Literal["occurred", "announced", "scheduled", "background", "unknown"]
EventRelation = Literal["direct", "linked", "background", "unrelated"]
EventImpact = Literal["systemic", "sector", "company", "context"]
EventNovelty = Literal["new", "material_update", "repeat", "unknown"]
EvidenceState = Literal["supported", "detail_limited", "conflicting", "unsupported"]
FactPredicate = Literal[
    "decision",
    "result",
    "guidance",
    "launch",
    "statement",
    "agreement",
    "status_change",
]
FactStatus = Literal["actual", "forecast", "scheduled", "quoted_opinion"]


class EventModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _utc(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("event timestamp must be timezone-aware")
    return value.astimezone(UTC)


class EvidenceDocument(EventModel):
    document_id: Digest
    revision_id: Digest
    origin_revision_id: Digest | None = None
    source_name: Text
    url: str | None = None
    published_at: datetime
    received_at: datetime
    event_time: datetime | date | None = None
    event_time_basis: Literal["source_exact", "source_date", "unknown"] = "unknown"
    source_tier: Literal["official", "primary", "secondary", "unknown"] = "unknown"
    source_status: Literal["ok", "partial", "failed", "unavailable"] = "ok"
    title: Text
    summary: str = ""
    detail_excerpt: str = ""
    evidence_budget_limited: bool = False

    @field_validator("published_at", "received_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)

    @field_validator("event_time")
    @classmethod
    def normalize_event_time(cls, value: datetime | date | None) -> datetime | date | None:
        return _utc(value) if isinstance(value, datetime) else value

    @model_validator(mode="after")
    def coherent_time(self) -> Self:
        if self.event_time_basis == "unknown":
            if self.event_time is not None:
                raise ValueError("unknown event time must be null")
        elif self.event_time_basis == "source_exact":
            if not isinstance(self.event_time, datetime):
                raise ValueError("source_exact requires a timezone-aware datetime")
            _utc(self.event_time)
        elif not isinstance(self.event_time, date) or isinstance(self.event_time, datetime):
            raise ValueError("source_date requires a date, not a fabricated midnight")
        if not self.title.strip() or not self.source_name.strip():
            raise ValueError("evidence title/source must not be blank")
        return self


class EvidenceRef(EventModel):
    document_id: Digest
    revision_id: Digest
    field: Literal["title", "summary", "detail_excerpt"]
    start: StrictInt = Field(ge=0)
    end: StrictInt = Field(gt=0)

    @model_validator(mode="after")
    def bounded_span(self) -> Self:
        if not 1 <= self.end - self.start <= 240:
            raise ValueError("evidence span must contain 1..240 codepoints")
        return self


Refs = Annotated[tuple[EvidenceRef, ...], Field(min_length=1, max_length=12)]


class EventFactDraft(EventModel):
    predicate: FactPredicate
    evidence_ref: EvidenceRef
    status: FactStatus = "actual"
    period: Text | None = None
    unit: Text | None = None


class EventCandidateDraft(EventModel):
    """Stage 1 proposal. Identity, novelty, and required facts are parent-owned."""

    item_ids: Annotated[tuple[StrictInt, ...], Field(min_length=1, max_length=3)]
    event_kind: EventKind
    actor_refs: Refs
    action_refs: Refs
    object_refs: tuple[EvidenceRef, ...] = Field(default=(), max_length=12)
    relation_refs: tuple[EvidenceRef, ...] = Field(default=(), max_length=12)
    impact_refs: tuple[EvidenceRef, ...] = Field(default=(), max_length=12)
    facts: tuple[EventFactDraft, ...] = Field(default=(), max_length=4)
    timing: EventTiming
    relation: EventRelation
    impact: EventImpact
    evidence_state: EvidenceState = "supported"

    @field_validator("item_ids")
    @classmethod
    def valid_ids(cls, values: tuple[int, ...]) -> tuple[int, ...]:
        if min(values) < 1 or len(set(values)) != len(values):
            raise ValueError("item_ids must be distinct positive same-run IDs")
        return values


class EventFact(EventModel):
    fact_id: Digest
    predicate: FactPredicate
    evidence_ref: EvidenceRef
    value_text: Annotated[str, Field(strict=True, min_length=1, max_length=240)]
    status: FactStatus
    period: Text | None = None
    unit: Text | None = None


class EventCandidate(EventModel):
    event_id: EventId
    event_key_hash: Digest
    semantic_key_hash: Digest
    event_kind: EventKind
    evidence_refs: Annotated[tuple[EvidenceRef, ...], Field(min_length=1, max_length=64)]
    actor_refs: Refs
    action_refs: Refs
    object_refs: tuple[EvidenceRef, ...] = ()
    relation_refs: tuple[EvidenceRef, ...] = ()
    impact_refs: tuple[EvidenceRef, ...] = ()
    change_facts: tuple[EventFact, ...] = Field(default=(), max_length=4)
    required_fact_ids: tuple[Digest, ...] = ()
    timing: EventTiming
    relation: EventRelation
    impact: EventImpact
    novelty: EventNovelty
    evidence_state: EvidenceState
    published_at: datetime
    effective_date: date | None = None
    official_key_hashes: tuple[Digest, ...] = ()
    document_aliases: tuple[Digest, ...] = ()
    revision_hashes: tuple[Digest, ...] = ()
    fact_hashes: tuple[Digest, ...] = ()
    source_official: bool = False
    selection_reason: str = ""

    @field_validator("published_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def valid_fact_membership(self) -> Self:
        ids = tuple(f.fact_id for f in self.change_facts)
        if len(set(ids)) != len(ids) or len(set(self.required_fact_ids)) != len(
            self.required_fact_ids
        ):
            raise ValueError("fact IDs must be unique")
        if not set(self.required_fact_ids) <= set(ids):
            raise ValueError("required fact must belong to this event")
        if len({ref.document_id for ref in self.evidence_refs}) > 3:
            raise ValueError("event may reference at most three documents")
        used_refs = (
            *self.actor_refs,
            *self.action_refs,
            *self.object_refs,
            *self.relation_refs,
            *self.impact_refs,
            *(fact.evidence_ref for fact in self.change_facts),
        )
        if not set(used_refs) <= set(self.evidence_refs):
            raise ValueError("event evidence must contain every identity and fact reference")
        return self


class EventIdentityReceipt(EventModel):
    """Hash-only alias/novelty record; callers supply remote-confirmed records."""

    event_id: EventId
    event_key_hash: Digest
    semantic_key_hash: Digest
    effective_date: date | None = None
    official_key_hashes: tuple[Digest, ...] = ()
    document_aliases: tuple[Digest, ...] = ()
    revision_hashes: tuple[Digest, ...] = ()
    fact_hashes: tuple[Digest, ...] = ()
    published_at: datetime

    @field_validator("published_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)


class EventExclusion(EventModel):
    event_id: EventId
    reason: Literal[
        "outside_window",
        "background",
        "low_importance",
        "evidence_conflict",
        "source_unavailable",
        "duplicate",
        "budget_deferred",
        "unsupported",
    ]


class EventSelectionPlan(EventModel):
    selected: tuple[EventCandidate, ...] = Field(default=(), max_length=5)
    excluded: tuple[EventExclusion, ...] = ()
    evidence_documents: tuple[EvidenceDocument, ...] = ()
    protected_block: str = ""
    evidence_row_count: StrictInt = Field(default=0, ge=0)
    protected_byte_count: StrictInt = Field(default=0, ge=0, le=8192)

    @model_validator(mode="after")
    def exact_accounting(self) -> Self:
        if self.protected_byte_count != len(self.protected_block.encode("utf-8")):
            raise ValueError("protected byte count must equal UTF-8 block size")
        keys = {(d.document_id, d.revision_id) for d in self.evidence_documents}
        if len(keys) != len(self.evidence_documents) or self.evidence_row_count != len(keys):
            raise ValueError("evidence row accounting must be exact and unique")
        ids = [event.event_id for event in self.selected]
        if len(ids) != len(set(ids)):
            raise ValueError("selected event IDs must be unique")
        return self
