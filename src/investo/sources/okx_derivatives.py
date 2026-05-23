"""OKX derivatives adapter (FD L6.15 fallback, u66).

No-key, geo-safe OKX public funding-rate + open-interest reader for
BTC-USD-SWAP. Emits BTC 펀딩비 + BTC OI items with ``category="macro"``.
This adapter is the fallback for :mod:`investo.sources.bybit_derivatives`
(Bybit primary → OKX fallback), and is also independently registered so
segment routing can recognise its ``source_name``.

The shared funding/OI item-building logic lives in
:func:`build_okx_items`, which the Bybit adapter calls directly on Bybit
terminal failure so the emitted ``source_name`` stays ``okx-derivatives``
(R8: ``source_name`` == producing adapter name) with
``funding_source=okx`` / ``oi_source=okx``.

u74 interface contract (load-bearing — do not rename keys):
funding item ``indicator=btc_funding``, ``btc_funding_rate`` (str),
``funding_source`` ∈ {bybit, okx}; OI item ``indicator=btc_oi``,
``btc_oi_usd`` (USD notional str), ``oi_source``.

Pins:

* No key, no secret (R13 no surface).
* R8 — flat string ``raw_metadata``; ``published_at`` tz-aware UTC.
* R6 — only ``SourceFetchError`` for source-side failures.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import format_float
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

OKX_SOURCE_NAME = "okx-derivatives"
_FUNDING_URL = "https://www.okx.com/api/v5/public/funding-rate"
_OI_URL = "https://www.okx.com/api/v5/public/open-interest"
_INST_ID = "BTC-USD-SWAP"
_DATA_PAGE = "https://www.okx.com/trade-swap/btc-usd-swap"


@register
class OkxDerivativesAdapter:
    """Adapter for OKX public funding-rate + open-interest (BTC swap)."""

    name: ClassVar[str] = OKX_SOURCE_NAME
    category: ClassVar[Category] = "macro"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        return await fetch_okx_items(client, window, source_name=self.name)


async def fetch_okx_items(
    client: httpx.AsyncClient,
    window: FetchWindow,
    *,
    source_name: str,
) -> list[NormalizedItem]:
    """Fetch OKX funding + OI and build the two indicator items.

    Used both by :class:`OkxDerivativesAdapter` and as the Bybit fallback
    path. ``source_name`` is the emitting adapter's name so items satisfy
    R8 regardless of which adapter triggered the OKX path.
    """

    funding_payload = await _fetch_json(client, _FUNDING_URL, source_name, {"instId": _INST_ID})
    oi_payload = await _fetch_json(
        client, _OI_URL, source_name, {"instType": "SWAP", "instId": _INST_ID}
    )
    published_at = window.end_utc.astimezone(UTC)
    items: list[NormalizedItem] = []

    funding_rate = _first_data_str(funding_payload, "fundingRate")
    if funding_rate is not None:
        item = _build_item(
            source_name=source_name,
            published_at=published_at,
            title=f"BTC 펀딩비 {funding_rate} (OKX, UTC 24h)",
            raw_metadata={
                "indicator": "btc_funding",
                "btc_funding_rate": funding_rate,
                "funding_source": "okx",
            },
        )
        if item is not None:
            items.append(item)

    oi_usd = _first_data_float(oi_payload, "oiUsd")
    if oi_usd is not None:
        item = _build_item(
            source_name=source_name,
            published_at=published_at,
            title=f"BTC 미결제약정 ${oi_usd:,.0f} (OKX, UTC 24h)",
            raw_metadata={
                "indicator": "btc_oi",
                "btc_oi_usd": format_float(oi_usd, precision=0),
                "oi_source": "okx",
            },
        )
        if item is not None:
            items.append(item)

    if not items:
        raise SourceFetchError(
            source_name=source_name,
            message="OKX funding-rate / open-interest missing expected fields",
            transient=False,
        )
    return items


async def _fetch_json(
    client: httpx.AsyncClient,
    url: str,
    source_name: str,
    params: dict[str, str],
) -> Any:
    response = await retry_get(client, url, source_name=source_name, params=params)
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise SourceFetchError(
            source_name=source_name,
            message=f"malformed JSON: {exc}",
            transient=False,
            cause=exc,
        ) from exc


def _first_data_str(payload: Any, key: str) -> str | None:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list) or not data:
        return None
    entry = data[0]
    if not isinstance(entry, dict):
        return None
    value = entry.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _first_data_float(payload: Any, key: str) -> float | None:
    raw = _first_data_str(payload, key)
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
