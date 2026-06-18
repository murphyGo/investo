"""u32 Step 1 — Source tier registry.

Each registered source adapter is assigned a tier label that surfaces
on the reader-facing coverage badge (u22) and on the
:class:`SourceOutcome` records carried through ``PipelineResult``. A
tier is a stable, editorial classification of the *kind* of source:

* ``"S"`` — primary regulatory / exchange feeds (the source of record
  for what they report). Examples: SEC EDGAR, FOMC RSS, the Korean
  FSC OpenAPI surfaces, US Treasury Direct, KRX.
* ``"A"`` — first-party / official feeds (the issuer's own publishing
  endpoint, just not the regulator's record). Examples: Yahoo Finance
  price endpoints, Binance market endpoints, Nasdaq earnings calendar,
  FRED, Federal Reserve calendar pages.
* ``"B"`` — reputable aggregator / news sources. Examples: CNBC top
  news, Yonhap market wire, Yahoo Finance news, The Block, CoinGecko
  events, DefiLlama market structure.
* ``"C"`` — miscellaneous / blog / unverified. Reserved for future use;
  no current adapter falls in this tier.

The tier is **not** a quality score — it is an editorial classification
that lets the reader weigh "we have 3 S-tier sources and 5 B-tier
sources" against "we have 0 S-tier sources and 8 B-tier sources" when
reading the briefing. The classification is stable across releases —
moving an adapter from ``"B"`` to ``"S"`` is a deliberate editorial
change, not a runtime configuration.

If the reader sees ``"unknown"`` in any badge, that means the registry
fell behind the adapter list — :func:`adapter_tier` defaults to
``"B"`` (the most common case) and logs a warning so the gap is
visible in operator triage.
"""

from __future__ import annotations

import logging
from typing import Final

from investo.models import SourceTier

_logger = logging.getLogger(__name__)

ADAPTER_TIERS: Final[dict[str, SourceTier]] = {
    # S — regulatory / exchange / sovereign data
    "sec-edgar-8k": "S",
    "fed-board-leadership": "S",
    "fomc-calendar": "S",
    "fomc-rss": "S",
    "fsc-krx-index-price": "S",
    "fsc-krx-stock-price": "S",
    "korea-policy-rss": "S",
    "dart-disclosure": "S",
    "congress-gov-bill-actions": "S",
    "house-financial-services-policy": "S",
    "senate-banking-policy": "S",
    "treasury-rates": "S",
    # u53 — Naver finance mirrors a KRX investor-flow aggregation. KRX
    # is the system of record but the proximate endpoint is an
    # aggregator surface, so this lands in A rather than S.
    "krx-foreign-flows": "A",
    # A — first-party / official feeds
    "yfinance-price": "A",
    "stooq-price": "A",
    "yahoo-finance-news": "A",
    "binance-crypto-market": "A",
    "nasdaq-earnings-calendar": "A",
    "fred-macro": "A",
    "fred-economic-calendar": "A",
    "us-economic-calendar": "A",
    "nasdaq-stocks-news": "A",
    # B — aggregator / news
    "cnbc-top-news": "B",
    "yonhap-market": "B",
    "theblock-crypto": "B",
    "coingecko-price": "B",
    "coingecko-events": "B",
    "defillama-market-structure": "B",
}

DEFAULT_TIER: Final[SourceTier] = "B"


def adapter_tier(source_name: str) -> SourceTier:
    """Return the editorial tier for a registered adapter name.

    Adapters not listed in :data:`ADAPTER_TIERS` get the default
    ``"B"`` tier and emit a one-line INFO log so the gap is visible
    in dev/debug output without escalating to a per-run warning that
    would clutter operator triage. New adapters should be added to
    :data:`ADAPTER_TIERS` as part of the same patch.
    """
    tier = ADAPTER_TIERS.get(source_name)
    if tier is None:
        _logger.info(
            "[tiers] %s missing from ADAPTER_TIERS — falling back to %s",
            source_name,
            DEFAULT_TIER,
        )
        return DEFAULT_TIER
    return tier


def tier_mix_label(tiers: list[SourceTier]) -> str:
    """Render a deterministic ``S=2 / A=1 / B=4`` style tier-mix string.

    Empty input → ``""`` (caller skips rendering). Tiers absent from
    the input are omitted; tier order is canonical (S → A → B → C) so
    the badge is stable regardless of input ordering.
    """
    if not tiers:
        return ""
    counts = {label: 0 for label in ("S", "A", "B", "C")}
    for tier in tiers:
        counts[tier] += 1
    parts = [f"{label}={count}" for label, count in counts.items() if count]
    return " / ".join(parts)


__all__ = [
    "ADAPTER_TIERS",
    "DEFAULT_TIER",
    "adapter_tier",
    "tier_mix_label",
]
