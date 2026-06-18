"""Verified high-drift fact snapshots.

This model surface is intentionally separate from ``CoreFact``. Core facts
verify numeric market anchors; these snapshots verify current entity-role facts
such as the current Federal Reserve chair.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from investo.models._validators import ensure_tz_aware, reject_blank_strict

FactId = Literal["fed.current_chair"]
FactStatus = Literal["fresh", "stale", "missing", "failed"]
FactSourceTier = Literal["S", "A", "B", "C"]


class FactSnapshot(BaseModel):
    """One source-backed observation for a verified current fact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fact_id: FactId
    value: str = Field(min_length=1)
    label_ko: str | None = None
    aliases: tuple[str, ...] = ()
    role: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    source_tier: FactSourceTier
    observed_at: datetime
    expires_at: datetime
    status: FactStatus
    raw_evidence_label: str = Field(min_length=1, max_length=160)

    @field_validator("value", "role", "source_name", "source_url", "raw_evidence_label")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        return reject_blank_strict(value)

    @field_validator("label_ko")
    @classmethod
    def _normalize_label_ko(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("aliases")
    @classmethod
    def _normalize_aliases(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        out: list[str] = []
        seen: set[str] = set()
        for alias in value:
            stripped = reject_blank_strict(alias)
            if stripped in seen:
                continue
            seen.add(stripped)
            out.append(stripped)
        return tuple(out)

    @field_validator("observed_at", "expires_at")
    @classmethod
    def _ensure_tz_aware(cls, value: datetime) -> datetime:
        return ensure_tz_aware(value)

    @model_validator(mode="after")
    def _validate_window(self) -> FactSnapshot:
        if self.expires_at <= self.observed_at:
            raise ValueError("expires_at must be after observed_at")
        return self


class VerifiedFactBundle(BaseModel):
    """Fact snapshots available to one briefing run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_date: date
    facts: tuple[FactSnapshot, ...] = ()

    def get(self, fact_id: FactId) -> FactSnapshot | None:
        for fact in self.facts:
            if fact.fact_id == fact_id:
                return fact
        return None

    def fresh(self, fact_id: FactId, now_utc: datetime) -> FactSnapshot | None:
        ensure_tz_aware(now_utc)
        fact = self.get(fact_id)
        if fact is None:
            return None
        if fact.status != "fresh":
            return None
        if fact.expires_at <= now_utc:
            return None
        return fact


__all__ = [
    "FactId",
    "FactSnapshot",
    "FactSourceTier",
    "FactStatus",
    "VerifiedFactBundle",
]
