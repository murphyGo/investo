"""Macro event carryover lifecycle models for u59."""

from __future__ import annotations

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investo.models.segments import MarketSegment

MacroLifecycleStatus = Literal["scheduled", "unresolved", "confirmed", "stale"]


class MacroLifecycleEvent(BaseModel):
    """One watched macro event persisted across briefing runs.

    ``event_key`` is the stable join key. Scheduled and actual source
    items must confirm by this key, not by title substring matching.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_key: str = Field(min_length=1, max_length=256)
    label: str = Field(min_length=1, max_length=120)
    source_name: str = Field(min_length=1, max_length=80)
    segment: MarketSegment
    status: MacroLifecycleStatus
    scheduled_date: date | None = None
    confirmed_date: date | None = None
    follow_up_until: date | None = None

    @model_validator(mode="after")
    def _validate_status_dates(self) -> Self:
        if self.status == "scheduled" and self.scheduled_date is None:
            raise ValueError("scheduled macro lifecycle event requires scheduled_date")
        if self.status == "confirmed" and self.confirmed_date is None:
            raise ValueError("confirmed macro lifecycle event requires confirmed_date")
        return self


__all__ = [
    "MacroLifecycleEvent",
    "MacroLifecycleStatus",
]
