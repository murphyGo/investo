"""Explicit event-generation policy; environment access stays at the entrypoint."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast

from investo.models.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY, MarketSegment

EventMode = Literal["off", "shadow", "preview", "active"]
EVENT_MODE_ENV = "INVESTO_EVENT_BRIEFING_MODE"

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

    def __post_init__(self) -> None:
        if self.mode not in ("off", "shadow", "preview", "active"):
            raise ValueError("event mode must be off, shadow, preview or active")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> EventExecutionConfig:
        raw = env.get(EVENT_MODE_ENV, "off").strip()
        if raw not in ("off", "shadow", "preview", "active"):
            raise ValueError("event mode must be off, shadow, preview or active")
        return cls(mode=cast("EventMode", raw))

    def validate_capabilities(self) -> None:
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
        return self.mode in ("preview", "active")

    def for_segment(self, segment: MarketSegment) -> EventExecutionConfig:
        if self.mode == "active" and segment not in EVENT_ACTIVE_SEGMENTS:
            return EventExecutionConfig("shadow")
        return self

    @property
    def v2_segments(self) -> tuple[MarketSegment, ...]:
        return tuple(
            segment
            for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)
            if self.for_segment(segment).uses_v2
        )


DEFAULT_EVENT_CONFIG = EventExecutionConfig()
