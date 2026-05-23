"""Tests for ``investo.sources.coingecko_global_market`` (FD L6.14, u66).

R10 four-path coverage:

* success — recorded ``global.json`` (btc dominance 58.07, total mcap)
* empty/missing-fields — dominance/mcap absent → terminal SourceFetchError
* malformed — non-JSON body → terminal SourceFetchError
* auth/error — 4xx terminal status surfaced by ``retry_get``.

Pins the u74 raw_metadata contract keys and flat-string R8 rule.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.coingecko_global_market import CoinGeckoGlobalMarketAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "coingecko-global-market"
_WINDOW = FetchWindow.from_kst_date(date(2026, 5, 23))


def _client(body: bytes, *, status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_success_real_fixture() -> None:
    adapter = CoinGeckoGlobalMarketAdapter()
    async with _client((_FIXTURE_DIR / "global.json").read_bytes()) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    item = items[0]
    assert item.source_name == "coingecko-global-market"
    assert item.category == "macro"
    assert item.published_at.tzinfo is UTC
    assert "BTC dominance 58.07%" in item.title


async def test_raw_metadata_contract_keys() -> None:
    adapter = CoinGeckoGlobalMarketAdapter()
    async with _client((_FIXTURE_DIR / "global.json").read_bytes()) as client:
        items = await adapter.fetch(client, _WINDOW)
    meta = items[0].raw_metadata
    assert meta["indicator"] == "global_market"
    assert meta["btc_dominance_pct"] == "58.07"
    assert meta["total_market_cap_usd"] == "2623499078661"
    assert "eth_dominance_pct" in meta
    assert "market_cap_change_24h_pct" in meta
    assert meta["updated_at"] == "1779567583"
    assert all(isinstance(v, str) for v in meta.values())


async def test_published_at_from_updated_at() -> None:
    adapter = CoinGeckoGlobalMarketAdapter()
    async with _client((_FIXTURE_DIR / "global.json").read_bytes()) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert items[0].published_at == datetime(2026, 5, 23, 20, 19, 43, tzinfo=UTC)


async def test_missing_fields_raises_terminal() -> None:
    adapter = CoinGeckoGlobalMarketAdapter()
    async with _client((_FIXTURE_DIR / "missing-fields.json").read_bytes()) as client:
        with pytest.raises(SourceFetchError) as exc:
            await adapter.fetch(client, _WINDOW)
    assert exc.value.transient is False


async def test_malformed_raises_terminal() -> None:
    adapter = CoinGeckoGlobalMarketAdapter()
    async with _client((_FIXTURE_DIR / "malformed.json").read_bytes()) as client:
        with pytest.raises(SourceFetchError) as exc:
            await adapter.fetch(client, _WINDOW)
    assert exc.value.transient is False


async def test_http_error_status_raises() -> None:
    adapter = CoinGeckoGlobalMarketAdapter()
    async with _client(b"too many requests", status=429) as client:
        with pytest.raises(SourceFetchError):
            await adapter.fetch(client, _WINDOW)


async def test_missing_updated_at_falls_back_to_window_end() -> None:
    body = b'{"data":{"market_cap_percentage":{"btc":50.0},"total_market_cap":{"usd":1000.0}}}'
    adapter = CoinGeckoGlobalMarketAdapter()
    async with _client(body) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert items[0].published_at == _WINDOW.end_utc.astimezone(UTC)
    assert "updated_at" not in items[0].raw_metadata


def test_class_attributes() -> None:
    assert CoinGeckoGlobalMarketAdapter.name == "coingecko-global-market"
    assert CoinGeckoGlobalMarketAdapter.category == "macro"
