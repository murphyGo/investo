"""Tests for u7 market-segment routing."""

from __future__ import annotations

from datetime import UTC, datetime

from investo.briefing.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    build_segment_coverage,
    segment_items,
    segment_source_outcomes,
)
from investo.models import NormalizedItem, SourceOutcome


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
        _item("fsc-krx-index-price", "코스피 2,730.34", category="price"),
        _item("fsc-krx-stock-price", "삼성전자[005930] 72,000원", category="price"),
        _item("korea-policy-rss", "자본시장 제도 개선 발표"),
        _item("other-news", "삼성전자[005930] 외국인 순매수"),
    ]

    segmented = segment_items(items)

    assert segmented.domestic_equity == tuple(items)
    assert segmented.us_equity == ()
    assert segmented.crypto == ()


def test_us_sources_and_us_tickers_route_to_us_equity() -> None:
    items = [
        _item("yfinance-price", "S&P 500 close", category="price"),
        _item("treasury-rates", "UST curve: 10Y 4.31%", category="macro"),
        _item("us-economic-calendar", "BEA GDP release", category="calendar"),
        _item("sec-edgar-8k", "Apple files 8-K"),
        _item("other-news", "NVDA rallies after earnings"),
    ]

    segmented = segment_items(items)

    assert segmented.us_equity == tuple(items)
    assert segmented.domestic_equity == ()
    assert segmented.crypto == (items[1],)


def test_crypto_sources_and_crypto_terms_route_to_crypto() -> None:
    items = [
        _item("binance-crypto-market", "BTCUSDT 24h 76,050.12", category="price"),
        _item("coingecko-price", "Bitcoin price snapshot", category="price"),
        _item("defillama-market-structure", "DeFi TVL $74.0B", category="macro"),
        _item("theblock-crypto", "Ethereum ETF inflows"),
        _item("treasury-rates", "UST curve affects crypto liquidity", category="macro"),
        _item("other-news", "Stablecoin bill advances"),
    ]

    segmented = segment_items(items)

    assert segmented.crypto == tuple(items)
    assert segmented.domestic_equity == ()
    assert segmented.us_equity == (items[4],)


def test_us_only_source_with_fed_keywords_does_not_dual_route_to_crypto() -> None:
    """u45 — ``fomc-rss`` is anchored single-segment (us-equity).

    Pre-u45 the ``_CRYPTO_CROSS_MARKET_TERMS + Fed`` combo in
    ``_is_crypto`` allowed a us-only-source item to leak into crypto
    purely on its body keywords. After u45 the source allow-list wins:
    a fomc-rss item carrying "liquidity" + "Federal Reserve" stays in
    us-equity only.
    """
    item = _item("fomc-rss", "Federal Reserve liquidity update hits risk assets")

    segmented = segment_items([item])

    assert segmented.us_equity == (item,)
    assert segmented.crypto == ()
    assert segmented.domestic_equity == ()


def test_shared_treasury_rates_source_fans_out_to_us_and_crypto() -> None:
    """u45 — explicit shared-source fan-out is preserved.

    ``treasury-rates`` is the one source in ``_SHARED_SOURCES_BY_SEGMENT``
    today; its UST curve narrative is reader-relevant for both
    us-equity and crypto liquidity discussion.
    """
    item = _item("treasury-rates", "UST curve: 10Y 4.31%", category="macro")

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


def test_segment_coverage_statuses_are_normal_partial_or_failed() -> None:
    normal = build_segment_coverage(
        US_EQUITY,
        [
            _item("yfinance-price", "S&P 500", category="price"),
            _item("yahoo-finance-news", "AAPL news", category="news"),
            _item("fomc-rss", "Fed calendar", category="calendar"),
        ],
    )
    partial = build_segment_coverage(
        CRYPTO,
        [_item("coingecko-price", "Bitcoin price", category="price")],
    )
    # u54 — legacy "insufficient" enum migrated to "failed"; zero items
    # routed to the segment still yields the strictest tier.
    failed_coverage = build_segment_coverage(DOMESTIC_EQUITY, [])

    assert normal.status == "normal"
    assert normal.status_label == "정상"
    assert normal.missing_category_label == "없음"
    assert partial.status == "partial"
    assert partial.missing_categories == ("news",)
    assert partial.missing_category_label == "뉴스"
    assert failed_coverage.status == "failed"
    assert failed_coverage.status_label == "실패"
    assert failed_coverage.missing_categories == ("news", "price")


# ---------------------------------------------------------------------------
# u22 — coverage reason codes + per-source outcome wiring
# ---------------------------------------------------------------------------


def test_zero_items_segment_emits_zero_items_reason() -> None:
    coverage = build_segment_coverage(CRYPTO, [])
    assert "ZERO_ITEMS" in coverage.reason_codes
    assert "수집 항목 0건" in coverage.reason_labels


def test_below_threshold_segment_emits_below_threshold_reason() -> None:
    # CRYPTO threshold is 2 — one item triggers BELOW_THRESHOLD plus
    # MISSING_NEWS (price-only sample below).
    coverage = build_segment_coverage(
        CRYPTO,
        [_item("coingecko-price", "BTC price", category="price")],
    )
    assert "BELOW_THRESHOLD" in coverage.reason_codes
    assert "MISSING_NEWS" in coverage.reason_codes


def test_missing_category_reason_codes_match_missing_set() -> None:
    coverage = build_segment_coverage(
        US_EQUITY,
        [_item("yfinance-price", "AAPL", category="price")],
    )
    # US_EQUITY requires news + price; missing news.
    assert "MISSING_NEWS" in coverage.reason_codes
    assert "MISSING_PRICE" not in coverage.reason_codes


def test_source_failed_outcome_threads_into_reason_codes() -> None:
    outcome = SourceOutcome.from_failure(
        "fred-macro",
        "macro",
        message="connection reset",
        transient=True,
    )
    coverage = build_segment_coverage(
        US_EQUITY,
        [
            _item("yfinance-price", "AAPL", category="price"),
            _item("yahoo-finance-news", "AAPL news", category="news"),
            _item("fomc-rss", "Fed calendar", category="calendar"),
        ],
        source_outcomes=[outcome],
    )
    assert "SOURCE_FAILED" in coverage.reason_codes
    assert coverage.failed_source_outcomes == (outcome,)
    # Status is still "normal" because items are present and required
    # categories are covered — the failure is *informational* for the
    # reader, not a status downgrade.
    assert coverage.status == "normal"


def test_source_zero_outcome_threads_into_reason_codes() -> None:
    coverage = build_segment_coverage(
        CRYPTO,
        [
            _item("coingecko-price", "BTC", category="price"),
            _item("theblock-crypto", "ETH news", category="news"),
        ],
        source_outcomes=[SourceOutcome.zero("theblock-crypto", "news")],
    )
    assert "SOURCE_ZERO" in coverage.reason_codes


def test_segment_source_outcomes_filters_to_segment_allowlist() -> None:
    outcomes = (
        SourceOutcome.ok("yfinance-price", "price", item_count=3),
        SourceOutcome.ok("treasury-rates", "macro", item_count=1),
        SourceOutcome.ok("us-economic-calendar", "calendar", item_count=2),
        SourceOutcome.ok("binance-crypto-market", "price", item_count=3),
        SourceOutcome.ok("coingecko-price", "price", item_count=2),
        SourceOutcome.ok("defillama-market-structure", "macro", item_count=2),
        SourceOutcome.ok("fsc-krx-index-price", "price", item_count=3),
        SourceOutcome.ok("fsc-krx-stock-price", "price", item_count=5),
        SourceOutcome.ok("korea-policy-rss", "news", item_count=2),
        SourceOutcome.zero("yonhap-market", "news"),
    )
    crypto_only = segment_source_outcomes(CRYPTO, outcomes)
    domestic_only = segment_source_outcomes(DOMESTIC_EQUITY, outcomes)

    assert {outcome.source_name for outcome in crypto_only} == {
        "binance-crypto-market",
        "coingecko-price",
        "defillama-market-structure",
        "treasury-rates",
    }
    assert {outcome.source_name for outcome in domestic_only} == {
        "fsc-krx-index-price",
        "fsc-krx-stock-price",
        "korea-policy-rss",
        "yonhap-market",
    }


def test_coverage_failure_reason_does_not_carry_secret_after_filter() -> None:
    """The failure reason field on a SegmentCoverage outcome is the
    sanitized one — never the raw exception message.
    """
    outcome = SourceOutcome.from_failure(
        "yfinance-price",
        "price",
        message="GET https://example.com?api_key=ABCDEFG&fmt=json failed",
        transient=True,
    )
    coverage = build_segment_coverage(
        US_EQUITY,
        [_item("yfinance-price", "S&P 500", category="price")],
        source_outcomes=[outcome],
    )
    failed = coverage.failed_source_outcomes[0]
    assert failed.failure_reason is not None
    assert "api_key=ABCDEFG" not in failed.failure_reason
