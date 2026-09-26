"""Explicit event-generation policy; environment access stays at the entrypoint."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast

EventMode = Literal["off", "shadow", "preview", "active"]
EVENT_MODE_ENV = "INVESTO_EVENT_BRIEFING_MODE"

# These are code capabilities, never operator flags. Later units enable their
# consumers only after their parser/finalizer and quality contracts exist.
EVENT_PREVIEW_READY = False
EVENT_ACTIVE_READY = False


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
            raise ValueError("event activation requires the u157/u158/u159 consumer contract")

    @property
    def uses_v2(self) -> bool:
        return self.mode in ("preview", "active")


DEFAULT_EVENT_CONFIG = EventExecutionConfig()
