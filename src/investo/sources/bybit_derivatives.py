"""Bybit derivatives adapter with OKX fallback (FD L6.15, u66).

Primary BTC 펀딩비 + 미결제약정(OI) source. A single no-key Bybit v5
``tickers`` call yields both indicators. On Bybit terminal failure the
adapter falls back to OKX (:func:`investo.sources.okx_derivatives.fetch_okx_items`),
emitting the same contract keys with ``*_source=okx``.

**Precedence (u66 plan 2026-05-24): Bybit primary → OKX fallback.**
Both are no-key and geo-safe. Binance fapi is NOT used as primary — it
returns 451 from GHA IPs (the crypto archive already shows
``binance-crypto-market`` status 451). Binance is at most an optional last
resort and is intentionally NOT wired here.

Design choices:

* **One Bybit call, two items** — funding + OI come from the same ticker
  row, so a single HTTP request produces both indicator items.
* **Snapshot semantics** — ``published_at`` = ``window.end_utc`` (R9
  idempotent, never ``datetime.now()``); the crypto segment is UTC 24h.
* **Per-source isolation (R6)** — Bybit terminal failure does not raise;
  it triggers the OKX fallback. Only when BOTH fail does the adapter
  raise ``SourceFetchError`` so the aggregator can isolate it without
  dropping other crypto items.

u74 interface contract (load-bearing — do not rename keys):
funding item ``indicator=btc_funding``, ``btc_funding_rate`` (str),
``funding_source`` ∈ {bybit, okx}; OI item ``indicator=btc_oi``,
``btc_oi_usd`` (USD notional str), ``oi_source``.

Pins:

* No key, no secret (R13 no surface).
* R8 — flat string ``raw_metadata``; ``published_at`` tz-aware UTC.
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
from investo.sources.okx_derivatives import fetch_okx_items
from investo.sources.protocol import SourceFetchError

_BYBIT_URL = "https://api.bybit.com/v5/market/tickers"
_DATA_PAGE = "https://www.bybit.com/trade/usdt/BTCUSDT"


@register
class BybitDerivativesAdapter:
    """Adapter for Bybit v5 tickers (BTC 펀딩비 + OI) with OKX fallback."""

    name: ClassVar[str] = "bybit-derivatives"
    category: ClassVar[Category] = "macro"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        try:
            return await self._fetch_bybit(client, window)
        except SourceFetchError as bybit_exc:
            try:
                return await fetch_okx_items(client, window, source_name="okx-derivatives")
            except SourceFetchError as okx_exc:
                raise SourceFetchError(
                    source_name=self.name,
                    message=(f"Bybit failed ({bybit_exc}); OKX fallback also failed ({okx_exc})"),
                    transient=bybit_exc.transient or okx_exc.transient,
                    cause=okx_exc,
                ) from okx_exc

    async def _fetch_bybit(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        response = await retry_get(
            client,
            _BYBIT_URL,
            source_name=self.name,
            params={"category": "linear", "symbol": "BTCUSDT"},
        )
        payload = parse_json_response(response, source_name=self.name)

        result = payload.get("result") if isinstance(payload, dict) else None
        rows = result.get("list") if isinstance(result, dict) else None
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise SourceFetchError(
                source_name=self.name,
                message="missing result.list[0]",
                transient=False,
            )
        row = rows[0]

        published_at = window.end_utc.astimezone(UTC)
        items: list[NormalizedItem] = []

        funding_rate = _str_field(row, "fundingRate")
        if funding_rate is not None:
            item = _build_item(
                source_name=self.name,
                published_at=published_at,
                title=f"BTC 펀딩비 {funding_rate} (Bybit, UTC 24h)",
                raw_metadata={
                    "indicator": "btc_funding",
                    "btc_funding_rate": funding_rate,
                    "funding_source": "bybit",
                },
            )
            if item is not None:
                items.append(item)

        oi_usd = _float_field(row, "openInterestValue")
        if oi_usd is not None:
            item = _build_item(
                source_name=self.name,
                published_at=published_at,
                title=f"BTC 미결제약정 ${oi_usd:,.0f} (Bybit, UTC 24h)",
                raw_metadata={
                    "indicator": "btc_oi",
                    "btc_oi_usd": format_float(oi_usd, precision=0),
                    "oi_source": "bybit",
                },
            )
            if item is not None:
                items.append(item)

        if not items:
            raise SourceFetchError(
                source_name=self.name,
                message="Bybit ticker missing fundingRate / openInterestValue",
                transient=False,
            )
        return items


def _str_field(row: dict[str, Any], key: str) -> str | None:
    value = row.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _float_field(row: dict[str, Any], key: str) -> float | None:
    raw = _str_field(row, key)
    if raw is None:
        return None
    try:
        parsed = float(raw)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _build_item(
    *,
    source_name: str,
    published_at: datetime,
    title: str,
    raw_metadata: dict[str, str],
) -> NormalizedItem | None:
    try:
        return NormalizedItem(
            source_name=source_name,
            category="macro",
            title=title,
            url=_DATA_PAGE,
            published_at=published_at,
            raw_metadata=raw_metadata,
        )
    except ValidationError:
        return None
