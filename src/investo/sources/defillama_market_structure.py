"""DeFiLlama public market-structure adapter."""

from __future__ import annotations

import asyncio
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

_CHAINS_URL = "https://api.llama.fi/v2/chains"
_STABLECOINS_URL = "https://stablecoins.llama.fi/stablecoins"
_DATA_PAGE_URL = "https://defillama.com/"


@register
class DefiLlamaMarketStructureAdapter:
    """Adapter for public DeFiLlama TVL and stablecoin context."""

    name: ClassVar[str] = "defillama-market-structure"
    category: ClassVar[Category] = "macro"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,
    ) -> list[NormalizedItem]:
        results = await asyncio.gather(
            self._fetch_json(client, _CHAINS_URL, params=None),
            self._fetch_json(client, _STABLECOINS_URL, params={"includePrices": "true"}),
            return_exceptions=True,
        )
        if all(isinstance(result, SourceFetchError) for result in results):
            raise results[0]
        items: list[NormalizedItem] = []
        now_utc = window.end_utc.astimezone(UTC)
        chains_payload, stablecoins_payload = results
        invalid_schema_count = 0
        if isinstance(chains_payload, BaseException):
            if not isinstance(chains_payload, SourceFetchError):
                raise chains_payload
        else:
            chain_item = _chains_to_item(chains_payload, source_name=self.name, now_utc=now_utc)
            if chain_item is not None:
                items.append(chain_item)
            elif not isinstance(chains_payload, list):
                invalid_schema_count += 1
        if isinstance(stablecoins_payload, BaseException):
            if not isinstance(stablecoins_payload, SourceFetchError):
                raise stablecoins_payload
        else:
            stablecoin_item = _stablecoins_to_item(
                stablecoins_payload,
                source_name=self.name,
                now_utc=now_utc,
            )
            if stablecoin_item is not None:
                items.append(stablecoin_item)
            else:
                pegged_assets = (
                    stablecoins_payload.get("peggedAssets")
                    if isinstance(stablecoins_payload, dict)
                    else None
                )
                if not isinstance(pegged_assets, list):
                    invalid_schema_count += 1
        if not items and invalid_schema_count:
            raise SourceFetchError(
                source_name=self.name,
                message="unexpected DeFiLlama schema",
                transient=False,
            )
        return items

    async def _fetch_json(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: dict[str, str] | None,
    ) -> Any:
        response = await retry_get(client, url, source_name=self.name, params=params)
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"malformed JSON: {exc}",
                transient=False,
                cause=exc,
            ) from exc


def _chains_to_item(payload: Any, *, source_name: str, now_utc: datetime) -> NormalizedItem | None:
    if not isinstance(payload, list):
        return None
    rows: list[tuple[str, float]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        tvl = _parse_float(row.get("tvl"))
        if not name or tvl is None or tvl <= 0:
            continue
        rows.append((name, tvl))
    if not rows:
        return None
    rows.sort(key=lambda pair: pair[1], reverse=True)
    top = rows[:5]
    total_tvl = sum(tvl for _, tvl in rows)
    leader_name, leader_tvl = top[0]
    top_summary = ", ".join(f"{name}:{tvl / 1_000_000_000:.1f}B" for name, tvl in top)
    try:
        return NormalizedItem(
            source_name=source_name,
            category="macro",
            title=f"DeFi TVL ${total_tvl / 1_000_000_000:.1f}B; leader {leader_name}",
            summary=f"Top chains by TVL: {top_summary}",
            url=_DATA_PAGE_URL,
            published_at=now_utc,
            raw_metadata={
                "metric": "chain_tvl",
                "total_tvl_usd": format_float(total_tvl),
                "leader": leader_name,
                "leader_tvl_usd": format_float(leader_tvl),
                "top_chain_count": str(len(top)),
            },
        )
    except ValidationError:
        return None


def _stablecoins_to_item(
    payload: Any,
    *,
    source_name: str,
    now_utc: datetime,
) -> NormalizedItem | None:
    pegged_assets = payload.get("peggedAssets") if isinstance(payload, dict) else None
    if not isinstance(pegged_assets, list):
        return None
    rows: list[tuple[str, float]] = []
    for asset in pegged_assets:
        if not isinstance(asset, dict):
            continue
        symbol = str(asset.get("symbol") or asset.get("name") or "").strip()
        circulation = asset.get("circulating")
        total = circulation.get("peggedUSD") if isinstance(circulation, dict) else None
        value = _parse_float(total)
        if not symbol or value is None or value <= 0:
            continue
        rows.append((symbol, value))
    if not rows:
        return None
    rows.sort(key=lambda pair: pair[1], reverse=True)
    top = rows[:5]
    total_supply = sum(value for _, value in rows)
    top_summary = ", ".join(f"{symbol}:{value / 1_000_000_000:.1f}B" for symbol, value in top)
    leader_symbol, leader_value = top[0]
    try:
        return NormalizedItem(
            source_name=source_name,
            category="macro",
            title=f"Stablecoin supply ${total_supply / 1_000_000_000:.1f}B; leader {leader_symbol}",
            summary=f"Top stablecoins: {top_summary}",
            url=_DATA_PAGE_URL,
            published_at=now_utc,
            raw_metadata={
                "metric": "stablecoin_supply",
                "total_supply_usd": format_float(total_supply),
                "leader": leader_symbol,
                "leader_supply_usd": format_float(leader_value),
                "top_asset_count": str(len(top)),
            },
        )
    except ValidationError:
        return None


def _parse_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed
