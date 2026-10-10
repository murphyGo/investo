"""Explicit event-generation policy; environment access stays at the entrypoint."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast

from investo.models.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY, MarketSegment

EventMode = Literal["off", "shadow", "preview", "active"]
EVENT_MODE_ENV = "INVESTO_EVENT_BRIEFING_MODE"
EVENT_DOCUMENT_SCHEMA_ENV = "INVESTO_EVENT_DOCUMENT_SCHEMA"
EVENT_V3_PREVIEW_READY = False
EVENT_V3_ACTIVE_READY = False

# The user authorized the event-body rollout on 2026-10-09 with outstanding
# human acceptance tracked separately. Runtime mode still defaults to off;
# preview publication and unqualified news/enrichment activation stay closed.
EVENT_PREVIEW_READY = True
EVENT_ACTIVE_READY = True
# Only these markets passed the reviewed live preview. Crypto retains v1
# shadow generation until its narrative failures receive a separate promotion.
EVENT_ACTIVE_SEGMENTS: tuple[MarketSegment, ...] = (DOMESTIC_EQUITY, US_EQUITY)


@dataclass(frozen=True, slots=True)
class EventExecutionConfig:
    mode: EventMode = "off"
    document_schema: Literal[2, 3] = 2
    active_segments: tuple[MarketSegment, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "active_segments", tuple(self.active_segments))
        if self.mode not in ("off", "shadow", "preview", "active"):
            raise ValueError("event mode must be off, shadow, preview or active")
        if type(self.document_schema) is not int or self.document_schema not in (2, 3):
            raise ValueError("event document schema must be two or three")
        if len(set(self.active_segments)) != len(self.active_segments) or any(
            segment not in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO) for segment in self.active_segments
        ):
            raise ValueError("event active segments must be distinct known markets")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> EventExecutionConfig:
        raw = env.get(EVENT_MODE_ENV, "off").strip()
        if raw not in ("off", "shadow", "preview", "active"):
            raise ValueError("event mode must be off, shadow, preview or active")
        schema = env.get(EVENT_DOCUMENT_SCHEMA_ENV, "2").strip()
        if schema not in ("2", "3"):
            raise ValueError("event document schema must be two or three")
        return cls(mode=cast("EventMode", raw), document_schema=cast("Literal[2, 3]", int(schema)))

    def validate_capabilities(self) -> None:
        if self.document_schema == 3:
            if self.mode == "preview" and not EVENT_V3_PREVIEW_READY:
                raise ValueError("schema-three preview requires the reviewed u169 consumer")
            if self.mode == "active" and (not EVENT_V3_ACTIVE_READY or not self.active_segments):
                raise ValueError("schema-three activation requires u172 market acceptance")
            return
        if self.mode == "preview" and not EVENT_PREVIEW_READY:
            raise ValueError("event preview requires the u158 v2 consumer")
        if self.mode == "active" and not EVENT_ACTIVE_READY:
            raise ValueError("event activation requires u157/u158/u159 operational acceptance")

    def validate_publication(self) -> None:
        if self.mode == "preview":
            raise ValueError("event preview requires the isolated non-public preview entrypoint")
        self.validate_capabilities()

    @property
    def uses_v2(self) -> bool:
        return self.document_schema == 2 and self.mode in ("preview", "active")

    @property
    def uses_v3(self) -> bool:
        return self.document_schema == 3 and self.mode in ("preview", "active")

    @property
    def uses_events(self) -> bool:
        return self.uses_v2 or self.uses_v3

    def for_segment(self, segment: MarketSegment) -> EventExecutionConfig:
        allowed = EVENT_ACTIVE_SEGMENTS if self.document_schema == 2 else self.active_segments
        if self.mode == "active" and segment not in allowed:
            return EventExecutionConfig("shadow", self.document_schema, self.active_segments)
        return self

    @property
    def v2_segments(self) -> tuple[MarketSegment, ...]:
        return tuple(
            segment
            for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)
            if self.for_segment(segment).uses_v2
        )

    @property
    def v3_segments(self) -> tuple[MarketSegment, ...]:
        return tuple(
            segment
            for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)
            if self.for_segment(segment).uses_v3
        )


DEFAULT_EVENT_CONFIG = EventExecutionConfig()
# One runtime type; retain the established import while exposing the C1 name.
EventGenerationPolicy = EventExecutionConfig
