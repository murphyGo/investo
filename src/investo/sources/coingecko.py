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
* **Explicit time basis** — u164 normal runs permit a live snapshot
  within six hours of response receipt. Historical callers retain R7
  date filtering; a current quote is never backdated to a prior close.
* **Per-coin isolation** — a single bad entry (naive ``last_updated``,
  pydantic validation failure) is dropped without affecting siblings
  in the same response.

Pins (extension 2026-05-01):

* AC-5.5 / R12 — `INVESTO_COINGECKO_COINS` env-var override
* R8 — `raw_metadata` is string-keyed and string-valued
"""

from __future__ import annotations

import logging
import math
import os
from datetime import UTC, datetime, timedelta
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
_ENV_DEMO_KEY = "COINGECKO_DEMO_API_KEY"
_logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _finite_number(value: Any, *, nonnegative: bool = False) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(number) or (nonnegative and number < 0):
        return None
    return number


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
        demo_key = os.environ.get(_ENV_DEMO_KEY, "").strip()
        response = await retry_get(
            client,
            self._ENDPOINT,
            source_name=self.name,
            headers={"x-cg-demo-api-key": demo_key} if demo_key else None,
            params={
                "vs_currency": "usd",
                "ids": ",".join(coins),
                "price_change_percentage": "24h",
            },
        )
        received_at = _utc_now()
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
        invalid = stale = future = outside = 0
        for entry in payload:
            normalized = self._normalize_entry(entry)
            if normalized is None:
                invalid += 1
                continue
            if window.price_snapshot_at is not None:
                if normalized.published_at < received_at - timedelta(hours=6):
                    stale += 1
                    continue
                if normalized.published_at > received_at:
                    future += 1
                    continue
                as_of = normalized.published_at.isoformat()
                normalized = normalized.model_copy(
                    update={
                        "title": f"조회 시점 가격 · {normalized.title}",
                        "summary": (f"기준 {as_of} (UTC); CoinGecko; {normalized.summary or ''}")[
                            :SUMMARY_MAX_LEN
                        ],
                        "raw_metadata": {
                            **normalized.raw_metadata,
                            "price_time_basis": "live_snapshot",
                            "price_as_of": as_of,
                            "observed_at": received_at.isoformat(),
                            "price_snapshot_reference_at": window.price_snapshot_at.isoformat(),
                            "report_target_date": window.target_date.isoformat(),
                        },
                    }
                )
            elif not window.contains(normalized.published_at):
                outside += 1
                continue
            items.append(normalized)
        _logger.info(
            "coingecko eligibility kept=%d invalid=%d stale=%d future=%d outside_window=%d",
            len(items),
            invalid,
            stale,
            future,
            outside,
        )
        return items

    def _normalize_entry(self, entry: Any) -> NormalizedItem | None:
        if not isinstance(entry, dict):
            return None

        coin_id = entry.get("id")
        symbol = entry.get("symbol")
        price = _finite_number(entry.get("current_price"), nonnegative=True)
        if (
            not isinstance(coin_id, str)
            or not isinstance(symbol, str)
            or price is None
            or price <= 0
        ):
            return None

        last_updated_raw = entry.get("last_updated")
        if not isinstance(last_updated_raw, str):
            return None
        try:
            last_updated = parse_iso8601_to_utc(last_updated_raw)
        except ValueError:
            return None

        pct = _finite_number(entry.get("price_change_percentage_24h"))
        metrics = {
            "volume_24h": _finite_number(entry.get("total_volume"), nonnegative=True),
            "market_cap": _finite_number(entry.get("market_cap"), nonnegative=True),
            "high_24h": _finite_number(entry.get("high_24h"), nonnegative=True),
            "low_24h": _finite_number(entry.get("low_24h"), nonnegative=True),
        }
        title = f"{symbol.upper()} ${price:,.2f}"
        if pct is not None:
            title += f" ({pct:+.2f}%)"
        summary = "; ".join(
            f"{label}: ${value:,.{precision}f}"
            for key, label, precision in (
                ("volume_24h", "24h vol", 0),
                ("market_cap", "market cap", 0),
                ("high_24h", "high", 2),
                ("low_24h", "low", 2),
            )
            if (value := metrics[key]) is not None
        )
        if len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        raw_metadata: dict[str, str] = {
            "coin_id": coin_id,
            "symbol": symbol,
            "price_usd": format_float(price),
        }
        if pct is not None:
            raw_metadata["pct_24h"] = format_float(pct)
        raw_metadata.update(
            {key: format_float(value) for key, value in metrics.items() if value is not None}
        )

        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary or None,
                url=f"https://www.coingecko.com/en/coins/{coin_id}",
                published_at=last_updated,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None
