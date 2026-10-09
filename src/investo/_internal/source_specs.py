"""Canonical production source metadata descriptors.

This module is intentionally a shared leaf: it imports only stable model
contracts and never imports ``investo.sources`` or ``investo.briefing``.
The adapter registry remains explicit in ``investo.sources``; these
descriptors define the metadata other units need about registered
production adapters.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal

from investo.models import MarketSegment, SourceTier
from investo.models.coverage import SOURCE_SKIP_REASON_LABELS, SourceSkipReason

SourceItemRouting = Literal[
    "single-segment",
    "shared-segments",
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
    reference_registry: bool = False
    news_window_opt_in: bool = False
    news_window_recipients: frozenset[MarketSegment] = frozenset()
    default_enabled: bool = True
    disabled_reason: SourceSkipReason | None = None
    evidence_domains: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if type(self.default_enabled) is not bool:
            raise ValueError("source default_enabled must be boolean")
        if self.default_enabled and self.disabled_reason is not None:
            raise ValueError("enabled source forbids disabled_reason")
        if not self.default_enabled and self.disabled_reason not in SOURCE_SKIP_REASON_LABELS:
            raise ValueError("disabled source requires a known reason")


def _spec(
    name: str,
    *,
    tier: SourceTier,
    market_window_segment: MarketSegment,
    item_routing: SourceItemRouting = "single-segment",
    item_segments: frozenset[MarketSegment],
    outcome_segments: frozenset[MarketSegment] | None = None,
    reference_registry: bool = False,
    news_window_opt_in: bool = False,
    news_window_recipients: frozenset[MarketSegment] | None = None,
    default_enabled: bool = True,
    disabled_reason: SourceSkipReason | None = None,
    evidence_domains: frozenset[str] = frozenset(),
) -> SourceSpec:
    return SourceSpec(
        name=name,
        tier=tier,
        market_window_segment=market_window_segment,
        item_routing=item_routing,
        item_segments=item_segments,
        outcome_segments=outcome_segments if outcome_segments is not None else item_segments,
        reference_registry=reference_registry,
        default_enabled=default_enabled,
        disabled_reason=disabled_reason,
        evidence_domains=evidence_domains,
        news_window_opt_in=news_window_opt_in,
        news_window_recipients=(
            news_window_recipients
            if news_window_recipients is not None
            else item_segments
            if news_window_opt_in
            else frozenset()
        ),
    )


_DOMESTIC: Final[frozenset[MarketSegment]] = frozenset({"domestic-equity"})
_US: Final[frozenset[MarketSegment]] = frozenset({"us-equity"})
_CRYPTO: Final[frozenset[MarketSegment]] = frozenset({"crypto"})
_US_AND_CRYPTO: Final[frozenset[MarketSegment]] = frozenset({"us-equity", "crypto"})
_ALL_SEGMENTS: Final[frozenset[MarketSegment]] = frozenset(
    {"domestic-equity", "us-equity", "crypto"}
)

SOURCE_SPECS: Final[tuple[SourceSpec, ...]] = (
    _spec(
        "bea-macro-actuals",
        evidence_domains=frozenset({"bea.gov"}),
        tier="S",
        market_window_segment="us-equity",
        item_segments=_US,
    ),
    _spec(
        "bls-macro-actuals",
        evidence_domains=frozenset({"bls.gov"}),
        tier="S",
        market_window_segment="us-equity",
        item_segments=_US,
    ),
    _spec(
        "sec-edgar-8k",
        evidence_domains=frozenset({"sec.gov"}),
        tier="S",
        market_window_segment="us-equity",
        item_segments=_US,
        news_window_opt_in=True,
    ),
    _spec(
        "fed-board-leadership",
        evidence_domains=frozenset({"federalreserve.gov"}),
        tier="S",
        market_window_segment="us-equity",
        item_segments=_US,
    ),
    _spec(
        "fed-speech-rss",
        evidence_domains=frozenset({"federalreserve.gov"}),
        tier="S",
        market_window_segment="us-equity",
        item_segments=_US,
        news_window_opt_in=True,
        news_window_recipients=_ALL_SEGMENTS,
    ),
    _spec(
        "fomc-calendar",
        evidence_domains=frozenset({"federalreserve.gov"}),
        tier="S",
        market_window_segment="us-equity",
        item_segments=_US,
    ),
    _spec(
        "fomc-rss",
        evidence_domains=frozenset({"federalreserve.gov"}),
        tier="S",
        market_window_segment="us-equity",
        item_segments=_US,
        news_window_opt_in=True,
        news_window_recipients=_ALL_SEGMENTS,
    ),
    _spec(
        "fsc-krx-index-price",
        evidence_domains=frozenset({"data.go.kr"}),
        tier="S",
        market_window_segment="domestic-equity",
        item_segments=_DOMESTIC,
    ),
    _spec(
        "fsc-krx-stock-price",
        evidence_domains=frozenset({"data.go.kr"}),
        tier="S",
        market_window_segment="domestic-equity",
        item_segments=_DOMESTIC,
    ),
    _spec(
        "korea-policy-rss",
        evidence_domains=frozenset({"fsc.go.kr"}),
        default_enabled=False,
        disabled_reason="upstream_unavailable",
        tier="S",
        market_window_segment="domestic-equity",
        item_segments=_DOMESTIC,
        news_window_opt_in=True,
    ),
    _spec(
        "dart-disclosure",
        tier="S",
        market_window_segment="domestic-equity",
        item_segments=_DOMESTIC,
        news_window_opt_in=True,
    ),
    _spec(
        "congress-gov-bill-actions",
        evidence_domains=frozenset({"congress.gov"}),
        tier="S",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
        news_window_opt_in=True,
    ),
    _spec(
        "house-financial-services-policy",
        evidence_domains=frozenset({"financialservices.house.gov"}),
        tier="S",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
        news_window_opt_in=True,
    ),
    _spec(
        "senate-banking-policy",
        evidence_domains=frozenset({"banking.senate.gov"}),
        tier="S",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
        news_window_opt_in=True,
    ),
    _spec(
        "sec-company-facts",
        evidence_domains=frozenset({"sec.gov"}),
        tier="S",
        market_window_segment="us-equity",
        item_segments=_US,
        reference_registry=True,
    ),
    _spec(
        "sec-newsroom-rss",
        evidence_domains=frozenset({"sec.gov"}),
        tier="S",
        market_window_segment="us-equity",
        item_segments=_US,
        news_window_opt_in=True,
    ),
    _spec(
        "treasury-rates",
        evidence_domains=frozenset({"treasury.gov"}),
        tier="S",
        market_window_segment="us-equity",
        item_routing="shared-segments",
        item_segments=_US_AND_CRYPTO,
    ),
    _spec(
        "eia-petroleum-weekly",
        evidence_domains=frozenset({"eia.gov"}),
        tier="S",
        market_window_segment="us-equity",
        item_segments=_US,
    ),
    _spec("nyfed-reference-rates", tier="S", market_window_segment="us-equity", item_segments=_US),
    _spec(
        "cftc-cot-positioning",
        evidence_domains=frozenset({"cftc.gov"}),
        tier="S",
        market_window_segment="us-equity",
        item_routing="cftc-contract-group",
        item_segments=frozenset(),
        outcome_segments=_US_AND_CRYPTO,
    ),
    _spec(
        "cftc-policy-rss",
        evidence_domains=frozenset({"cftc.gov"}),
        tier="S",
        market_window_segment="us-equity",
        item_segments=_US,
        news_window_opt_in=True,
    ),
    _spec(
        "treasury-auctions",
        evidence_domains=frozenset({"treasury.gov"}),
        tier="A",
        market_window_segment="us-equity",
        item_segments=_US,
    ),
    _spec(
        "fred-fx-close",
        evidence_domains=frozenset({"stlouisfed.org"}),
        tier="S",
        market_window_segment="domestic-equity",
        item_segments=_DOMESTIC,
    ),
    _spec(
        "krx-foreign-flows",
        evidence_domains=frozenset({"finance.naver.com"}),
        default_enabled=False,
        disabled_reason="endpoint_removed",
        tier="A",
        market_window_segment="domestic-equity",
        item_segments=_DOMESTIC,
    ),
    _spec(
        "yfinance-price",
        evidence_domains=frozenset({"finance.yahoo.com"}),
        tier="A",
        market_window_segment="us-equity",
        item_segments=_US,
    ),
    _spec(
        "yahoo-finance-news",
        evidence_domains=frozenset({"finance.yahoo.com"}),
        default_enabled=False,
        disabled_reason="endpoint_removed",
        tier="A",
        market_window_segment="us-equity",
        item_segments=_US,
        news_window_opt_in=True,
    ),
    _spec(
        "binance-crypto-market",
        evidence_domains=frozenset({"binance.com"}),
        default_enabled=False,
        disabled_reason="region_denied",
        tier="A",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
    ),
    _spec(
        "nasdaq-earnings-calendar",
        evidence_domains=frozenset({"nasdaq.com"}),
        tier="A",
        market_window_segment="us-equity",
        item_segments=_US,
    ),
    _spec(
        "nasdaq-symbol-directory",
        evidence_domains=frozenset({"nasdaq.com"}),
        tier="A",
        market_window_segment="us-equity",
        item_segments=_US,
        reference_registry=True,
    ),
    _spec(
        "fred-macro",
        evidence_domains=frozenset({"stlouisfed.org"}),
        tier="A",
        market_window_segment="us-equity",
        item_segments=_US,
    ),
    _spec(
        "fred-economic-calendar",
        evidence_domains=frozenset({"stlouisfed.org"}),
        tier="A",
        market_window_segment="us-equity",
        item_segments=_US,
    ),
    _spec("us-economic-calendar", tier="A", market_window_segment="us-equity", item_segments=_US),
    _spec(
        "nasdaq-stocks-news",
        evidence_domains=frozenset({"nasdaq.com"}),
        tier="A",
        market_window_segment="us-equity",
        item_segments=_US,
        news_window_opt_in=True,
    ),
    _spec(
        "bybit-derivatives",
        evidence_domains=frozenset({"bybit.com"}),
        tier="A",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
    ),
    _spec(
        "okx-derivatives",
        evidence_domains=frozenset({"okx.com"}),
        tier="A",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
    ),
    _spec(
        "cboe-volatility-indices",
        evidence_domains=frozenset({"cboe.com"}),
        tier="A",
        market_window_segment="us-equity",
        item_segments=_US,
    ),
    _spec(
        "cnbc-top-news",
        evidence_domains=frozenset({"cnbc.com"}),
        default_enabled=False,
        disabled_reason="access_denied",
        tier="B",
        market_window_segment="us-equity",
        item_segments=_US,
        news_window_opt_in=True,
    ),
    _spec(
        "yonhap-market",
        evidence_domains=frozenset({"yna.co.kr"}),
        tier="B",
        market_window_segment="domestic-equity",
        item_segments=_DOMESTIC,
        news_window_opt_in=True,
    ),
    _spec(
        "yonhap-index-close",
        evidence_domains=frozenset({"yna.co.kr"}),
        tier="B",
        market_window_segment="domestic-equity",
        item_segments=_DOMESTIC,
    ),
    _spec(
        "theblock-crypto",
        evidence_domains=frozenset({"theblock.co"}),
        tier="B",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
        news_window_opt_in=True,
    ),
    _spec(
        "coingecko-price",
        evidence_domains=frozenset({"coingecko.com"}),
        tier="B",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
    ),
    _spec(
        "coingecko-global-market",
        evidence_domains=frozenset({"coingecko.com"}),
        tier="B",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
    ),
    _spec(
        "alternative-fng",
        evidence_domains=frozenset({"alternative.me"}),
        tier="B",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
    ),
    _spec(
        "defillama-market-structure",
        evidence_domains=frozenset({"defillama.com"}),
        tier="B",
        market_window_segment="crypto",
        item_segments=_CRYPTO,
    ),
)

SOURCE_SPECS_BY_NAME: Final[dict[str, SourceSpec]] = {spec.name: spec for spec in SOURCE_SPECS}


def news_window_source_recipients() -> Mapping[str, frozenset[MarketSegment]]:
    """Explicit news lanes; shared Fed evidence still needs article qualification."""
    return MappingProxyType(
        {spec.name: spec.news_window_recipients for spec in SOURCE_SPECS if spec.news_window_opt_in}
    )


def source_names_for_market_window(segment: MarketSegment) -> frozenset[str]:
    return frozenset(spec.name for spec in SOURCE_SPECS if spec.market_window_segment == segment)


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
    "news_window_source_recipients",
    "source_names_for_item_routing",
    "source_names_for_item_segment",
    "source_names_for_market_window",
    "source_names_for_outcome_segment",
    "source_skip_reasons",
]


def source_skip_reasons(*, enable: str = "", disable: str = "") -> dict[str, SourceSkipReason]:
    """Resolve exact-name run overrides without I/O or echoing untrusted input."""

    def names(raw: str) -> frozenset[str]:
        parsed = frozenset(part.strip() for part in raw.split(",") if part.strip())
        if parsed - set(SOURCE_SPECS_BY_NAME):
            raise ValueError("source activation override contains unknown names")
        return parsed

    enabled, disabled = names(enable), names(disable)
    if enabled & disabled:
        raise ValueError("source activation enable and disable overlap")
    reasons: dict[str, SourceSkipReason] = {
        spec.name: spec.disabled_reason
        for spec in SOURCE_SPECS
        if not spec.default_enabled
        and spec.disabled_reason is not None
        and spec.name not in enabled
    }
    reasons.update({name: "operator_disabled" for name in disabled})
    return reasons
