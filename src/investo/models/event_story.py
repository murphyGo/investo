"""Complete frozen story contracts; reducers and ledger I/O belong to later owners."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, StrictInt, field_validator, model_validator

from investo.models.event_context import ContextRef, ContextRefs, EventTimeValue, TimePrecision
from investo.models.event_evidence import event_digest
from investo.models.event_identity import EventFactDelta, StoryIdentityHint
from investo.models.events import Digest, EventId, EventKind, EventModel
from investo.models.segments import MarketSegment

StoryState = Literal[
    "announced", "pending", "confirmed", "implemented", "resolved", "cancelled", "unknown"
]
StoryDisposition = Literal["active", "archived_unknown", "closed"]
StoryTransitionSignal = Literal[
    "announcement",
    "pending_confirmation",
    "outcome_confirmed",
    "implementation_verified",
    "resolution_verified",
    "cancellation_verified",
    "evidence_conflict",
    "no_new_evidence",
]


class SealedStorySourceRef(EventModel):
    document_id: Digest
    revision_id: Digest
    chunk_id: Digest
    start: Annotated[StrictInt, Field(ge=0)]
    end: Annotated[StrictInt, Field(gt=0)]
    ref_sha256: Digest
    source_href: Annotated[str, Field(strict=True, min_length=1, max_length=2000)] | None = None

    @model_validator(mode="after")
    def valid_locator(self) -> Self:
        if not 1 <= self.end - self.start <= 240:
            raise ValueError("story.source_ref_invalid")
        if self.source_href is not None:
            url = urlsplit(self.source_href)
            if url.scheme not in {"http", "https"} or not url.hostname or url.username:
                raise ValueError("story.source_ref_invalid")
        return self

    @property
    def context_ref(self) -> ContextRef:
        return ContextRef(
            document_id=self.document_id,
            revision_id=self.revision_id,
            chunk_id=self.chunk_id,
            start=self.start,
            end=self.end,
        )


SourceReceipts = Annotated[tuple[SealedStorySourceRef, ...], Field(max_length=64)]


class StoryTransitionTime(EventModel):
    value: datetime | date | None = None
    precision: TimePrecision = "unknown"
    evidence_refs: SourceReceipts = ()

    @model_validator(mode="after")
    def precise(self) -> Self:
        # Reuse the source precision validator, preserving a date as a date.
        point = EventTimeValue(value=self.value, precision=self.precision)
        object.__setattr__(self, "value", point.value)
        if (self.precision == "unknown") != (not self.evidence_refs):
            raise ValueError("story.time_unbound")
        return self


class StoryTransitionTimeDraft(EventModel):
    value: datetime | date | None = None
    precision: TimePrecision = "unknown"
    evidence_refs: ContextRefs = ()

    @model_validator(mode="after")
    def precise(self) -> Self:
        point = EventTimeValue(value=self.value, precision=self.precision)
        object.__setattr__(self, "value", point.value)
        if (self.precision == "unknown") != (not self.evidence_refs):
            raise ValueError("story.time_unbound")
        return self


class VerifiedStoryDelta(EventModel):
    fact_ids: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=8)]
    delta_hash: Digest
    reader_text: Annotated[str, Field(min_length=1, max_length=240)]
    source_refs: Annotated[tuple[SealedStorySourceRef, ...], Field(min_length=1, max_length=64)]


class ResolutionTarget(EventModel):
    kind: Literal["same_occurrence", "linked_release_result"]
    occurrence_id: EventId | None = None
    thread_key_hash: Digest | None = None
    subject_ids: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=8)]
    period: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    required_metric_keys: Annotated[tuple[Digest, ...], Field(max_length=8)] = ()
    expected_status: Literal["actual", "scheduled", "quoted_opinion"]
    source_refs: Annotated[tuple[SealedStorySourceRef, ...], Field(min_length=1, max_length=64)]

    @model_validator(mode="after")
    def target_identity(self) -> Self:
        if self.kind == "same_occurrence" and self.occurrence_id is None:
            raise ValueError("story.resolution_unbound")
        if self.kind == "linked_release_result" and (
            self.thread_key_hash is None
            or self.period is None
            or not self.required_metric_keys
            or self.expected_status != "actual"
        ):
            raise ValueError("story.resolution_unbound")
        return self


class ObservationQuestion(EventModel):
    question_id: Digest
    kind: Literal[
        "release_result",
        "decision_outcome",
        "implementation_status",
        "agreement_outcome",
        "service_status",
        "correction_resolution",
        "source_confirmation",
    ]
    text: Annotated[str, Field(min_length=1, max_length=180)]
    subject_ids: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=8)]
    resolution_target: ResolutionTarget
    source_refs: Annotated[tuple[SealedStorySourceRef, ...], Field(min_length=1, max_length=64)]


class NextCheck(EventModel):
    kind: Literal["scheduled_fact", "observation_question"]
    text: Annotated[str, Field(min_length=1, max_length=240)]
    fact_id: Digest | None = None
    question_id: Digest | None = None
    scheduled_time: StoryTransitionTime | None = None
    source_refs: Annotated[tuple[SealedStorySourceRef, ...], Field(min_length=1, max_length=64)]

    @model_validator(mode="after")
    def source_backed_check(self) -> Self:
        if self.kind == "scheduled_fact":
            if (
                self.fact_id is None
                or self.question_id is not None
                or self.scheduled_time is None
                or self.scheduled_time.precision == "unknown"
            ):
                raise ValueError("story.next_check_unbound")
        elif (
            self.question_id is None or self.fact_id is not None or self.scheduled_time is not None
        ):
            raise ValueError("story.next_check_unbound")
        return self


class StoryRecord(EventModel):
    story_id: Digest
    segment: MarketSegment
    event_ids: Annotated[tuple[EventId, ...], Field(min_length=1, max_length=128)]
    latest_state: StoryState
    verified_delta: VerifiedStoryDelta | None = None
    open_question: ObservationQuestion | None = None
    next_check: NextCheck | None = None
    resolution_evidence: SourceReceipts = ()
    updated_at: datetime
    source_refs: Annotated[tuple[SealedStorySourceRef, ...], Field(min_length=1, max_length=64)]
    kind: EventKind
    disposition: StoryDisposition = "active"
    closed_at: datetime | None = None
    last_evidence_at: datetime
    state_time: StoryTransitionTime = StoryTransitionTime()
    related_story_ids: Annotated[tuple[Digest, ...], Field(max_length=4)] = ()

    @field_validator("updated_at", "last_evidence_at", "closed_at")
    @classmethod
    def utc_clock(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.utcoffset() is None:
                raise ValueError("story.clock_invalid")
            return value.astimezone(UTC)
        return value

    @model_validator(mode="after")
    def coherent_record(self) -> Self:
        if len(set(self.event_ids)) != len(self.event_ids) or len(
            set(self.related_story_ids)
        ) != len(self.related_story_ids):
            raise ValueError("story.record_invalid")
        terminal = self.latest_state in {"resolved", "cancelled"}
        if terminal != (self.disposition == "closed") or terminal != (self.closed_at is not None):
            raise ValueError("story.closure_unbound")
        if terminal and not self.resolution_evidence:
            raise ValueError("story.closure_unbound")
        if self.last_evidence_at > self.updated_at or (
            self.closed_at is not None and self.closed_at > self.updated_at
        ):
            raise ValueError("story.clock_invalid")
        if (
            self.next_check is not None
            and self.next_check.kind == "observation_question"
            and (
                self.open_question is None
                or self.next_check.question_id != self.open_question.question_id
            )
        ):
            raise ValueError("story.next_check_unbound")
        return self


def story_record_hash(record: StoryRecord) -> str:
    return event_digest("story-record-v3", record.model_dump(mode="json"))


class StoryTransitionProposal(EventModel):
    signal: StoryTransitionSignal
    proposed_state: StoryState
    evidence_refs: ContextRefs = ()
    occurrence_ids: tuple[EventId, ...] = ()
    resolution_fact_ids: Annotated[tuple[Digest, ...], Field(max_length=8)] = ()
    transition_time: StoryTransitionTimeDraft = StoryTransitionTimeDraft()


class StoryObservation(EventModel):
    story_hint: StoryIdentityHint
    event_id: EventId
    event_kind: EventKind
    fact_delta: EventFactDelta
    transition_proposal: StoryTransitionProposal
    question_proposal: ObservationQuestion | None = None
    next_check_proposal: NextCheck | None = None
    context_refs: ContextRefs
    observation_clock: datetime

    @field_validator("observation_clock")
    @classmethod
    def utc_clock(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("story.clock_invalid")
        return value.astimezone(UTC)


class StoryStateProposal(EventModel):
    story_id: Digest
    segment: MarketSegment
    prior_record_hash: Digest | None = None
    next_record: StoryRecord
    next_record_hash: Digest
    event_ids: tuple[EventId, ...]
    fact_ids: Annotated[tuple[Digest, ...], Field(max_length=8)]
    evidence_refs: ContextRefs
    observed_clock: datetime

    @model_validator(mode="after")
    def record_binding(self) -> Self:
        if (
            self.observed_clock.utcoffset() is None
            or self.observed_clock != self.next_record.updated_at
        ):
            raise ValueError("story.clock_invalid")
        if (
            self.story_id != self.next_record.story_id
            or self.segment != self.next_record.segment
            or self.next_record_hash != story_record_hash(self.next_record)
        ):
            raise ValueError("story.record_hash_mismatch")
        if not set(self.event_ids) <= set(self.next_record.event_ids) or not self.evidence_refs:
            raise ValueError("story.proposal_unbound")
        return self


class StoryPublicationDelta(EventModel):
    story_id: Digest
    segment: MarketSegment
    prior_state: StoryState | None = None
    next_state: StoryState
    event_ids: tuple[EventId, ...]
    fact_ids: Annotated[tuple[Digest, ...], Field(max_length=8)]
    prior_record_hash: Digest | None = None
    next_record: StoryRecord
    next_record_hash: Digest
    source_receipts: Annotated[tuple[SealedStorySourceRef, ...], Field(min_length=1, max_length=64)]
    observed_clock: datetime
    disposition: StoryDisposition

    @model_validator(mode="after")
    def record_binding(self) -> Self:
        if (
            self.observed_clock.utcoffset() is None
            or self.observed_clock != self.next_record.updated_at
        ):
            raise ValueError("story.clock_invalid")
        if (
            self.story_id != self.next_record.story_id
            or self.segment != self.next_record.segment
            or self.next_state != self.next_record.latest_state
            or self.disposition != self.next_record.disposition
            or self.next_record_hash != story_record_hash(self.next_record)
        ):
            raise ValueError("story.record_hash_mismatch")
        if not set(self.event_ids) <= set(self.next_record.event_ids):
            raise ValueError("story.delta_unbound")
        return self


class StoryLedger(EventModel):
    schema_version: Literal[3] = 3
    records: tuple[StoryRecord, ...] = ()

    @model_validator(mode="after")
    def unique_records(self) -> Self:
        if len({(r.segment, r.story_id) for r in self.records}) != len(self.records):
            raise ValueError("story.ledger_invalid")
        return self


class StoryTransitionResult(EventModel):
    record: StoryRecord | None
    disposition: Literal["applied", "unchanged", "limited", "conflict"]
    reason_code: Literal[
        "story.applied",
        "story.no_new_evidence",
        "story.source_unavailable",
        "story.transition_unbound",
        "story.state_conflict",
        "story.closed_immutable",
        "story.resolution_unbound",
        "story.record_budget_exhausted",
    ]
    proposed_delta: StoryStateProposal | None = None
