"""Shared terminal public-notification DTOs.

The publisher derives this value from validated public-document bytes.  The
default segmented notifier consumes it without consulting generated briefing
fields.  Validation and extraction remain publisher responsibilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from investo._internal.text import bound_at_sentence
from investo.models.event_document import PublicEventView, PublishedEventEdition
from investo.models.segments import (
    COVERAGE_STATUS_LABELS,
    SEGMENT_LABELS,
    CoverageStatus,
    MarketSegment,
)


@dataclass(frozen=True, slots=True)
class PublicEventSummary:
    """A terminal event projection; never generated narrative input."""

    event_id: str
    headline: str
    fact_summary: str
    coverage: Literal["supported", "detail_limited"]

    def __post_init__(self) -> None:
        if len(self.event_id) != 24 or any(c not in "0123456789abcdef" for c in self.event_id):
            raise ValueError("event_id must be a canonical event identity")
        _require_clean_line(self.headline, field_name="headline")
        _require_clean_line(self.fact_summary, field_name="fact_summary")
        if len(self.headline) > 80 or len(self.fact_summary) > 180:
            raise ValueError("event summary exceeds its public bounds")
        if bound_at_sentence(self.fact_summary, 180, require_complete=True) != self.fact_summary:
            raise ValueError("fact_summary must contain complete sentences")
        if self.coverage not in {"supported", "detail_limited"}:
            raise ValueError("event summary coverage is unsupported")


@dataclass(frozen=True, slots=True)
class PublicNotificationSummary:
    """Minimal sealed input shared by publisher and notifier.

    Safety/extraction remains the publisher terminal validator's job. This
    shared DTO enforces the closed identity, coverage, and already-cleaned
    single-line shape so downstream consumers cannot receive an incoherent
    compatibility value.
    """

    segment: MarketSegment
    target_date: date
    conclusion: str
    coverage_status: CoverageStatus
    coverage_label: str
    watchlist: str | None = None
    events: tuple[PublicEventSummary, ...] = ()

    def __post_init__(self) -> None:
        if self.segment not in SEGMENT_LABELS:
            raise ValueError("segment must be a known market segment")
        if not isinstance(self.target_date, date) or isinstance(self.target_date, datetime):
            raise TypeError("target_date must be date")
        _require_clean_line(self.conclusion, field_name="conclusion")
        if self.coverage_status not in COVERAGE_STATUS_LABELS:
            raise ValueError("coverage_status must be a known status")
        if self.coverage_label != COVERAGE_STATUS_LABELS[self.coverage_status]:
            raise ValueError("coverage_label must match coverage_status")
        if self.watchlist is not None:
            _require_clean_line(self.watchlist, field_name="watchlist")
        events = tuple(self.events)
        if any(not isinstance(event, PublicEventSummary) for event in events):
            raise TypeError("notification events must be PublicEventSummary")
        if len(events) > 3 or len({event.event_id for event in events}) != len(events):
            raise ValueError("notification events must be at most three distinct events")
        object.__setattr__(self, "events", events)


def _require_clean_line(value: str, *, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str")
    if not value or value != value.strip() or "\n" in value or "\r" in value:
        raise ValueError(f"{field_name} must be a non-empty cleaned single line")


@dataclass(frozen=True, slots=True)
class EventNotificationSummaryV3:
    """Terminal native edition, with digest → headline → availability fallback."""

    edition: PublishedEventEdition

    @property
    def segment(self) -> MarketSegment:
        return self.edition.segment

    @property
    def target_date(self) -> date:
        return self.edition.target_date

    @property
    def conclusion(self) -> str:
        if self.edition.digests:
            return self.edition.digests[0].text
        if self.edition.events:
            return self.edition.events[0].headline
        return (
            "출처 수집 제한"
            if self.edition.availability.status == "source_limited"
            else "새로운 주요 사건을 선정하지 못했습니다."
        )

    @property
    def coverage_status(self) -> CoverageStatus:
        return "limited" if self.edition.availability.status == "source_limited" else "normal"

    @property
    def coverage_label(self) -> str:
        return COVERAGE_STATUS_LABELS[self.coverage_status]

    @property
    def events(self) -> tuple[PublicEventView, ...]:
        return self.edition.events

    @property
    def watchlist(self) -> None:
        return None


TerminalNotificationSummary = PublicNotificationSummary | EventNotificationSummaryV3


__all__ = ["PublicEventSummary", "PublicNotificationSummary"]
