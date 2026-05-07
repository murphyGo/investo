"""Tests for u19 visual card input contracts."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from investo.visuals.cards import (
    DataConfidenceCardInput,
    MarketSnapshotCardInput,
    PriceSnapshotCardInput,
    PriceSnapshotRow,
    WatchlistRelevanceCardInput,
    WatchlistRelevanceRow,
)


def test_data_confidence_card_input_is_strict_and_immutable() -> None:
    card = DataConfidenceCardInput(
        target_date=date(2026, 5, 7),
        segment="us-equity",
        coverage_status="partial",
        item_count=12,
        source_count=4,
        missing_categories=("가격",),
    )

    assert card.kind == "data-confidence"
    assert card.missing_categories == ("가격",)
    with pytest.raises(ValidationError):
        DataConfidenceCardInput(
            target_date=date(2026, 5, 7),
            segment="us-equity",
            coverage_status="partial",
            item_count=-1,
            source_count=4,
        )


def test_market_snapshot_card_rejects_blank_required_text() -> None:
    with pytest.raises(ValidationError):
        MarketSnapshotCardInput(
            target_date=date(2026, 5, 7),
            segment="crypto",
            conclusion="",
            main_driver="BTC liquidity improved",
            caution="Data coverage is partial",
            coverage_status="partial",
        )


def test_price_snapshot_card_requires_at_least_one_known_row() -> None:
    row = PriceSnapshotRow(
        symbol="NVDA",
        price="1,024.00",
        percent_change="+2.15%",
        volume="30,000,000",
        high="1,030.00",
        low="990.00",
        source_name="yfinance-price",
    )
    card = PriceSnapshotCardInput(
        target_date=date(2026, 5, 7),
        segment="us-equity",
        rows=(row,),
    )

    assert card.kind == "price-snapshot"
    assert card.rows[0].symbol == "NVDA"
    with pytest.raises(ValidationError):
        PriceSnapshotCardInput(
            target_date=date(2026, 5, 7),
            segment="us-equity",
            rows=(),
        )


def test_watchlist_relevance_card_does_not_have_impact_claim_fields() -> None:
    row = WatchlistRelevanceRow(
        term="NVDA",
        kind="ticker",
        source_name="yahoo-finance-news",
        title="NVDA rallies after earnings",
        url="https://example.com/nvda",
    )
    card = WatchlistRelevanceCardInput(
        target_date=date(2026, 5, 7),
        segment="us-equity",
        configured=True,
        total_matches=1,
        rows=(row,),
    )

    assert card.kind == "watchlist-relevance"
    assert "impact" not in card.model_dump()
    with pytest.raises(ValidationError):
        WatchlistRelevanceCardInput(
            target_date=date(2026, 5, 7),
            segment="us-equity",
            configured=True,
            total_matches=1,
            rows=(row, row, row, row),
        )
