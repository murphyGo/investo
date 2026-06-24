"""Canonical production source metadata descriptors.

This module is intentionally a shared leaf: it imports only stable model
contracts and never imports ``investo.sources`` or ``investo.briefing``.
The adapter registry remains explicit in ``investo.sources``; these
descriptors define the metadata other units need about registered
production adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from investo.models import MarketSegment, SourceTier

SourceItemRouting = Literal[
    "single-segment",
    "shared-segments",
    "us-with-crypto-signal",
    "cftc-contract-group",
]


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """Production source descriptor used to derive compatibility views."""

    name: str
    tier: SourceTier
    market_window_segment: MarketSegment
    item_routing: SourceItemRouting
    item_segments: frozenset[MarketSegment]
    outcome_segments: frozenset[MarketSegment]


def _spec(
    name: str,
    *,
    tier: SourceTier,
    market_window_segment: MarketSegment,
    item_routing: SourceItemRouting = "single-segment",
    item_segments: frozenset[MarketSegment],
    outcome_segments: frozenset[MarketSegment] | None = None,
) -> SourceSpec:
    return SourceSpec(
        name=name,
        tier=tier,
        market_window_segment=market_window_segment,
        item_routing=item_routing,
        item_segments=item_segments,
        outcome_segments=outcome_segments if outcome_segments is not None else item_segments,
    )


_DOMESTIC: Final[frozenset[MarketSegment]] = frozenset({"domestic-equity"})
_US: Final[frozenset[MarketSegment]] = frozenset({"us-equity"})
_CRYPTO: Final[frozenset[MarketSegment]] = frozenset({"crypto"})
_US_AND_CRYPTO: Final[frozenset[MarketSegment]] = frozenset({"us-equity", "crypto"})

SOURCE_SPECS: Final[tuple[SourceSpec, ...]] = (
    _spec("bea-macro-actuals", tier="S", market_window_segment="us-equity", item_segments=_US),
    _spec("bls-macro-actuals", tier="S", market_window_segment="us-equity", item_segments=_US),
    _spec("sec-edgar-8k", tier="S", market_window_segment="us-equity", item_segments=_US),
    _spec("fed-board-leadership", tier="S", market_window_segment="us-equity", item_segments=_US),
    _spec("fed-speech-rss", tier="S", market_window_segment="us-equity", item_segments=_US),
    _spec("fomc-calendar", tier="S", market_window_segment="us-equity", item_segments=_US),
    _spec("fomc-rss", tier="S", market_window_segment="us-equity", item_segments=_US),
    _spec(
        "fsc-krx-index-price",
        tier="S",
        market_window_segment="domestic-equity",
        item_segments=_DOMESTIC,
    ),
    _spec(
        "fsc-krx-stock-price",
        tier="S",
        market_window_segment="domestic-equity",
        item_segments=_DOMESTIC,
    ),
    _spec(
        "korea-policy-rss",
        tier="S",
        market_window_segment="domestic-equity",
        item_segments=_DOMESTIC,
    ),
    _spec(
        "dart-disclosure",
        tier="S",
        market_window_segment="domestic-equity",
        item_segments=_DOMESTIC,
    ),
    _spec(
        "congress-gov-bill-actions",
        tier="S",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
    ),
    _spec(
        "house-financial-services-policy",
        tier="S",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
    ),
    _spec(
        "senate-banking-policy",
        tier="S",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
    ),
    _spec("sec-company-facts", tier="S", market_window_segment="us-equity", item_segments=_US),
    _spec("sec-newsroom-rss", tier="S", market_window_segment="us-equity", item_segments=_US),
    _spec(
        "treasury-rates",
        tier="S",
        market_window_segment="us-equity",
        item_routing="shared-segments",
        item_segments=_US_AND_CRYPTO,
    ),
    _spec("eia-petroleum-weekly", tier="S", market_window_segment="us-equity", item_segments=_US),
    _spec("nyfed-reference-rates", tier="S", market_window_segment="us-equity", item_segments=_US),
    _spec(
        "cftc-cot-positioning",
        tier="S",
        market_window_segment="us-equity",
        item_routing="cftc-contract-group",
        item_segments=frozenset(),
        outcome_segments=_US_AND_CRYPTO,
    ),
    _spec(
        "krx-foreign-flows",
        tier="A",
        market_window_segment="domestic-equity",
        item_segments=_DOMESTIC,
    ),
    _spec("yfinance-price", tier="A", market_window_segment="us-equity", item_segments=_US),
    _spec(
        "stooq-price",
        tier="A",
        market_window_segment="us-equity",
        item_routing="us-with-crypto-signal",
        item_segments=_US,
        outcome_segments=_US_AND_CRYPTO,
    ),
    _spec("yahoo-finance-news", tier="A", market_window_segment="us-equity", item_segments=_US),
    _spec(
        "binance-crypto-market",
        tier="A",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
    ),
    _spec(
        "nasdaq-earnings-calendar",
        tier="A",
        market_window_segment="us-equity",
        item_segments=_US,
    ),
    _spec(
        "nasdaq-symbol-directory",
        tier="A",
        market_window_segment="us-equity",
        item_segments=_US,
    ),
    _spec("fred-macro", tier="A", market_window_segment="us-equity", item_segments=_US),
    _spec(
        "fred-economic-calendar",
        tier="A",
        market_window_segment="us-equity",
        item_segments=_US,
    ),
    _spec("us-economic-calendar", tier="A", market_window_segment="us-equity", item_segments=_US),
    _spec("nasdaq-stocks-news", tier="A", market_window_segment="us-equity", item_segments=_US),
    _spec(
        "stooq-kr-market",
        tier="A",
        market_window_segment="domestic-equity",
        item_segments=_DOMESTIC,
    ),
    _spec("bybit-derivatives", tier="A", market_window_segment="crypto", item_segments=_CRYPTO),
    _spec("okx-derivatives", tier="A", market_window_segment="crypto", item_segments=_CRYPTO),
    _spec(
        "cboe-volatility-indices",
        tier="A",
        market_window_segment="us-equity",
        item_segments=_US,
    ),
    _spec("cnbc-top-news", tier="B", market_window_segment="us-equity", item_segments=_US),
    _spec(
        "yonhap-market",
        tier="B",
        market_window_segment="domestic-equity",
        item_segments=_DOMESTIC,
    ),
    _spec("theblock-crypto", tier="B", market_window_segment="crypto", item_segments=_CRYPTO),
    _spec("coingecko-price", tier="B", market_window_segment="crypto", item_segments=_CRYPTO),
    _spec(
        "coingecko-global-market",
        tier="B",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
    ),
    _spec("alternative-fng", tier="B", market_window_segment="crypto", item_segments=_CRYPTO),
    _spec(
        "defillama-market-structure",
        tier="B",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
    ),
)

SOURCE_SPECS_BY_NAME: Final[dict[str, SourceSpec]] = {spec.name: spec for spec in SOURCE_SPECS}


def source_names_for_market_window(segment: MarketSegment) -> frozenset[str]:
    return frozenset(
        spec.name for spec in SOURCE_SPECS if spec.market_window_segment == segment
    )


def source_names_for_item_segment(
    segment: MarketSegment,
    *,
    routing: SourceItemRouting | None = None,
) -> frozenset[str]:
    return frozenset(
        spec.name
        for spec in SOURCE_SPECS
        if segment in spec.item_segments and (routing is None or spec.item_routing == routing)
    )


def source_names_for_outcome_segment(segment: MarketSegment) -> frozenset[str]:
    return frozenset(spec.name for spec in SOURCE_SPECS if segment in spec.outcome_segments)


def source_names_for_item_routing(routing: SourceItemRouting) -> frozenset[str]:
    return frozenset(spec.name for spec in SOURCE_SPECS if spec.item_routing == routing)


__all__ = [
    "SOURCE_SPECS",
    "SOURCE_SPECS_BY_NAME",
    "SourceItemRouting",
    "SourceSpec",
    "source_names_for_item_routing",
    "source_names_for_item_segment",
    "source_names_for_market_window",
    "source_names_for_outcome_segment",
]
