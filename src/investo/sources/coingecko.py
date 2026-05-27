"""CoinGecko Public API adapter — crypto price snapshots.

Implements the algorithm from FD L6.3 (extension 2026-05-01). Fetches
the current market snapshot for each configured coin id and emits one
:class:`NormalizedItem` per coin with `category="price"`.

Design choices (audit log 2026-05-01):

* **One HTTP call per fetch** — the ``/coins/markets`` endpoint accepts
  a comma-joined ``ids`` parameter, so all coins are returned in a
  single response. (Contrast with :mod:`yfinance` which is one HTTP
  per ticker.) This minimises the rate-limit surface against
  CoinGecko's free tier (~30 req/min).
* **Strict R7 window** — crypto trades 24/7, so ``last_updated`` is
  always within minutes of ``fetch_all`` invocation and falls
  naturally inside the KST trading-day window. No relaxation needed.
* **Per-coin isolation** — a single bad entry (naive ``last_updated``,
  pydantic validation failure) is dropped without affecting siblings
  in the same response.

Pins (extension 2026-05-01):

* AC-5.5 / R12 — `INVESTO_COINGECKO_COINS` env-var override
* R8 — `raw_metadata` is string-keyed and string-valued
"""

from __future__ import annotations

from typing import Any, ClassVar

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import (
    SUMMARY_MAX_LEN,
    format_float,
    parse_iso8601_to_utc,
    parse_symbol_list,
)
from investo.sources._parse import parse_json_response
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_ENV_COINS = "INVESTO_COINGECKO_COINS"


@register
class CoinGeckoPriceAdapter:
    """Adapter for the CoinGecko Public API ``/coins/markets`` endpoint."""

    name: ClassVar[str] = "coingecko-price"
    category: ClassVar[Category] = "price"

    _DEFAULT_COINS: ClassVar[tuple[str, ...]] = ("bitcoin", "ethereum", "solana")

    _ENDPOINT: ClassVar[str] = "https://api.coingecko.com/api/v3/coins/markets"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        coins = parse_symbol_list(_ENV_COINS, self._DEFAULT_COINS)
        response = await retry_get(
            client,
            self._ENDPOINT,
            source_name=self.name,
            params={
                "vs_currency": "usd",
                "ids": ",".join(coins),
                "price_change_percentage": "24h",
            },
        )
        payload = parse_json_response(response, source_name=self.name)

        if not isinstance(payload, list):
            raise SourceFetchError(
                source_name=self.name,
                message=f"expected list response, got {type(payload).__name__}",
                transient=False,
            )
        if not payload:
            # All requested coin ids invalid → terminal config error.
            raise SourceFetchError(
                source_name=self.name,
                message=f"empty markets response (no coin ids matched: {coins})",
                transient=False,
            )

        items: list[NormalizedItem] = []
        for entry in payload:
            normalized = self._normalize_entry(entry)
            if normalized is None:
                continue
            if window.contains(normalized.published_at):
                items.append(normalized)
        return items

    def _normalize_entry(self, entry: Any) -> NormalizedItem | None:
        if not isinstance(entry, dict):
            return None

        coin_id = entry.get("id")
        symbol = entry.get("symbol")
        price = entry.get("current_price")
        if (
            not isinstance(coin_id, str)
            or not isinstance(symbol, str)
            or not isinstance(price, (int, float))
        ):
            return None

        last_updated_raw = entry.get("last_updated")
        if not isinstance(last_updated_raw, str):
            return None
        try:
            last_updated = parse_iso8601_to_utc(last_updated_raw)
        except ValueError:
            return None

        # CoinGecko returns null for new listings without a 24h history.
        # Default to 0.0 so the item is still emitted with a flat title.
        pct_raw = entry.get("price_change_percentage_24h")
        pct = float(pct_raw) if isinstance(pct_raw, (int, float)) else 0.0

        volume_24h = entry.get("total_volume") or 0
        market_cap = entry.get("market_cap") or 0
        high_24h = entry.get("high_24h") or 0.0
        low_24h = entry.get("low_24h") or 0.0

        title = f"{symbol.upper()} ${float(price):,.2f} ({pct:+.2f}%)"
        summary = (
            f"24h vol: ${float(volume_24h):,.0f}; "
            f"market cap: ${float(market_cap):,.0f}; "
            f"high: ${float(high_24h):,.2f}; "
            f"low: ${float(low_24h):,.2f}"
        )
        if len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        raw_metadata: dict[str, str] = {
            "coin_id": coin_id,
            "symbol": symbol,
            "price_usd": format_float(float(price)),
            "pct_24h": format_float(pct),
            "volume_24h": format_float(float(volume_24h)),
            "market_cap": format_float(float(market_cap)),
            "high_24h": format_float(float(high_24h)),
            "low_24h": format_float(float(low_24h)),
        }

        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=f"https://www.coingecko.com/en/coins/{coin_id}",
                published_at=last_updated,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None
