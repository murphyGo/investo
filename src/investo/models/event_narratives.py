"""Frozen versioned event narration; source identity remains owned by the plan."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, field_validator, model_validator

from investo.models.events import Digest, EventId, EventModel, EventSelectionPlan, EvidenceRef

ShortText = Annotated[str, Field(strict=True, min_length=1, max_length=80)]
Explanation = Annotated[str, Field(strict=True, min_length=1, max_length=180)]
NarrativeRefs = Annotated[tuple[EvidenceRef, ...], Field(max_length=64)]
SectionText = Annotated[str, Field(strict=True, min_length=1)]


class EventMeaning(EventModel):
    text: Explanation | None
    mode: Literal["source_reported", "conditional", "unavailable"]
    evidence_refs: NarrativeRefs = ()

    @model_validator(mode="after")
    def consistent_availability(self) -> Self:
        if self.mode == "unavailable":
            if self.text is not None or self.evidence_refs:
                raise ValueError("unavailable meaning must have null text and no refs")
        elif self.text is None or not self.evidence_refs:
            raise ValueError("available meaning requires text and source refs")
        return self


class EventReaction(EventModel):
    text: Explanation | None
    status: Literal["observed", "source_reported_no_reaction", "unavailable"]
    evidence_refs: NarrativeRefs = ()

    @model_validator(mode="after")
    def consistent_availability(self) -> Self:
        if self.status == "unavailable":
            if self.text is not None or self.evidence_refs:
                raise ValueError("unavailable reaction must have null text and no refs")
        elif self.text is None or not self.evidence_refs:
            raise ValueError("available reaction requires text and source refs")
        return self


class EventNarrative(EventModel):
    event_id: EventId
    headline: ShortText
    what_happened: Annotated[str, Field(strict=True, min_length=1, max_length=240)]
    fact_ids: Annotated[tuple[Digest, ...], Field(max_length=4)]
    source_refs: Annotated[tuple[EvidenceRef, ...], Field(min_length=1, max_length=64)]
    meaning: EventMeaning
    reaction: EventReaction


class Stage2Sections(EventModel):
    market_summary: SectionText
    sector_flow: SectionText
    indicators_events: SectionText
    notable_tickers: SectionText
    today_watch: SectionText


class Stage2OutputV2(EventModel):
    schema_version: Literal[2]
    sections: Stage2Sections
    events: Annotated[tuple[EventNarrative, ...], Field(max_length=5)]

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_version(cls, value: object) -> object:
        if type(value) is not int or value != 2:
            raise ValueError("event schema version must be integer 2")
        return value


class EventGenerationPayload(EventModel):
    plan: EventSelectionPlan
    narratives: Annotated[tuple[EventNarrative, ...], Field(max_length=5)]
    collection_limited: StrictBool = False
