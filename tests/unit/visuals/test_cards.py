"""Tests for u19 visual card input contracts."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from investo.briefing.segments import build_segment_coverage
from investo.briefing.watchlist import WatchlistConfig, match_watchlist_items
from investo.models import NormalizedItem
from investo.visuals.cards import (
    DataConfidenceCardInput,
    MarketSnapshotCardInput,
    PriceSnapshotCardInput,
    PriceSnapshotRow,
    WatchlistRelevanceCardInput,
    WatchlistRelevanceRow,
    build_data_confidence_card,
    build_price_snapshot_card,
    build_watchlist_relevance_card,
)


def _item(
    source_name: str,
    category: str,
    title: str,
    *,
    raw_metadata: dict[str, str] | None = None,
    summary: str | None = None,
) -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name,
        category=category,  # type: ignore[arg-type]
        title=title,
        summary=summary,
        url="https://example.com/item",
        published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        raw_metadata=raw_metadata or {},
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


def test_build_data_confidence_card_from_segment_coverage() -> None:
    coverage = build_segment_coverage(
        "crypto",
        [_item("coingecko-price", "price", "BTC $100")],
    )

    card = build_data_confidence_card(date(2026, 5, 7), coverage)

    assert card.segment == "crypto"
    assert card.coverage_status == "partial"
    assert card.item_count == 1
    assert card.source_count == 1
    assert card.missing_categories == ("뉴스",)
    # u22 — reasons + source rows surface on the card.
    assert "뉴스 카테고리 누락" in card.reason_labels
    assert "최소 수집 기준 미달" in card.reason_labels


def test_build_data_confidence_card_includes_failed_and_zero_source_rows() -> None:
    from investo.models import SourceOutcome

    items = [
        _item("yfinance-price", "price", "AAPL"),
        _item("yahoo-finance-news", "news", "AAPL news"),
        _item("fomc-rss", "calendar", "FOMC"),
    ]
    outcomes = [
        SourceOutcome.from_failure(
            "fred-macro",
            "macro",
            message="connection reset",
            transient=True,
        ),
        SourceOutcome.zero("nasdaq-earnings-calendar", "earnings"),
        SourceOutcome.ok("yfinance-price", "price", item_count=1),
        SourceOutcome.ok("yahoo-finance-news", "news", item_count=1),
        SourceOutcome.ok("fomc-rss", "calendar", item_count=1),
    ]
    coverage = build_segment_coverage("us-equity", items, source_outcomes=outcomes)

    card = build_data_confidence_card(date(2026, 5, 7), coverage)

    statuses = [row.status for row in card.source_rows]
    assert statuses[0] == "failed"
    assert "zero" in statuses
    assert any(row.status == "ok" for row in card.source_rows)
    failed_row = card.source_rows[0]
    assert failed_row.source_name == "fred-macro"
    assert "connection reset" in failed_row.detail


def test_build_data_confidence_card_does_not_leak_secret_via_failure_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from investo.models import SourceOutcome

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "supersecret-token-value-xyz")
    items = [_item("coingecko-price", "price", "BTC", raw_metadata={"symbol": "btc"})]
    outcomes = [
        SourceOutcome.from_failure(
            "theblock-crypto",
            "news",
            message="boom supersecret-token-value-xyz on chat 1234567890",
            transient=True,
        ),
    ]
    coverage = build_segment_coverage("crypto", items, source_outcomes=outcomes)

    card = build_data_confidence_card(date(2026, 5, 7), coverage)

    detail = card.source_rows[0].detail
    assert "supersecret-token-value-xyz" not in detail
    assert "1234567890" not in detail
    assert "[REDACTED" in detail


def test_build_price_snapshot_card_maps_known_yfinance_and_coingecko_metadata() -> None:
    yfinance = _item(
        "yfinance-price",
        "price",
        "AAPL 272.26 (+0.77%)",
        raw_metadata={
            "ticker": "AAPL",
            "close": "272.255",
            "prev_close": "270.17",
            "high": "273.00",
            "low": "268.00",
            "volume": "12345678",
        },
    )
    coingecko = _item(
        "coingecko-price",
        "price",
        "BTC $76,105.00 (+0.33%)",
        raw_metadata={
            "symbol": "btc",
            "price_usd": "76105",
            "pct_24h": "0.3321",
            "volume_24h": "42000000000",
            "market_cap": "1500000000000",
            "high_24h": "76529",
            "low_24h": "75103",
        },
    )
    ignored = _item("other-price", "price", "Unknown")

    card = build_price_snapshot_card(date(2026, 5, 7), "us-equity", [yfinance, coingecko, ignored])

    assert card is not None
    assert [row.symbol for row in card.rows] == ["AAPL", "BTC"]
    assert card.rows[0].percent_change == "+0.77%"
    assert card.rows[1].price == "$76,105.00"
    assert card.rows[1].percent_change == "+0.33%"


def test_build_price_snapshot_card_omits_unknown_or_incomplete_metadata() -> None:
    assert (
        build_price_snapshot_card(
            date(2026, 5, 7),
            "domestic-equity",
            [_item("yfinance-price", "price", "Missing metadata", raw_metadata={"ticker": "AAPL"})],
        )
        is None
    )


def test_build_watchlist_relevance_card_limits_rows_and_avoids_impact_claims() -> None:
    items = [
        _item("yahoo-finance-news", "news", "NVDA rallies after earnings"),
        _item("yahoo-finance-news", "news", "AAPL unveils new device"),
        _item("coingecko-price", "price", "BTC $76,105.00"),
        _item("fomc-rss", "calendar", "FOMC minutes published"),
    ]
    impact = match_watchlist_items(
        items,
        WatchlistConfig(tickers=("NVDA", "AAPL"), assets=("BTC",), keywords=("FOMC",)),
    )

    card = build_watchlist_relevance_card(date(2026, 5, 7), "us-equity", impact)

    assert card.total_matches == 4
    assert len(card.rows) == 3
    assert "impact" not in card.model_dump()
