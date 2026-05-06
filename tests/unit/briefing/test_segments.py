"""Tests for u7 market-segment routing."""

from __future__ import annotations

from datetime import UTC, datetime

from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY, segment_items
from investo.models import NormalizedItem


def _item(
    source_name: str,
    title: str,
    *,
    category: str = "news",
    summary: str | None = None,
) -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name,
        category=category,  # type: ignore[arg-type]
        title=title,
        summary=summary,
        published_at=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
    )


def test_yonhap_and_korean_ticker_route_to_domestic_equity() -> None:
    items = [
        _item("yonhap-market", "코스피 7,000 돌파"),
        _item("other-news", "삼성전자[005930] 외국인 순매수"),
    ]

    segmented = segment_items(items)

    assert segmented.domestic_equity == tuple(items)
    assert segmented.us_equity == ()
    assert segmented.crypto == ()


def test_us_sources_and_us_tickers_route_to_us_equity() -> None:
    items = [
        _item("yfinance-price", "S&P 500 close", category="price"),
        _item("sec-edgar-8k", "Apple files 8-K"),
        _item("other-news", "NVDA rallies after earnings"),
    ]

    segmented = segment_items(items)

    assert segmented.us_equity == tuple(items)
    assert segmented.domestic_equity == ()
    assert segmented.crypto == ()


def test_crypto_sources_and_crypto_terms_route_to_crypto() -> None:
    items = [
        _item("coingecko-price", "Bitcoin price snapshot", category="price"),
        _item("theblock-crypto", "Ethereum ETF inflows"),
        _item("other-news", "Stablecoin bill advances"),
    ]

    segmented = segment_items(items)

    assert segmented.crypto == tuple(items)
    assert segmented.domestic_equity == ()
    assert segmented.us_equity == ()


def test_fed_liquidity_item_can_route_to_us_and_crypto() -> None:
    item = _item("fomc-rss", "Federal Reserve liquidity update hits risk assets")

    segmented = segment_items([item])

    assert segmented.us_equity == (item,)
    assert segmented.crypto == (item,)
    assert segmented.domestic_equity == ()


def test_low_signal_unrelated_item_routes_nowhere() -> None:
    item = _item("weather", "Local weather update", summary="Rain expected")

    segmented = segment_items([item])

    assert segmented.domestic_equity == ()
    assert segmented.us_equity == ()
    assert segmented.crypto == ()


def test_data_limited_thresholds_are_segment_specific() -> None:
    items = [
        _item("yonhap-market", "코스피"),
        _item("yfinance-price", "S&P 500", category="price"),
        _item("coingecko-price", "BTC", category="price"),
    ]

    segmented = segment_items(items)

    assert segmented.is_data_limited(DOMESTIC_EQUITY)
    assert segmented.is_data_limited(US_EQUITY)
    assert segmented.is_data_limited(CRYPTO)
