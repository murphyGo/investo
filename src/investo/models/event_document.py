"""Native event edition input and frozen, text-free public projections."""

from __future__ import annotations

import json
from datetime import date, datetime
from hashlib import sha256
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from investo.models.briefing import Briefing
from investo.models.event_asset_impact import EventAssetImpact
from investo.models.event_context import (
    ContextEventDraft,
    ContextRef,
    ContextRefs,
    EventContextDocument,
    EventSupportVector,
    MeaningContext,
    ReactionContext,
    RequiredContextRefs,
    TimePrecision,
)
from investo.models.event_identity import CanonicalEventBinding
from investo.models.event_story import (
    NextCheck,
    SealedStorySourceRef,
    SourceReceipts,
    StoryPublicationDelta,
    StoryState,
    StoryStateProposal,
)
from investo.models.events import Digest, EventId, EventModel, FactStatus, NumericWatchpoint
from investo.models.exchange_flows import ExchangeFlow
from investo.models.market_anchor import MarketAnchor
from investo.models.network_activity import NetworkActivity
from investo.models.option_expiry import OptionExpiry
from investo.models.segments import MarketSegment

PublicSourceLocator = SealedStorySourceRef
ContentEditionAvailability = Literal["normal", "quiet", "source_limited"]
Headline = Annotated[str, Field(strict=True, min_length=1, max_length=120)]
ShortText = Annotated[str, Field(strict=True, min_length=1, max_length=180)]
ArticleContextRefs = Annotated[tuple[ContextRef, ...], Field(min_length=1, max_length=64)]


class EditionAvailability(EventModel):
    status: ContentEditionAvailability
    reason_codes: tuple[
        Literal["no_eligible_events", "source_limited", "no_surviving_events"], ...
    ] = ()


class EditionNewsWindow(EventModel):
    start_utc: datetime
    end_utc: datetime

    @model_validator(mode="after")
    def aware_interval(self) -> Self:
        if (
            self.start_utc.utcoffset() is None
            or self.end_utc.utcoffset() is None
            or self.start_utc > self.end_utc
        ):
            raise ValueError("edition.news_window_invalid")
        return self


class EditorialEventPlan(EventModel):
    event_id: EventId
    source_event: ContextEventDraft
    required_fact_ids: Annotated[tuple[Digest, ...], Field(max_length=8)]
    assigned_refs: Annotated[tuple[ContextRef, ...], Field(min_length=1, max_length=128)]
    placement: Literal["article", "reference"] = "article"


class EditorialPlan(EventModel):
    events: Annotated[tuple[EditorialEventPlan, ...], Field(max_length=5)] = ()
    exclusions: tuple[
        tuple[
            EventId,
            Literal["repeat", "background", "conflict", "budget_deferred", "low_importance"],
        ],
        ...,
    ] = ()
    evidence_bytes: Annotated[int, Field(strict=True, ge=0, le=16384)] = 0

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        if len({e.event_id for e in self.events}) != len(self.events):
            raise ValueError("edition.selection_mismatch")
        return self


class EventArticle(EventModel):
    event_id: EventId
    headline: Headline
    what_changed: Annotated[str, Field(strict=True, min_length=1, max_length=600)]
    fact_ids: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=8)]
    source_refs: ArticleContextRefs
    background: ShortText | None = None
    background_refs: ContextRefs = ()
    meaning: MeaningContext = MeaningContext(mode="unavailable")
    reaction: ReactionContext = ReactionContext(status="unavailable", attribution="unavailable")


class EventDigest(EventModel):
    event_id: EventId
    fact_ids: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=8)]
    # Presentation bounds are checked after original hard findings. Oversized or
    # incomplete digests are omitted independently of their valid article.
    text: Annotated[str, Field(strict=True, min_length=1, max_length=600)]
    source_refs: RequiredContextRefs


class ContextPanel(EventModel):
    kind: Literal["background", "comparison", "sector", "asset"]
    event_id: EventId | None = None
    text: ShortText
    source_refs: RequiredContextRefs


class FollowUpEntry(EventModel):
    kind: Literal["event", "scheduled"]
    event_id: EventId
    story_id: Digest
    reader_state: StoryState
    basis: Literal["current_delta", "committed_history"] = "current_delta"
    last_evidence_at: datetime | None = None
    verified_delta_text: Annotated[str, Field(min_length=1, max_length=240)] | None = None
    question: ShortText | None = None
    next_check: NextCheck | None = None
    source_refs: ArticleContextRefs

    @model_validator(mode="after")
    def meaningful_follow_up(self) -> Self:
        if self.question is None and self.next_check is None and self.verified_delta_text is None:
            raise ValueError("edition.follow_up_unbound")
        if self.kind == "scheduled" and (
            self.next_check is None or self.next_check.kind != "scheduled_fact"
        ):
            raise ValueError("edition.follow_up_unbound")
        return self


class NumericFollowUpEntry(EventModel):
    kind: Literal["numeric"] = "numeric"
    event_id: EventId
    fact_ids: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=8)]
    source_refs: RequiredContextRefs
    numeric_values: NumericWatchpoint


EditionFollowUp = Annotated[FollowUpEntry | NumericFollowUpEntry, Field(discriminator="kind")]


class EventVisualInput(EventModel):
    event_id: EventId
    fact_ids: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=8)]
    source_refs: RequiredContextRefs
    relative_path: Annotated[
        str, Field(pattern=r"^20\d{2}-\d{2}-\d{2}\.assets/event-[0-9a-f]{24}\.svg$")
    ]
    dark_relative_path: Annotated[
        str, Field(pattern=r"^20\d{2}-\d{2}-\d{2}\.assets/event-[0-9a-f]{24}-dark\.svg$")
    ]
    artifact_ids: Annotated[tuple[str, ...], Field(min_length=3, max_length=3)]


class MarketReferencePanel(EventModel):
    anchors: Annotated[tuple[MarketAnchor, ...], Field(max_length=24)] = ()
    daily_network_activity: Annotated[tuple[NetworkActivity, ...], Field(max_length=4)] = ()
    daily_exchange_flows: Annotated[tuple[ExchangeFlow, ...], Field(max_length=2)] = ()
    calculated_option_expiries: Annotated[tuple[OptionExpiry, ...], Field(max_length=2)] = ()


class EventReferencePanel(EventModel):
    event_id: EventId
    fact_ids: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=8)]
    source_refs: ArticleContextRefs


class EventEditionContent(EventModel):
    schema_version: Literal[3] = 3
    articles: Annotated[tuple[EventArticle, ...], Field(max_length=5)] = ()
    digests: Annotated[tuple[EventDigest, ...], Field(max_length=3)] = ()
    context_panels: Annotated[tuple[ContextPanel, ...], Field(max_length=5)] = ()


class EventEditionDraft(EventEditionContent):
    segment: MarketSegment
    target_date: date
    price_reference_date: date | None = None
    price_time_basis: Literal["trading_date", "unavailable"] = "unavailable"
    news_window: EditionNewsWindow | None = None
    availability: EditionAvailability
    editorial_plan: EditorialPlan
    bindings: Annotated[tuple[CanonicalEventBinding, ...], Field(max_length=5, repr=False)] = ()
    documents: Annotated[tuple[EventContextDocument, ...], Field(max_length=96, repr=False)] = ()
    support: Annotated[tuple[EventSupportVector, ...], Field(max_length=5)] = ()
    market_reference: MarketReferencePanel = MarketReferencePanel()
    reference_panels: Annotated[tuple[EventReferencePanel, ...], Field(max_length=5)] = ()
    follow_ups: Annotated[tuple[EditionFollowUp, ...], Field(max_length=3)] = ()
    asset_impacts: Annotated[tuple[EventAssetImpact, ...], Field(max_length=16)] = ()
    visual_inputs: Annotated[tuple[EventVisualInput, ...], Field(max_length=5)] = ()
    story_proposals: Annotated[tuple[StoryStateProposal, ...], Field(max_length=3, repr=False)] = ()

    @model_validator(mode="after")
    def provenance(self) -> Self:
        if (self.price_reference_date is None) != (self.price_time_basis == "unavailable"):
            raise ValueError("edition.price_time_invalid")
        if self.availability.status == "quiet" and self.articles:
            raise ValueError("edition.availability_invalid")
        return self


class PublicTimeValue(EventModel):
    value: datetime | date | None
    precision: TimePrecision
    source_refs: SourceReceipts = ()


class PublicEventTime(EventModel):
    occurred_at: PublicTimeValue
    announced_at: PublicTimeValue
    published_at: PublicTimeValue
    received_at: PublicTimeValue
    reference_period: str | None = None
    reference_period_refs: SourceReceipts = ()


class PublicFactView(EventModel):
    fact_id: Digest
    subject_id: Digest
    object_id: Digest | None = None
    metric_key_hash: Digest | None = None
    reader_label: Annotated[str, Field(min_length=1, max_length=240)]
    value: Annotated[str, Field(min_length=1, max_length=240)]
    unit: str | None = None
    period: str | None = None
    status: FactStatus
    source_refs: SourceReceipts


class PublicMeaningView(EventModel):
    mode: Literal["source_reported", "conditional", "unavailable"]
    text: ShortText | None = None
    mechanism: ShortText | None = None
    assumptions: tuple[str, ...] = ()
    source_refs: SourceReceipts = ()


class PublicReactionView(EventModel):
    status: Literal["observed", "source_reported_no_reaction", "unavailable"]
    attribution: Literal["source_reported", "coincidence_only", "unavailable"]
    asset_id: str | None = None
    text: ShortText | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    observed_at: datetime | None = None
    source_refs: SourceReceipts = ()


class PublicFactCorrection(EventModel):
    old_fact_id: Digest
    new_fact_id: Digest
    source_claim: Annotated[str, Field(min_length=1, max_length=1200)]
    source_refs: SourceReceipts


class PublicEventView(EventModel):
    event_id: EventId
    actor_labels: tuple[str, ...]
    object_labels: tuple[str, ...]
    headline: Headline
    what_changed: Annotated[str, Field(min_length=1, max_length=600)]
    facts: Annotated[tuple[PublicFactView, ...], Field(min_length=1, max_length=8)]
    time: PublicEventTime
    background: ShortText | None = None
    meaning: PublicMeaningView
    reaction: PublicReactionView
    support: EventSupportVector
    source_refs: SourceReceipts
    story_id: Digest | None = None
    corrections: tuple[PublicFactCorrection, ...] = ()


class PublicDigestView(EventModel):
    event_id: EventId
    fact_ids: tuple[Digest, ...]
    text: Annotated[str, Field(min_length=1, max_length=140)]
    source_refs: SourceReceipts


class PublicFollowUpView(EventModel):
    kind: Literal["event", "scheduled"]
    event_id: EventId
    story_id: Digest
    reader_state: StoryState
    basis: Literal["current_delta", "committed_history"] = "current_delta"
    last_evidence_at: datetime | None = None
    verified_delta_text: Annotated[str, Field(min_length=1, max_length=240)] | None = None
    question: ShortText | None = None
    next_check: NextCheck | None = None
    source_refs: SourceReceipts


class PublicNumericFollowUpView(EventModel):
    kind: Literal["numeric"] = "numeric"
    event_id: EventId
    fact_ids: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=8)]
    source_refs: SourceReceipts
    numeric_values: NumericWatchpoint


PublicEditionFollowUp = Annotated[
    PublicFollowUpView | PublicNumericFollowUpView, Field(discriminator="kind")
]


class PublicAssetImpactView(EventModel):
    event_id: EventId
    asset_id: str
    relation: Literal["direct", "related"]
    mechanism: ShortText
    condition: ShortText | None = None
    fact_ids: tuple[Digest, ...]
    source_refs: SourceReceipts


class PublicReferencePanel(EventModel):
    event_id: EventId
    facts: Annotated[tuple[PublicFactView, ...], Field(min_length=1, max_length=8)]
    source_refs: SourceReceipts


class PublicContextPanel(EventModel):
    kind: Literal["background", "comparison", "sector", "asset"]
    event_id: EventId | None = None
    text: ShortText
    source_refs: SourceReceipts


class PublishedEventEdition(EventModel):
    schema_version: Literal[3] = 3
    segment: MarketSegment
    target_date: date
    archive_relative_path: str
    markdown_sha256: Digest
    projection_sha256: Digest
    price_reference_date: date | None
    price_time_basis: Literal["trading_date", "unavailable"]
    news_window: EditionNewsWindow | None
    availability: EditionAvailability
    events: Annotated[tuple[PublicEventView, ...], Field(max_length=5)]
    digests: Annotated[tuple[PublicDigestView, ...], Field(max_length=3)]
    follow_ups: Annotated[tuple[PublicEditionFollowUp, ...], Field(max_length=3)]
    asset_impacts: Annotated[tuple[PublicAssetImpactView, ...], Field(max_length=16)]
    story_publication_deltas: tuple[StoryPublicationDelta, ...] = ()
    reference_panels: Annotated[tuple[PublicReferencePanel, ...], Field(max_length=5)] = ()
    context_panels: Annotated[tuple[PublicContextPanel, ...], Field(max_length=5)] = ()

    @property
    def canonical_projection_hash(self) -> str:
        data = json.dumps(
            self.model_dump(mode="json", exclude={"projection_sha256"}),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return sha256(data.encode("utf-8")).hexdigest()


class PublicEditionView(EventModel):
    edition: PublishedEventEdition
    rendered_markdown: str

    @property
    def target_date(self) -> date:
        return self.edition.target_date

    @property
    def segment(self) -> MarketSegment:
        return self.edition.segment


GeneratedDraft = Briefing | EventEditionDraft
ReadablePublicDocument = Briefing | PublicEditionView
