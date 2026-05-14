"""u45 — anti-regression tests for segment-routing exclusivity.

Each scenario fixes a leak observed in the 2026-05-08 us-equity trace
footer (or guards a previously valid behaviour against the new rules):

* **R1** — ``theblock-crypto`` + body "SEC charges Hyperliquid"
  (Item #54). Pre-u45 the ``"sec "`` keyword in ``_US_MARKET_TERMS``
  pulled this item into us-equity; the new source-anchored rule keeps
  it crypto-only.
* **R2** — ``yahoo-finance-news`` + title "Bitcoin and ethereum prices
  today" (Item #76). Pre-u45 the source allow-list match alone routed
  it to us-equity even though the title was unambiguously crypto;
  ``_has_strong_crypto_signal`` now overrides for us-only sources.
* **R3** — ``yahoo-finance-news`` + title starting with "S&P 500"
  (regression guard for ordinary US market news).
* **R4** — ``treasury-rates`` shared-source fan-out remains intentional.
* **R5** — ``cnbc-top-news`` + Federal-Reserve body — the Fed keyword
  alone no longer dual-routes (us-equity only).
* **R6** — ``theblock-crypto`` + body "Federal Reserve and BTC" — the
  ``_CRYPTO_CROSS_MARKET_TERMS + Fed`` combo is no longer evaluated for
  source-anchored items, so this stays crypto-only.
* **R7** — orphan low-signal item is dropped (no segment).

Plus an invariant test: across a representative mix, every non-shared
item lands in at most one segment.
"""

from __future__ import annotations

from datetime import UTC, datetime

from investo.briefing.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
    segment_items,
)
from investo.models import NormalizedItem

_SHARED_SOURCES = frozenset({"treasury-rates"})


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
        published_at=datetime(2026, 5, 8, 12, 0, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# Anti-regression — leaks observed in 2026-05-08 us-equity trace footer
# ---------------------------------------------------------------------------


def test_r1_theblock_crypto_with_sec_keyword_stays_crypto_only() -> None:
    """Item #54 anti-regression — Hyperliquid + SEC."""
    item = _item(
        "theblock-crypto",
        "Hyperliquid loss",
        summary="SEC charges Hyperliquid trader over wash trades",
    )

    segmented = segment_items([item])

    assert segmented.crypto == (item,)
    assert segmented.us_equity == ()
    assert segmented.domestic_equity == ()


def test_r2_yahoo_finance_with_bitcoin_title_moves_to_crypto() -> None:
    """Item #76 anti-regression — yahoo-finance + crypto title prefix."""
    item = _item(
        "yahoo-finance-news",
        "Bitcoin and ethereum prices today",
        summary="Daily BTC and ETH snapshot for retail readers.",
    )

    segmented = segment_items([item])

    assert segmented.crypto == (item,)
    assert segmented.us_equity == ()


def test_r2b_yahoo_finance_with_consensus_crypto_title_moves_to_crypto() -> None:
    """Item #82 anti-regression — yahoo-finance + crypto-conference title.

    The title carries the explicit ticker ``BTC`` further down (not
    here), so the move is driven by the ``crypto`` prefix token.
    """
    item = _item(
        "yahoo-finance-news",
        "Crypto: 7 ideas from Consensus that show crypto's shift toward TradFi",
    )

    segmented = segment_items([item])

    assert segmented.crypto == (item,)
    assert segmented.us_equity == ()


def test_r3_yahoo_finance_with_general_market_title_stays_us_equity() -> None:
    """Regression guard — ordinary US market news keeps us-equity routing."""
    item = _item(
        "yahoo-finance-news",
        "S&P 500 reaches new high as megacaps rally",
    )

    segmented = segment_items([item])

    assert segmented.us_equity == (item,)
    assert segmented.crypto == ()


def test_r4_treasury_rates_shared_source_fans_out_intentionally() -> None:
    """Shared-source cross-routing preserved by explicit allow-list."""
    item = _item("treasury-rates", "UST 10Y 4.31%", category="macro")

    segmented = segment_items([item])

    assert segmented.us_equity == (item,)
    assert segmented.crypto == (item,)


def test_r5_cnbc_with_fed_keyword_routes_to_us_equity_only() -> None:
    """``cnbc-top-news`` is us-only; Fed keyword no longer dual-routes."""
    item = _item(
        "cnbc-top-news",
        "Federal Reserve hints at rate cut",
        summary="Officials see room for easing later this year.",
    )

    segmented = segment_items([item])

    assert segmented.us_equity == (item,)
    assert segmented.crypto == ()


def test_r6_theblock_crypto_with_fed_and_btc_stays_crypto_only() -> None:
    """Source-anchored crypto wins over the Fed cross-market combo."""
    item = _item(
        "theblock-crypto",
        "Federal Reserve liquidity ripples through BTC",
        summary="Treasury market moves and BTC reaction.",
    )

    segmented = segment_items([item])

    assert segmented.crypto == (item,)
    assert segmented.us_equity == ()


def test_r7_unknown_source_with_no_keywords_routes_nowhere() -> None:
    """Orphan low-signal item is dropped (no segment, no leak)."""
    item = _item("weather", "Local weather update", summary="Rain expected.")

    segmented = segment_items([item])

    assert segmented.domestic_equity == ()
    assert segmented.us_equity == ()
    assert segmented.crypto == ()


# ---------------------------------------------------------------------------
# Additional source-anchored exclusivity checks
# ---------------------------------------------------------------------------


def test_us_only_source_without_crypto_signal_routes_only_to_us_equity() -> None:
    item = _item("fred-macro", "DGS10 4.31%", category="macro")

    segmented = segment_items([item])

    assert segmented.us_equity == (item,)
    assert segmented.crypto == ()
    assert segmented.domestic_equity == ()


def test_crypto_only_source_with_general_news_stays_crypto_only() -> None:
    """Regression guard — generic crypto news from a single-segment source."""
    item = _item(
        "theblock-crypto",
        "Spot Bitcoin ETF approved by regulator",
    )

    segmented = segment_items([item])

    assert segmented.crypto == (item,)
    assert segmented.us_equity == ()


def test_official_crypto_policy_source_routes_to_crypto_without_ticker() -> None:
    """u58 — official policy source should not need BTC/ETH tokens."""
    item = _item(
        "senate-banking-policy",
        "Executive session to consider H.R. 3633, the Digital Asset Market Clarity Act",
        category="calendar",
        summary="Committee markup on digital asset market structure.",
    )

    segmented = segment_items([item])

    assert segmented.crypto == (item,)
    assert segmented.us_equity == ()


def test_policy_priority_metadata_routes_unknown_official_item_to_crypto() -> None:
    """u58 — policy metadata is a routing override for future official sources."""
    item = NormalizedItem(
        source_name="future-official-policy",
        category="news",
        title="Committee markup on digital asset market structure",
        summary="No BTC or ETH price tokens in this policy item.",
        published_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
        raw_metadata={"policy_priority": "crypto_regulation", "official_source": "true"},
    )

    segmented = segment_items([item])

    assert segmented.crypto == (item,)
    assert segmented.us_equity == ()


def test_domestic_only_source_with_korean_news_stays_domestic() -> None:
    item = _item("yonhap-market", "코스피 7,000 돌파")

    segmented = segment_items([item])

    assert segmented.domestic_equity == (item,)
    assert segmented.us_equity == ()
    assert segmented.crypto == ()


def test_dart_disclosure_routes_to_domestic_only() -> None:
    """u41 — DART 공시는 국내 전용; us-equity / crypto 누설 금지."""
    item = _item(
        "dart-disclosure",
        "[DART] 삼성전자 - 주요사항보고서(자기주식취득결정)",
        summary="자기주식취득결정 (접수번호 20260508900123)",
    )

    segmented = segment_items([item])

    assert segmented.domestic_equity == (item,)
    assert segmented.us_equity == ()
    assert segmented.crypto == ()


def test_dart_disclosure_with_btc_in_corp_name_stays_domestic() -> None:
    """Source-anchored routing — even if the corp name contained ``BTC``
    the dart-disclosure source slot keeps the item in domestic-equity.
    Strong-crypto-signal override applies only to *us-only* sources.
    """
    item = _item(
        "dart-disclosure",
        "[DART] BTC홀딩스 - 주식등의대량보유상황보고서",
        summary="주식등의대량보유상황보고서 (접수번호 20260508900456)",
    )

    segmented = segment_items([item])

    assert segmented.domestic_equity == (item,)
    assert segmented.crypto == ()
    assert segmented.us_equity == ()


def test_us_only_source_with_btc_ticker_in_summary_moves_to_crypto() -> None:
    """Strong crypto signal triggered by ``BTC`` ticker in summary."""
    item = _item(
        "yahoo-finance-news",
        "Markets recap",
        summary="Equities mixed; BTC retraces 2% intraday.",
    )

    segmented = segment_items([item])

    assert segmented.crypto == (item,)
    assert segmented.us_equity == ()


def test_us_only_source_with_lowercase_btc_inside_word_stays_us_equity() -> None:
    """Word-boundary regex prevents false positive on substrings."""
    item = _item(
        "yahoo-finance-news",
        "Debtor lawsuit names ABCBTC Holdings",
        summary="Court filing alleges fraud at the holdings company.",
    )

    segmented = segment_items([item])

    assert segmented.us_equity == (item,)
    assert segmented.crypto == ()


def test_keyword_fallback_us_ticker_routes_to_us_equity() -> None:
    item = _item("blogspot", "NVDA quarterly beat sends shares higher")

    segmented = segment_items([item])

    assert segmented.us_equity == (item,)
    assert segmented.crypto == ()


def test_keyword_fallback_korean_ticker_routes_to_domestic() -> None:
    item = _item("blogspot", "삼성전자[005930] 외국인 순매수")

    segmented = segment_items([item])

    assert segmented.domestic_equity == (item,)
    assert segmented.us_equity == ()


# ---------------------------------------------------------------------------
# u46 — stooq-price routing (us-only source, BTC/ETH titles override)
# ---------------------------------------------------------------------------


def test_stooq_price_us_index_routes_to_us_equity_only() -> None:
    """``^GSPC`` from stooq-price stays us-equity; no crypto leak."""
    item = _item(
        "stooq-price",
        "^GSPC 7,398.90",
        category="price",
        summary="O:7363.00 H:7401.50 L:7363.00 C:7398.90 V:3349607690",
    )

    segmented = segment_items([item])

    assert segmented.us_equity == (item,)
    assert segmented.crypto == ()
    assert segmented.domestic_equity == ()


def test_stooq_price_btc_title_moves_to_crypto() -> None:
    """``BTC-USD`` title from stooq-price triggers strong-crypto override."""
    item = _item(
        "stooq-price",
        "BTC-USD 80,142.30",
        category="price",
        summary="O:79735.20 H:80482.80 L:79230.50 C:80142.30 V:14237",
    )

    segmented = segment_items([item])

    assert segmented.crypto == (item,)
    assert segmented.us_equity == ()


def test_stooq_price_eth_title_moves_to_crypto() -> None:
    item = _item(
        "stooq-price",
        "ETH-USD 2,331.00",
        category="price",
        summary="O:2314.40 H:2338.14 L:2300.00 C:2331.00 V:282698",
    )

    segmented = segment_items([item])

    assert segmented.crypto == (item,)
    assert segmented.us_equity == ()


def test_stooq_price_aapl_stays_us_equity() -> None:
    item = _item(
        "stooq-price",
        "AAPL 293.32",
        category="price",
        summary="O:290.01 H:294.76 L:290.00 C:293.32 V:52692761",
    )

    segmented = segment_items([item])

    assert segmented.us_equity == (item,)
    assert segmented.crypto == ()


# ---------------------------------------------------------------------------
# Invariant — a non-shared item lands in at most one segment
# ---------------------------------------------------------------------------


def test_non_shared_items_route_to_at_most_one_segment() -> None:
    items = [
        _item("theblock-crypto", "Hyperliquid SEC investigation"),
        _item("yahoo-finance-news", "Bitcoin and ethereum prices today"),
        _item("yahoo-finance-news", "S&P 500 reaches new high"),
        _item("cnbc-top-news", "Federal Reserve hints at rate cut"),
        _item("yonhap-market", "코스피 7,000 돌파"),
        _item("fomc-rss", "Federal Reserve liquidity update"),
        _item("fred-macro", "DGS10 4.31%", category="macro"),
        _item("coingecko-price", "BTC price snapshot", category="price"),
        _item("blogspot", "NVDA quarterly beat"),
        _item("weather", "Local weather update"),
    ]

    segmented = segment_items(items)

    by_segment: dict[MarketSegment, set[int]] = {
        DOMESTIC_EQUITY: {id(i) for i in segmented.domestic_equity},
        US_EQUITY: {id(i) for i in segmented.us_equity},
        CRYPTO: {id(i) for i in segmented.crypto},
    }
    for item in items:
        if item.source_name in _SHARED_SOURCES:
            continue
        membership = sum(1 for ids in by_segment.values() if id(item) in ids)
        assert membership <= 1, (
            f"non-shared item {item.source_name!r} / {item.title!r} "
            f"appeared in {membership} segments"
        )


def test_shared_source_fans_out_to_all_registered_segments() -> None:
    """Invariant complement — explicitly registered shared sources fan out."""
    items = [_item("treasury-rates", "UST 2Y/10Y curve update", category="macro")]

    segmented = segment_items(items)

    assert segmented.us_equity == tuple(items)
    assert segmented.crypto == tuple(items)
    assert segmented.domestic_equity == ()


# ---------------------------------------------------------------------------
# u53 — krx-foreign-flows (domestic-only) + new us-equity sector / macro tickers
# ---------------------------------------------------------------------------


def test_krx_foreign_flows_routes_to_domestic_only() -> None:
    """``krx-foreign-flows`` is a domestic-only allow-list entry (u53).

    No leak into us-equity or crypto regardless of body content (the
    Korean labels '외국인' / '기관' do not match any us-equity or crypto
    keyword anyway, but the source-anchor rule pre-empts the keyword
    fallback).
    """
    item = _item(
        "krx-foreign-flows",
        "KOSPI 외국인 순매도 -28,147억원 (2026-05-11)",
        category="price",
        summary="KOSPI 2026-05-11 외국인 순매수 -28,147억원",
    )

    segmented = segment_items([item])

    assert segmented.domestic_equity == (item,)
    assert segmented.us_equity == ()
    assert segmented.crypto == ()


def test_stooq_price_sector_etf_routes_to_us_equity_only() -> None:
    """u53 — ``XLK`` (Stooq sector SPDR) is us-equity-only; no crypto leak."""
    item = _item(
        "stooq-price",
        "XLK 173.96",
        category="price",
        summary="O:176.15 H:176.99 L:171.20 C:173.96 V:6687269",
    )

    segmented = segment_items([item])

    assert segmented.us_equity == (item,)
    assert segmented.crypto == ()
    assert segmented.domestic_equity == ()


def test_stooq_price_gold_etf_routes_to_us_equity_only() -> None:
    """u53 commodity-proxy policy — ``GLD`` rides us-equity only (MVP)."""
    item = _item(
        "stooq-price",
        "GLD 431.60",
        category="price",
        summary="O:430.73 H:431.74 L:425.85 C:431.60 V:3165479",
    )

    segmented = segment_items([item])

    assert segmented.us_equity == (item,)
    assert segmented.crypto == ()
    assert segmented.domestic_equity == ()


def test_stooq_price_oil_futures_routes_to_us_equity_only() -> None:
    """u53 — ``CL=F`` (WTI futures) lands in us-equity only (commodity proxy MVP)."""
    item = _item(
        "stooq-price",
        "CL=F 102.31",
        category="price",
        summary="O:98.28 H:102.72 L:98.02 C:102.31 V:0",
    )

    segmented = segment_items([item])

    assert segmented.us_equity == (item,)
    assert segmented.crypto == ()
    assert segmented.domestic_equity == ()


def test_yfinance_russell_2000_routes_to_us_equity_only() -> None:
    """u53 — ``^RUT`` (Russell 2000 index from yfinance) is us-equity-only."""
    item = _item(
        "yfinance-price",
        "^RUT 2,412.85 (+0.66%)",
        category="price",
        summary="O:2398.65 H:2418.90 L:2389.40 C:2412.85 V:0",
    )

    segmented = segment_items([item])

    assert segmented.us_equity == (item,)
    assert segmented.crypto == ()
    assert segmented.domestic_equity == ()
