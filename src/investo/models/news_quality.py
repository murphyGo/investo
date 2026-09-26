"""Closed public news-window diagnostics, measured before publication."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import Field, computed_field, field_validator, model_validator

from investo.models.events import EventModel
from investo.models.news_window import SourceName, utc_datetime


class NewsSourceObservation(EventModel):
    source_name: SourceName
    requested_start: datetime
    end_utc: datetime
    gap_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 0
    completeness: Literal["full", "partial", "unknown"] = "unknown"

    @field_validator("requested_start", "end_utc")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc_datetime(value)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end_utc <= self.requested_start:
            raise ValueError("observed news interval must be nonempty")
        return self


class NewsObservationQuality(EventModel):
    basis: Literal["terminal"] = "terminal"
    price_reference_date: date
    sources: Annotated[tuple[NewsSourceObservation, ...], Field(min_length=1, max_length=128)]

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({row.source_name for row in self.sources}) != len(self.sources):
            raise ValueError("duplicate news observation source")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def requested_start(self) -> datetime:
        return min(row.requested_start for row in self.sources)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def end_utc(self) -> datetime:
        return max(row.end_utc for row in self.sources)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def full_sources(self) -> int:
        return sum(row.completeness == "full" for row in self.sources)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def partial_sources(self) -> int:
        return sum(row.completeness == "partial" for row in self.sources)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def unknown_sources(self) -> int:
        return sum(row.completeness == "unknown" for row in self.sources)
