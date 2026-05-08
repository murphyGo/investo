"""Tests for ``investo.sources.defillama_market_structure``."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.defillama_market_structure import DefiLlamaMarketStructureAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "defillama-market-structure"
_WINDOW = FetchWindow.from_kst_date(date(2026, 5, 7))
_CHAINS_URL = "https://api.llama.fi/v2/chains"
_STABLECOINS_URL = "https://stablecoins.llama.fi/stablecoins?includePrices=true"


def _mock_client(
    fixtures: dict[str, bytes],
    *,
    failing_urls: set[str] | None = None,
) -> httpx.AsyncClient:
    failures = failing_urls or set()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url in failures:
            return httpx.Response(503, text="temporary")
        body = fixtures.get(url)
        if body is None:
            return httpx.Response(404, text="missing fixture")
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_emits_tvl_and_stablecoin_items() -> None:
    fixtures = {
        _CHAINS_URL: (_FIXTURE_DIR / "chains.json").read_bytes(),
        _STABLECOINS_URL: (_FIXTURE_DIR / "stablecoins.json").read_bytes(),
    }
    adapter = DefiLlamaMarketStructureAdapter()
    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert [item.raw_metadata["metric"] for item in items] == [
        "chain_tvl",
        "stablecoin_supply",
    ]
    assert items[0].source_name == "defillama-market-structure"
    assert items[0].category == "macro"
    assert items[0].title == "DeFi TVL $74.0B; leader Ethereum"
    assert items[0].raw_metadata["leader_tvl_usd"] == "56000000000.000000"
    assert items[1].title == "Stablecoin supply $161.1B; leader USDT"
    assert items[1].summary is not None
    assert "USDC:36.0B" in items[1].summary


async def test_one_failed_endpoint_keeps_successful_endpoint() -> None:
    fixtures = {_CHAINS_URL: (_FIXTURE_DIR / "chains.json").read_bytes()}
    adapter = DefiLlamaMarketStructureAdapter()
    async with _mock_client(fixtures, failing_urls={_STABLECOINS_URL}) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert [item.raw_metadata["metric"] for item in items] == ["chain_tvl"]


async def test_all_failed_endpoints_raise_source_error() -> None:
    adapter = DefiLlamaMarketStructureAdapter()
    async with _mock_client({}, failing_urls={_CHAINS_URL, _STABLECOINS_URL}) as client:
        with pytest.raises(SourceFetchError):
            await adapter.fetch(client, _WINDOW)


async def test_malformed_payload_raises_source_error() -> None:
    fixtures = {
        _CHAINS_URL: b"{}",
        _STABLECOINS_URL: b"[]",
    }
    adapter = DefiLlamaMarketStructureAdapter()
    async with _mock_client(fixtures) as client:
        with pytest.raises(SourceFetchError, match="unexpected DeFiLlama schema"):
            await adapter.fetch(client, _WINDOW)


async def test_non_finite_numeric_rows_are_dropped() -> None:
    fixtures = {
        _CHAINS_URL: b'[{"name":"Bad","tvl":"NaN"},{"name":"Ethereum","tvl":56000000000}]',
        _STABLECOINS_URL: (
            b'{"peggedAssets":['
            b'{"symbol":"BAD","circulating":{"peggedUSD":"Infinity"}},'
            b'{"symbol":"USDT","circulating":{"peggedUSD":114000000000}}'
            b"]}"
        ),
    }
    adapter = DefiLlamaMarketStructureAdapter()
    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert items[0].raw_metadata["leader"] == "Ethereum"
    assert items[1].raw_metadata["leader"] == "USDT"
