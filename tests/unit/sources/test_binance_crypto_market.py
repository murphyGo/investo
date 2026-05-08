"""Tests for ``investo.sources.binance_crypto_market``."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.binance_crypto_market import BinanceCryptoMarketAdapter

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "binance-crypto-market"
_WINDOW = FetchWindow.from_kst_date(date(2026, 5, 7))


def _mock_client(
    fixtures: dict[str, bytes],
    *,
    status_per: dict[str, int] | None = None,
) -> httpx.AsyncClient:
    statuses = status_per or {}

    def handler(request: httpx.Request) -> httpx.Response:
        symbol = request.url.params.get("symbol", "")
        body = fixtures.get(symbol)
        status = statuses.get(symbol, 200)
        if body is None:
            return httpx.Response(404, json={"msg": "missing fixture"})
        return httpx.Response(status, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_parses_configured_symbols(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_CRYPTO_MARKET_SYMBOLS", "BTCUSDT,ETHUSDT")
    fixtures = {
        "BTCUSDT": (_FIXTURE_DIR / "BTCUSDT.json").read_bytes(),
        "ETHUSDT": (_FIXTURE_DIR / "ETHUSDT.json").read_bytes(),
    }
    adapter = BinanceCryptoMarketAdapter()
    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert [item.raw_metadata["symbol"] for item in items] == ["BTCUSDT", "ETHUSDT"]
    assert items[0].source_name == "binance-crypto-market"
    assert items[0].category == "price"
    assert items[0].title == "BTCUSDT 24h 76,050.12 (+2.91%)"
    assert items[0].raw_metadata["quote_volume"] == "3152800000.120000"
    assert items[0].raw_metadata["trade_count"] == "1823456"
    assert str(items[0].url) == "https://www.binance.com/en/markets/overview"


async def test_invalid_symbol_isolated_from_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_CRYPTO_MARKET_SYMBOLS", "BTCUSDT,BADUSDT")
    fixtures = {"BTCUSDT": (_FIXTURE_DIR / "BTCUSDT.json").read_bytes()}
    adapter = BinanceCryptoMarketAdapter()
    async with _mock_client(fixtures, status_per={"BADUSDT": 404}) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert [item.raw_metadata["symbol"] for item in items] == ["BTCUSDT"]


async def test_malformed_symbol_payload_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_CRYPTO_MARKET_SYMBOLS", "BTCUSDT")
    adapter = BinanceCryptoMarketAdapter()
    async with _mock_client({"BTCUSDT": b'{"symbol":"BTCUSDT","lastPrice":"bad"}'}) as client:
        assert await adapter.fetch(client, _WINDOW) == []
