"""Shared terminal public-notification DTOs.

The publisher derives this value from validated public-document bytes.  The
default segmented notifier consumes it without consulting generated briefing
fields.  Validation and extraction remain publisher responsibilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from investo.models.segments import (
    COVERAGE_STATUS_LABELS,
    SEGMENT_LABELS,
    CoverageStatus,
    MarketSegment,
)


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


def _require_clean_line(value: str, *, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str")
    if not value or value != value.strip() or "\n" in value or "\r" in value:
        raise ValueError(f"{field_name} must be a non-empty cleaned single line")


__all__ = ["PublicNotificationSummary"]
