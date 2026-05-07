"""Input contracts for data-derived briefing visual cards."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from investo.briefing.segments import CoverageStatus, MarketSegment

CardKind = Literal[
    "data-confidence",
    "market-snapshot",
    "price-snapshot",
    "watchlist-relevance",
]


class _CardInput(BaseModel):
    """Shared immutable base for visual card input models."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_date: date
    segment: MarketSegment


class DataConfidenceCardInput(_CardInput):
    """Reader-facing source coverage and confidence state."""

    kind: Literal["data-confidence"] = "data-confidence"
    coverage_status: CoverageStatus
    item_count: int = Field(ge=0)
    source_count: int = Field(ge=0)
    missing_categories: tuple[str, ...] = Field(default_factory=tuple)


class MarketSnapshotCardInput(_CardInput):
    """Cleaned first-viewport narrative summary for a segment."""

    kind: Literal["market-snapshot"] = "market-snapshot"
    conclusion: str = Field(min_length=1, max_length=240)
    main_driver: str = Field(min_length=1, max_length=240)
    caution: str = Field(min_length=1, max_length=240)
    coverage_status: CoverageStatus


class PriceSnapshotRow(BaseModel):
    """One normalized price row supported by the visual renderer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(min_length=1, max_length=24)
    label: str | None = Field(default=None, max_length=80)
    price: str = Field(min_length=1, max_length=40)
    percent_change: str = Field(min_length=1, max_length=24)
    volume: str | None = Field(default=None, max_length=40)
    high: str | None = Field(default=None, max_length=40)
    low: str | None = Field(default=None, max_length=40)
    source_name: str = Field(min_length=1, max_length=100)


class PriceSnapshotCardInput(_CardInput):
    """Known-schema price rows for US equity and crypto visuals."""

    kind: Literal["price-snapshot"] = "price-snapshot"
    rows: tuple[PriceSnapshotRow, ...] = Field(min_length=1, max_length=12)


class WatchlistRelevanceRow(BaseModel):
    """One watchlist match safe for visual display."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    term: str = Field(min_length=1, max_length=80)
    kind: str = Field(min_length=1, max_length=24)
    source_name: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=240)
    url: HttpUrl | None = None


class WatchlistRelevanceCardInput(_CardInput):
    """Watchlist match summary without inferred investment impact."""

    kind: Literal["watchlist-relevance"] = "watchlist-relevance"
    configured: bool
    total_matches: int = Field(ge=0)
    rows: tuple[WatchlistRelevanceRow, ...] = Field(default_factory=tuple, max_length=3)


__all__ = [
    "CardKind",
    "DataConfidenceCardInput",
    "MarketSnapshotCardInput",
    "PriceSnapshotCardInput",
    "PriceSnapshotRow",
    "WatchlistRelevanceCardInput",
    "WatchlistRelevanceRow",
]
