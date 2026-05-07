"""Tests for u18 watchlist relevance helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from investo.briefing.watchlist import (
    WatchlistConfig,
    match_watchlist_items,
    render_watchlist_impact,
    render_watchlist_prompt_context,
)
from investo.models import NormalizedItem


def _item(title: str, summary: str | None = None) -> NormalizedItem:
    return NormalizedItem(
        source_name="yahoo-finance-news",
        category="news",
        title=title,
        summary=summary,
        published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
    )


def test_watchlist_config_normalizes_and_deduplicates_terms() -> None:
    config = WatchlistConfig(
        tickers=(" nvda ", "NVDA"),
        assets=("btc",),
        sectors=(" AI ",),
        keywords=("", "FOMC"),
    )

    assert config.tickers == ("NVDA",)
    assert config.assets == ("BTC",)
    assert config.sectors == ("AI",)
    assert config.keywords == ("FOMC",)
    assert config.is_configured


def test_match_watchlist_items_finds_ticker_asset_sector_and_keyword() -> None:
    config = WatchlistConfig(
        tickers=("NVDA",),
        assets=("BTC",),
        sectors=("semiconductor",),
        keywords=("FOMC",),
    )
    items = [
        _item("NVDA rallies after earnings", "semiconductor demand improves"),
        _item("Bitcoin ETF flow rises", "BTC liquidity improves"),
        _item("FOMC minutes published"),
    ]

    impact = match_watchlist_items(items, config)

    assert impact.configured
    assert {match.term for match in impact.matches} == {"NVDA", "semiconductor", "BTC", "FOMC"}
    rendered = render_watchlist_impact(impact)
    assert "4건 확인" in rendered
    assert "NVDA" in rendered
    assert "BTC" in rendered
    assert "Watchlist relevance" in render_watchlist_prompt_context(impact)


def test_watchlist_no_match_does_not_invent_impact() -> None:
    impact = match_watchlist_items([_item("Local weather")], WatchlistConfig(tickers=("AAPL",)))

    assert impact.configured
    assert impact.matches == ()
    assert "직접 연결된 수집 항목 없음" in render_watchlist_impact(impact)
    assert "Do not invent personal impact" in render_watchlist_prompt_context(impact)


def test_empty_watchlist_is_explicitly_unconfigured() -> None:
    impact = match_watchlist_items([_item("NVDA rallies")], WatchlistConfig())

    assert not impact.configured
    assert impact.matches == ()
    assert "관심 목록 미설정" in render_watchlist_impact(impact)
    assert render_watchlist_prompt_context(impact) == ""
