"""Input contracts for data-derived briefing visual cards."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from investo.briefing.segments import (
    CATEGORY_LABELS,
    COVERAGE_REASON_LABELS,
    CoverageStatus,
    MarketSegment,
    SegmentCoverage,
)
from investo.briefing.watchlist import WatchlistImpact
from investo.models import NormalizedItem

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


class DataConfidenceSourceRow(BaseModel):
    """One adapter's verdict surfaced on the data-confidence card."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_name: str = Field(min_length=1, max_length=100)
    status: Literal["ok", "zero", "failed"]
    detail: str = Field(default="", max_length=160)


class DataConfidenceCardInput(_CardInput):
    """Reader-facing source coverage and confidence state."""

    kind: Literal["data-confidence"] = "data-confidence"
    coverage_status: CoverageStatus
    item_count: int = Field(ge=0)
    source_count: int = Field(ge=0)
    missing_categories: tuple[str, ...] = Field(default_factory=tuple)
    reason_labels: tuple[str, ...] = Field(default_factory=tuple, max_length=8)
    source_rows: tuple[DataConfidenceSourceRow, ...] = Field(default_factory=tuple, max_length=12)


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

    @field_validator("symbol", "price", "percent_change", "source_name")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        return stripped


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

    @field_validator("term", "kind", "source_name", "title")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        return stripped


class WatchlistRelevanceCardInput(_CardInput):
    """Watchlist match summary without inferred investment impact."""

    kind: Literal["watchlist-relevance"] = "watchlist-relevance"
    configured: bool
    total_matches: int = Field(ge=0)
    rows: tuple[WatchlistRelevanceRow, ...] = Field(default_factory=tuple, max_length=3)


def build_data_confidence_card(
    target_date: date,
    coverage: SegmentCoverage,
) -> DataConfidenceCardInput:
    """Build a data confidence card from deterministic segment coverage.

    u22 — exposes ``reason_labels`` (Korean labels for every reason
    code on the coverage) and ``source_rows`` (per-adapter verdict).
    Failure detail is taken from the already-sanitized
    ``failure_reason`` on the underlying outcome; never from the raw
    exception. Healthy adapters are summarized as a single trailing
    "정상 N개" line so the card stays visually compact.
    """
    return DataConfidenceCardInput(
        target_date=target_date,
        segment=coverage.segment,
        coverage_status=coverage.status,
        item_count=coverage.item_count,
        source_count=coverage.source_count,
        missing_categories=tuple(
            CATEGORY_LABELS[category] for category in coverage.missing_categories
        ),
        reason_labels=tuple(COVERAGE_REASON_LABELS[code] for code in coverage.reason_codes),
        source_rows=_build_data_confidence_source_rows(coverage),
    )


def _build_data_confidence_source_rows(
    coverage: SegmentCoverage,
) -> tuple[DataConfidenceSourceRow, ...]:
    rows: list[DataConfidenceSourceRow] = []
    for outcome in coverage.failed_source_outcomes:
        rows.append(
            DataConfidenceSourceRow(
                source_name=outcome.source_name,
                status="failed",
                detail=(outcome.failure_reason or "사유 미확인")[:160],
            )
        )
    for outcome in coverage.zero_source_outcomes:
        rows.append(
            DataConfidenceSourceRow(
                source_name=outcome.source_name,
                status="zero",
                detail="0건 반환",
            )
        )
    ok = coverage.ok_source_outcomes
    if ok:
        names = ", ".join(outcome.source_name for outcome in ok[:3])
        if len(ok) > 3:
            names = f"{names} 외 {len(ok) - 3}개"
        rows.append(
            DataConfidenceSourceRow(
                source_name=f"정상 {len(ok)}개",
                status="ok",
                detail=names,
            )
        )
    return tuple(rows)


def build_price_snapshot_card(
    target_date: date,
    segment: MarketSegment,
    items: Sequence[NormalizedItem],
) -> PriceSnapshotCardInput | None:
    """Build a price snapshot card from known source metadata, or return None."""
    rows: list[PriceSnapshotRow] = []
    for item in items:
        row = _price_row_from_item(item)
        if row is not None:
            rows.append(row)
        if len(rows) >= 12:
            break
    if not rows:
        return None
    return PriceSnapshotCardInput(target_date=target_date, segment=segment, rows=tuple(rows))


def build_watchlist_relevance_card(
    target_date: date,
    segment: MarketSegment,
    impact: WatchlistImpact,
) -> WatchlistRelevanceCardInput:
    """Build a watchlist card that reports matches without inferring impact."""
    rows = tuple(
        WatchlistRelevanceRow(
            term=match.term,
            kind=match.kind,
            source_name=match.item.source_name,
            title=match.item.title,
            url=match.item.url,
        )
        for match in impact.matches[:3]
    )
    return WatchlistRelevanceCardInput(
        target_date=target_date,
        segment=segment,
        configured=impact.configured,
        total_matches=len(impact.matches),
        rows=rows,
    )


def _price_row_from_item(item: NormalizedItem) -> PriceSnapshotRow | None:
    if item.source_name == "yfinance-price":
        return _yfinance_price_row(item)
    if item.source_name == "coingecko-price":
        return _coingecko_price_row(item)
    return None


def _yfinance_price_row(item: NormalizedItem) -> PriceSnapshotRow | None:
    metadata = item.raw_metadata
    ticker = metadata.get("ticker")
    close = metadata.get("close")
    prev_close = metadata.get("prev_close")
    high = metadata.get("high")
    low = metadata.get("low")
    volume = metadata.get("volume")
    if not isinstance(ticker, str) or not isinstance(close, str):
        return None
    pct = _format_percent_change(close, prev_close if isinstance(prev_close, str) else None)
    return PriceSnapshotRow(
        symbol=ticker,
        price=_format_number_text(close),
        percent_change=pct,
        volume=_format_number_text(volume) if isinstance(volume, str) else None,
        high=_format_number_text(high) if isinstance(high, str) else None,
        low=_format_number_text(low) if isinstance(low, str) else None,
        source_name=item.source_name,
    )


def _coingecko_price_row(item: NormalizedItem) -> PriceSnapshotRow | None:
    metadata = item.raw_metadata
    symbol = metadata.get("symbol")
    price = metadata.get("price_usd")
    pct = metadata.get("pct_24h")
    high = metadata.get("high_24h")
    low = metadata.get("low_24h")
    volume = metadata.get("volume_24h")
    if not isinstance(symbol, str) or not isinstance(price, str) or not isinstance(pct, str):
        return None
    return PriceSnapshotRow(
        symbol=symbol.upper(),
        price=f"${_format_number_text(price)}",
        percent_change=_format_percent_text(pct),
        volume=f"${_format_number_text(volume)}" if isinstance(volume, str) else None,
        high=f"${_format_number_text(high)}" if isinstance(high, str) else None,
        low=f"${_format_number_text(low)}" if isinstance(low, str) else None,
        source_name=item.source_name,
    )


def _format_percent_change(current: str, previous: str | None) -> str:
    current_float = _parse_float(current)
    previous_float = _parse_float(previous) if previous is not None else None
    if current_float is None or previous_float is None or previous_float == 0.0:
        return "n/a"
    pct = (current_float - previous_float) / previous_float * 100.0
    return f"{pct:+.2f}%"


def _format_percent_text(value: str) -> str:
    parsed = _parse_float(value)
    if parsed is None:
        return "n/a"
    return f"{parsed:+.2f}%"


def _format_number_text(value: str | None) -> str:
    parsed = _parse_float(value)
    if parsed is None:
        return "n/a"
    if abs(parsed) >= 1_000_000_000:
        return f"{parsed / 1_000_000_000:,.2f}B"
    if abs(parsed) >= 1_000_000:
        return f"{parsed / 1_000_000:,.2f}M"
    if abs(parsed) >= 1_000:
        return f"{parsed:,.2f}"
    return f"{parsed:,.2f}"


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


__all__ = [
    "CardKind",
    "DataConfidenceCardInput",
    "DataConfidenceSourceRow",
    "MarketSnapshotCardInput",
    "PriceSnapshotCardInput",
    "PriceSnapshotRow",
    "WatchlistRelevanceCardInput",
    "WatchlistRelevanceRow",
    "build_data_confidence_card",
    "build_price_snapshot_card",
    "build_watchlist_relevance_card",
]
