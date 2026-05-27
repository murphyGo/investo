"""CoinGecko global market adapter (FD L6.14, u66).

Fetches the no-key CoinGecko ``/api/v3/global`` endpoint and emits a
single :class:`NormalizedItem` with ``category="macro"`` tagged
``indicator=global_market`` carrying BTC dominance and total crypto
market-cap context. Consumed by the u74 crypto indicator contract for
the BTC 도미넌스 and 전체 시총 rows.

Design choices (u66 plan 2026-05-24):

* **No key, no secret** — the global endpoint is fully public (free-tier
  rate ~5-15/min, called once/day). R13 has no surface.
* **Snapshot semantics** — global totals are a point-in-time read;
  ``data.updated_at`` (Unix seconds) becomes ``published_at`` (R9
  idempotent). The crypto segment runs on a UTC 24h frame.
* **Schema-failure isolation** — missing BTC dominance or total market
  cap raises ``SourceFetchError`` (R6) rather than emitting a half item.

u74 interface contract (load-bearing — do not rename keys):
``indicator=global_market``, ``btc_dominance_pct`` (%), ``eth_dominance_pct``,
``total_market_cap_usd``, ``total_volume_usd``,
``market_cap_change_24h_pct``, ``updated_at``.

Pins:

* R8 — flat string ``raw_metadata``; ``published_at`` tz-aware UTC.
* R6 — only ``SourceFetchError`` for source-side schema failures.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import format_float
from investo.sources._parse import parse_json_response
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError


@register
class CoinGeckoGlobalMarketAdapter:
    """Adapter for the CoinGecko ``/api/v3/global`` endpoint."""

    name: ClassVar[str] = "coingecko-global-market"
    category: ClassVar[Category] = "macro"

    _ENDPOINT: ClassVar[str] = "https://api.coingecko.com/api/v3/global"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        response = await retry_get(
            client,
            self._ENDPOINT,
            source_name=self.name,
        )
        payload = parse_json_response(response, source_name=self.name)

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise SourceFetchError(
                source_name=self.name,
                message="missing data object",
                transient=False,
            )

        pct = data.get("market_cap_percentage")
        total_market_cap = data.get("total_market_cap")
        btc_dominance = self._extract_float(pct, "btc") if isinstance(pct, dict) else None
        total_mcap_usd = (
            self._extract_float(total_market_cap, "usd")
            if isinstance(total_market_cap, dict)
            else None
        )
        if btc_dominance is None or total_mcap_usd is None:
            raise SourceFetchError(
                source_name=self.name,
                message="missing BTC dominance or total market cap",
                transient=False,
            )

        eth_dominance = self._extract_float(pct, "eth") if isinstance(pct, dict) else None
        total_volume = data.get("total_volume")
        total_volume_usd = (
            self._extract_float(total_volume, "usd") if isinstance(total_volume, dict) else None
        )
        change_24h = self._coerce_float(data.get("market_cap_change_percentage_24h_usd"))
        updated_at_raw = data.get("updated_at")

        if isinstance(updated_at_raw, int) and not isinstance(updated_at_raw, bool):
            try:
                published_at = datetime.fromtimestamp(updated_at_raw, tz=UTC)
            except (ValueError, OverflowError, OSError):
                published_at = window.end_utc.astimezone(UTC)
        else:
            published_at = window.end_utc.astimezone(UTC)

        raw_metadata: dict[str, str] = {
            "indicator": "global_market",
            "btc_dominance_pct": format_float(btc_dominance, precision=2),
            "total_market_cap_usd": format_float(total_mcap_usd, precision=0),
        }
        if eth_dominance is not None:
            raw_metadata["eth_dominance_pct"] = format_float(eth_dominance, precision=2)
        if total_volume_usd is not None:
            raw_metadata["total_volume_usd"] = format_float(total_volume_usd, precision=0)
        if change_24h is not None:
            raw_metadata["market_cap_change_24h_pct"] = format_float(change_24h, precision=4)
        if isinstance(updated_at_raw, int) and not isinstance(updated_at_raw, bool):
            raw_metadata["updated_at"] = str(updated_at_raw)

        title = (
            f"Global crypto market cap ${total_mcap_usd:,.0f}; BTC dominance {btc_dominance:.2f}%"
        )

        try:
            return [
                NormalizedItem(
                    source_name=self.name,
                    category=self.category,
                    title=title,
                    summary=(
                        f"Total market cap ${total_mcap_usd:,.0f}; "
                        f"BTC dominance {btc_dominance:.2f}% (UTC 24h snapshot)"
                    ),
                    url="https://www.coingecko.com/en/global-charts",
                    published_at=published_at,
                    raw_metadata=raw_metadata,
                )
            ]
        except ValidationError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"normalization failed: {exc}",
                transient=False,
                cause=exc,
            ) from exc

    @staticmethod
    def _extract_float(mapping: dict[str, Any], key: str) -> float | None:
        return CoinGeckoGlobalMarketAdapter._coerce_float(mapping.get(key))

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value) if math.isfinite(float(value)) else None
        return None
