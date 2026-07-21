"""Shared terminal public-notification DTOs.

The publisher derives this value from validated public-document bytes.  The
default segmented notifier consumes it without consulting generated briefing
fields.  Validation and extraction remain publisher responsibilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from investo.models.segments import CoverageStatus, MarketSegment


@dataclass(frozen=True, slots=True)
class PublicNotificationSummary:
    """Minimal sealed input shared by publisher and notifier."""

    segment: MarketSegment
    target_date: date
    conclusion: str
    coverage_status: CoverageStatus
    coverage_label: str
    watchlist: str | None = None


__all__ = ["PublicNotificationSummary"]
