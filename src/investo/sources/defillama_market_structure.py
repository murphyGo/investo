"""DeFiLlama public market-structure adapter."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from typing import Any, ClassVar

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.models.insights import InsightTime, SourceInsightEnvelope
from investo.models.insights_crypto import (
    LLAMA_SUPPLY,
    LLAMA_TVL,
    decimal_value,
    envelope,
    safe_metric,
)
from investo.sources._config import format_float
from investo.sources._parse import parse_json_response
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_CHAINS_URL = "https://api.llama.fi/v2/chains"
_STABLECOINS_URL = "https://stablecoins.llama.fi/stablecoins"
_DATA_PAGE_URL = "https://defillama.com/"


@dataclass(frozen=True, slots=True)
class _ObservedPayload:
    legacy: Any
    precise: Any
    start: datetime
    end: datetime


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
            self._fetch_json(
                client,
                _CHAINS_URL,
                params=None,
                **({"insights_enabled": True} if window.insights_enabled else {}),
            ),
            self._fetch_json(
                client,
                _STABLECOINS_URL,
                params={"includePrices": "true"},
                **({"insights_enabled": True} if window.insights_enabled else {}),
            ),
            return_exceptions=True,
        )
        if all(isinstance(result, SourceFetchError) for result in results):
            raise results[0]
        items: list[NormalizedItem] = []
        now_utc = window.end_utc.astimezone(UTC)
        chains_payload, stablecoins_payload = results
        chains_observation = (
            chains_payload if isinstance(chains_payload, _ObservedPayload) else None
        )
        stable_observation = (
            stablecoins_payload if isinstance(stablecoins_payload, _ObservedPayload) else None
        )
        if chains_observation:
            chains_payload = chains_observation.legacy
        if stable_observation:
            stablecoins_payload = stable_observation.legacy
        invalid_schema_count = 0
        if isinstance(chains_payload, BaseException):
            if not isinstance(chains_payload, SourceFetchError):
                raise chains_payload
        else:
            chain_item = _chains_to_item(chains_payload, source_name=self.name, now_utc=now_utc)
            if chain_item is not None:
                if chains_observation:
                    chain_item = chain_item.model_copy(
                        update={"insight_envelope": _insight_sum(chains_observation, stable=False)}
                    )
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
                if stable_observation:
                    stablecoin_item = stablecoin_item.model_copy(
                        update={"insight_envelope": _insight_sum(stable_observation, stable=True)}
                    )
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
        insights_enabled: bool = False,
    ) -> Any:
        start = datetime.now(UTC) if insights_enabled else None
        response = await retry_get(client, url, source_name=self.name, params=params)
        end = datetime.now(UTC) if insights_enabled else None
        legacy = parse_json_response(response, source_name=self.name)
        if start is None or end is None:
            return legacy
        try:
            precise = response.json(parse_float=Decimal)
        except ValueError:
            precise = None
        return _ObservedPayload(legacy, precise, start, end)


def _insight_sum(observed: _ObservedPayload, *, stable: bool) -> SourceInsightEnvelope | None:
    payload = observed.precise
    rows = (
        payload.get("peggedAssets")
        if stable and isinstance(payload, dict)
        else payload
        if not stable
        else None
    )
    if not isinstance(rows, list) or len(rows) > 10000:
        return None
    values = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = (
            str(row.get("symbol") or row.get("name") or "").strip()
            if stable
            else str(row.get("name") or "").strip()
        )
        circulation = row.get("circulating")
        raw = (
            circulation.get("peggedUSD")
            if stable and isinstance(circulation, dict)
            else row.get("tvl")
            if not stable
            else None
        )
        # Apply the existing positive/named-row rule, then retain original Decimal tokens.
        legacy = _parse_float(raw)
        if not name or legacy is None or legacy <= 0:
            continue
        value = decimal_value(raw)
        if value is None:
            return None
        identity = (
            str(row.get("id"))
            if stable and row.get("id") is not None
            else name
            if not stable
            else None
        )
        if identity is not None:
            if identity in seen:
                return None
            seen.add(identity)
        values.append(value)
    if not values:
        return None
    with localcontext() as context:
        context.prec = 256
        total = sum(values, Decimal(0))
    clock = (
        InsightTime(
            basis="collection_window",
            precision="exact",
            window_start=observed.start,
            window_end=observed.end,
        )
        if observed.start < observed.end
        else InsightTime(basis="source_response", precision="unknown")
    )
    return envelope(
        "defillama-market-structure",
        [safe_metric(LLAMA_SUPPLY if stable else LLAMA_TVL, total, clock)],
    )


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
