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

import json
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import parse_symbol_list
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_SUMMARY_MAX_LEN = 280
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
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"malformed JSON: {exc}",
                transient=False,
                cause=exc,
            ) from exc

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
            last_updated = self._parse_iso8601(last_updated_raw)
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
        if len(summary) > _SUMMARY_MAX_LEN:
            summary = summary[:_SUMMARY_MAX_LEN]

        raw_metadata: dict[str, str] = {
            "coin_id": coin_id,
            "symbol": symbol,
            "price_usd": f"{float(price):.6f}",
            "pct_24h": f"{pct:.6f}",
            "volume_24h": f"{float(volume_24h):.2f}",
            "market_cap": f"{float(market_cap):.2f}",
            "high_24h": f"{float(high_24h):.6f}",
            "low_24h": f"{float(low_24h):.6f}",
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

    @staticmethod
    def _parse_iso8601(text: str) -> datetime:
        """Parse a CoinGecko ``last_updated`` string to a tz-aware UTC datetime.

        CoinGecko emits ISO 8601 with millisecond precision and a
        trailing ``Z`` (e.g. ``"2026-04-30T17:25:01.044Z"``). Python
        3.11+ ``fromisoformat`` accepts the ``Z`` suffix. Naive results
        (no timezone) raise — adapters per R8 must reject naive inputs
        rather than silently assume UTC.
        """

        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            raise ValueError(f"naive last_updated: {text!r}")
        return parsed.astimezone(UTC)
