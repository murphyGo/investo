"""Private, source-addressed context for schema-three event generation."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import Annotated, Literal, Self

from pydantic import Field, StrictInt, field_validator, model_validator

from investo.models.events import (
    Digest,
    EventImpact,
    EventKind,
    EventModel,
    EventRelation,
    EventTiming,
    FactPredicate,
    FactStatus,
)

ChunkRole = Literal[
    "identity", "fact", "background", "comparison", "meaning", "reaction", "follow_up"
]
TimePrecision = Literal["exact", "date", "unknown"]
ContextReason = Literal[
    "facts.required_missing",
    "facts.content_shallow",
    "time.event_unknown",
    "history.unavailable",
    "source.locator_missing",
    "meaning.ref_missing",
    "reaction.ref_missing",
]
ContextRule = Literal[
    "context.unknown_document",
    "context.unknown_chunk",
    "context.span_out_of_bounds",
    "context.blank_span",
    "context.item_mismatch",
    "context.source_unavailable",
    "context.future_occurred",
    "context.invalid_schema",
    "context.required_missing",
    "context.budget_exhausted",
    "context.buffer_conflict",
    "context.fact_invalid",
    "context.status_unbound",
]


class ContextRef(EventModel):
    document_id: Digest
    revision_id: Digest
    chunk_id: Digest
    start: Annotated[StrictInt, Field(ge=0)]
    end: Annotated[StrictInt, Field(gt=0)]

    @model_validator(mode="after")
    def bounded_span(self) -> Self:
        if not 1 <= self.end - self.start <= 240:
            raise ValueError("context span must contain one to 240 codepoints")
        return self


ContextRefs = Annotated[tuple[ContextRef, ...], Field(max_length=16)]
RequiredContextRefs = Annotated[tuple[ContextRef, ...], Field(min_length=1, max_length=16)]


class EvidenceChunk(EventModel):
    chunk_id: Digest
    role: ChunkRole
    text: Annotated[str, Field(strict=True, min_length=1, max_length=1200, repr=False)]
    source_locator: Annotated[str, Field(strict=True, min_length=1, max_length=240)]
    text_sha256: Digest

    @model_validator(mode="after")
    def verify_buffer(self) -> Self:
        if not self.text.strip():
            raise ValueError("context chunk must not be blank")
        if hashlib.sha256(self.text.encode("utf-8")).hexdigest() != self.text_sha256:
            raise ValueError("context chunk hash does not match its buffer")
        return self


class EventTimeValue(EventModel):
    value: datetime | date | None = None
    precision: TimePrecision = "unknown"
    source_refs: ContextRefs = ()

    @model_validator(mode="after")
    def precise_time(self) -> Self:
        if self.precision == "unknown":
            if self.value is not None or self.source_refs:
                raise ValueError("unknown time must have no value or references")
        elif self.precision == "exact":
            if not isinstance(self.value, datetime) or self.value.utcoffset() is None:
                raise ValueError("exact time must be timezone-aware")
            object.__setattr__(self, "value", self.value.astimezone(UTC))
        elif not isinstance(self.value, date) or isinstance(self.value, datetime):
            raise ValueError("date precision must preserve the source date")
        return self


class ReferencePeriod(EventModel):
    value: Annotated[str, Field(strict=True, min_length=1, max_length=80)] | None = None
    source_refs: ContextRefs = ()

    @model_validator(mode="after")
    def supported_period(self) -> Self:
        if (self.value is None) != (not self.source_refs):
            raise ValueError("reference period requires source evidence")
        return self


class EventTimeContext(EventModel):
    occurred_at: EventTimeValue = EventTimeValue()
    announced_at: EventTimeValue = EventTimeValue()
    published_at: EventTimeValue = EventTimeValue()
    received_at: EventTimeValue = EventTimeValue()
    reference_period: ReferencePeriod = ReferencePeriod()

    @model_validator(mode="after")
    def source_event_time(self) -> Self:
        for point in (self.occurred_at, self.announced_at):
            if point.precision != "unknown" and not point.source_refs:
                raise ValueError("event occurrence and announcement require source references")
        return self


class EventContextDocument(EventModel):
    document_id: Digest
    revision_id: Digest
    origin_revision_id: Digest
    source_name: Annotated[str, Field(strict=True, min_length=1, max_length=100)]
    url: Annotated[str, Field(strict=True, min_length=1, max_length=2000)] | None = None
    source_tier: Literal["official", "primary", "secondary", "unknown"] = "unknown"
    source_status: Literal["ok", "partial", "failed", "unavailable"] = "ok"
    chunks: Annotated[tuple[EvidenceChunk, ...], Field(min_length=1, max_length=4, repr=False)]
    time: EventTimeContext
    evidence_budget_limited: bool = False

    @model_validator(mode="after")
    def unique_chunks_and_time_refs(self) -> Self:
        keys = {chunk.chunk_id: chunk for chunk in self.chunks}
        if len(keys) != len(self.chunks):
            raise ValueError("context chunk identities must be unique")
        refs = (
            *self.time.occurred_at.source_refs,
            *self.time.announced_at.source_refs,
            *self.time.published_at.source_refs,
            *self.time.received_at.source_refs,
            *self.time.reference_period.source_refs,
        )
        for ref in refs:
            chunk = keys.get(ref.chunk_id)
            if (
                ref.document_id != self.document_id
                or ref.revision_id != self.revision_id
                or chunk is None
                or ref.end > len(chunk.text)
                or not chunk.text[ref.start : ref.end].strip()
            ):
                raise ValueError("document time reference must belong to its exact buffer")
        return self


class ContextFactDraft(EventModel):
    predicate: FactPredicate
    status: FactStatus
    value_kind: Literal["numeric", "text"]
    subject_refs: RequiredContextRefs
    predicate_refs: ContextRefs = ()
    object_refs: ContextRefs = ()
    metric_refs: ContextRefs = ()
    value_refs: RequiredContextRefs
    unit_refs: ContextRefs = ()
    period_refs: ContextRefs = ()
    status_refs: ContextRefs = ()

    @model_validator(mode="after")
    def metric_identity(self) -> Self:
        if self.value_kind == "numeric" and not self.metric_refs:
            raise ValueError("numeric facts require a source-backed metric")
        return self


class ContextEventDraft(EventModel):
    """Stage-one proposal; identities, novelty and quality remain parent-owned."""

    item_ids: Annotated[tuple[StrictInt, ...], Field(min_length=1, max_length=4)]
    event_kind: EventKind
    actor_refs: RequiredContextRefs
    action_refs: RequiredContextRefs
    object_refs: ContextRefs = ()
    relation_refs: ContextRefs = ()
    impact_refs: ContextRefs = ()
    facts: Annotated[tuple[ContextFactDraft, ...], Field(max_length=8)] = ()
    background_refs: ContextRefs = ()
    comparison_refs: ContextRefs = ()
    meaning_refs: ContextRefs = ()
    reaction_refs: ContextRefs = ()
    follow_up_refs: ContextRefs = ()
    timing: EventTiming
    relation: EventRelation
    impact: EventImpact

    @field_validator("item_ids")
    @classmethod
    def positive_unique_ids(cls, values: tuple[int, ...]) -> tuple[int, ...]:
        if min(values) < 1 or len(set(values)) != len(values):
            raise ValueError("context item IDs must be distinct positive same-run IDs")
        return values


class ContextClassificationResult(EventModel):
    schema_version: Literal[3]
    events: Annotated[tuple[ContextEventDraft, ...], Field(max_length=12)]


class EventSupportVector(EventModel):
    facts: Literal["complete", "limited", "missing"]
    time: Literal["exact", "date", "publication_only", "unknown"]
    novelty: Literal["known", "unknown"]
    locator: Literal["complete", "missing"]
    meaning: Literal["source_reported", "conditional", "unavailable"] = "unavailable"
    reaction: Literal["observed", "source_reported_no_reaction", "unavailable"] = "unavailable"
    reason_codes: Annotated[tuple[ContextReason, ...], Field(max_length=8)] = ()


class ContextPreparationObservation(EventModel):
    """Hash-only shadow observation; never represents an LLM classification."""

    schema_version: Literal[3] = 3
    basis: Literal["deterministic_shadow"] = "deterministic_shadow"
    buffer_sha256: Digest | None = None
    input_count: Annotated[StrictInt, Field(ge=0, le=96)]
    retained_count: Annotated[StrictInt, Field(ge=0, le=96)]
    deferred_count: Annotated[StrictInt, Field(ge=0, le=96)]
    rule_code: ContextRule | None = None


class MeaningContext(EventModel):
    mode: Literal["source_reported", "conditional", "unavailable"]
    text: Annotated[str, Field(strict=True, min_length=1, max_length=180)] | None = None
    mechanism: Annotated[str, Field(strict=True, min_length=1, max_length=180)] | None = None
    assumptions: Annotated[tuple[str, ...], Field(max_length=4)] = ()
    refs: ContextRefs = ()

    @model_validator(mode="after")
    def coherent_meaning(self) -> Self:
        if self.mode == "unavailable":
            if self.text is not None or self.mechanism is not None or self.assumptions or self.refs:
                raise ValueError("unavailable meaning must not make claims")
        elif self.text is None or not self.refs:
            raise ValueError("meaning requires text and source evidence")
        if self.mode == "conditional" and (not self.mechanism or not self.assumptions):
            raise ValueError("conditional meaning requires a mechanism and assumptions")
        if any(not value.strip() or len(value) > 180 for value in self.assumptions):
            raise ValueError("meaning assumptions must be bounded nonblank text")
        return self


class ReactionContext(EventModel):
    status: Literal["observed", "source_reported_no_reaction", "unavailable"]
    attribution: Literal["source_reported", "coincidence_only", "unavailable"]
    asset_id: Annotated[str, Field(strict=True, min_length=1, max_length=100)] | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    observed_at: datetime | None = None
    baseline_ref: ContextRef | None = None
    value_ref: ContextRef | None = None
    text: Annotated[str, Field(strict=True, min_length=1, max_length=180)] | None = None
    refs: ContextRefs = ()

    @field_validator("window_start", "window_end", "observed_at")
    @classmethod
    def aware_window(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.utcoffset() is None:
            raise ValueError("reaction time must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def verified_reaction(self) -> Self:
        if self.status == "unavailable":
            if (
                any(
                    value is not None
                    for value in (
                        self.asset_id,
                        self.window_start,
                        self.window_end,
                        self.observed_at,
                        self.baseline_ref,
                        self.value_ref,
                        self.text,
                    )
                )
                or self.refs
                or self.attribution != "unavailable"
            ):
                raise ValueError("unavailable reaction must not make claims")
        elif self.text is None or not self.refs:
            raise ValueError("reaction requires text and source evidence")
        if self.status == "observed":
            if (
                self.asset_id is None
                or self.window_start is None
                or self.window_end is None
                or self.observed_at is None
                or self.baseline_ref is None
                or self.value_ref is None
                or self.attribution == "unavailable"
            ):
                raise ValueError("observed reaction requires asset, window and compared evidence")
            if self.window_start > self.window_end or self.observed_at < self.window_end:
                raise ValueError("reaction window must precede its observation")
            if not {self.baseline_ref, self.value_ref} <= set(self.refs):
                raise ValueError("reaction compared values must belong to its references")
        if self.status == "source_reported_no_reaction" and self.attribution != "source_reported":
            raise ValueError("no-reaction claims require source attribution")
        return self


class ContextDiagnostic(EventModel):
    field: Literal["envelope", "identity", "fact", "time", "context", "budget"]
    rule_code: ContextRule
    event_id_hash: Digest | None = None
    attempt: Annotated[StrictInt, Field(ge=1, le=16)]
