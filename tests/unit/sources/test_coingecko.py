"""Tests for ``investo.sources.coingecko.CoinGeckoPriceAdapter``.

Pins FD L6.3 (extension 2026-05-01):

* Recorded fixture (``fixtures/api/coingecko-price/markets.json``) —
  happy path, field mapping, ISO8601 ``Z``-suffix parsing
* Inline synthetic JSON — null pct fallback, naive timestamp drop,
  empty array → terminal SourceFetchError
* R12 env-var override, default coin list
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.coingecko import CoinGeckoPriceAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "coingecko-price"
_MARKETS_FIXTURE = _FIXTURE_DIR / "markets.json"

# Recorded fixture's last_updated timestamps are 2026-04-30T17:24-25Z
# → inside R7 window for target_date = 2026-05-01.
_WINDOW = FetchWindow.from_kst_date(date(2026, 5, 1))


def _mock_client(body: bytes, *, status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _capturing_client(body: bytes) -> tuple[httpx.AsyncClient, list[httpx.Request]]:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), captured


def _override_coins(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("INVESTO_COINGECKO_COINS", value)


# ---------------------------------------------------------------------------
# Recorded-fixture happy path
# ---------------------------------------------------------------------------


async def test_fetch_three_coins_real_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INVESTO_COINGECKO_COINS", raising=False)
    body = _MARKETS_FIXTURE.read_bytes()
    adapter = CoinGeckoPriceAdapter()
    async with _mock_client(body) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 3
    by_symbol = {item.raw_metadata["symbol"]: item for item in items}
    assert set(by_symbol) == {"btc", "eth", "sol"}
    for item in items:
        assert item.source_name == "coingecko-price"
        assert item.category == "price"
        assert item.published_at.tzinfo is UTC


async def test_title_format_from_real_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INVESTO_COINGECKO_COINS", raising=False)
    body = _MARKETS_FIXTURE.read_bytes()
    adapter = CoinGeckoPriceAdapter()
    async with _mock_client(body) as client:
        items = await adapter.fetch(client, _WINDOW)
    by_symbol = {item.raw_metadata["symbol"]: item for item in items}
    btc = by_symbol["btc"]
    # Recorded: btc price 76105, pct +0.3321 → "BTC $76,105.00 (+0.33%)"
    assert btc.title == "BTC $76,105.00 (+0.33%)"
    eth = by_symbol["eth"]
    # Recorded: eth price 2253.73, pct -0.90081 → "ETH $2,253.73 (-0.90%)"
    assert eth.title == "ETH $2,253.73 (-0.90%)"


async def test_summary_format_from_real_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INVESTO_COINGECKO_COINS", raising=False)
    body = _MARKETS_FIXTURE.read_bytes()
    adapter = CoinGeckoPriceAdapter()
    async with _mock_client(body) as client:
        items = await adapter.fetch(client, _WINDOW)
    btc = next(i for i in items if i.raw_metadata["symbol"] == "btc")
    assert btc.summary is not None
    assert btc.summary.startswith("24h vol: $")
    assert "market cap: $" in btc.summary
    assert "high: $76,529" in btc.summary
    assert "low: $75,103" in btc.summary


async def test_url_uses_coin_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INVESTO_COINGECKO_COINS", raising=False)
    body = _MARKETS_FIXTURE.read_bytes()
    adapter = CoinGeckoPriceAdapter()
    async with _mock_client(body) as client:
        items = await adapter.fetch(client, _WINDOW)
    by_id = {item.raw_metadata["coin_id"]: item for item in items}
    assert str(by_id["bitcoin"].url) == "https://www.coingecko.com/en/coins/bitcoin"
    assert str(by_id["ethereum"].url) == "https://www.coingecko.com/en/coins/ethereum"


async def test_raw_metadata_keys_and_strings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INVESTO_COINGECKO_COINS", raising=False)
    body = _MARKETS_FIXTURE.read_bytes()
    adapter = CoinGeckoPriceAdapter()
    async with _mock_client(body) as client:
        items = await adapter.fetch(client, _WINDOW)
    item = items[0]
    expected_keys = {
        "coin_id",
        "symbol",
        "price_usd",
        "pct_24h",
        "volume_24h",
        "market_cap",
        "high_24h",
        "low_24h",
    }
    assert set(item.raw_metadata) == expected_keys
    assert all(isinstance(v, str) for v in item.raw_metadata.values())


# ---------------------------------------------------------------------------
# Synthetic edge cases
# ---------------------------------------------------------------------------


def _build_entry(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "bitcoin",
        "symbol": "btc",
        "current_price": 50000.0,
        "market_cap": 1_000_000_000_000,
        "total_volume": 30_000_000_000,
        "high_24h": 51000.0,
        "low_24h": 49000.0,
        "price_change_percentage_24h": 1.5,
        "last_updated": "2026-04-30T17:25:01.044Z",
    }
    base.update(overrides)
    return base


async def test_null_pct_24h_defaults_to_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    # New-listing scenario: CoinGecko returns null for 24h pct.
    monkeypatch.setenv("INVESTO_COINGECKO_COINS", "bitcoin")
    body = json.dumps([_build_entry(price_change_percentage_24h=None)]).encode("utf-8")
    adapter = CoinGeckoPriceAdapter()
    async with _mock_client(body) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    assert "(+0.00%)" in items[0].title
    assert items[0].raw_metadata["pct_24h"] == "0.000000"


async def test_naive_last_updated_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    # Synthetic naive ISO (no Z suffix, no offset) → adapter drops the
    # entry per R8. Sibling entries continue.
    monkeypatch.setenv("INVESTO_COINGECKO_COINS", "bitcoin,ethereum")
    body = json.dumps(
        [
            _build_entry(id="bitcoin", symbol="btc"),
            _build_entry(
                id="ethereum",
                symbol="eth",
                last_updated="2026-04-30T17:25:00",  # naive
            ),
        ]
    ).encode("utf-8")
    adapter = CoinGeckoPriceAdapter()
    async with _mock_client(body) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    assert items[0].raw_metadata["symbol"] == "btc"


async def test_empty_response_raises_terminal_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # All coin ids invalid → CoinGecko returns []. The adapter treats
    # this as a config error and raises SourceFetchError(transient=False).
    monkeypatch.setenv("INVESTO_COINGECKO_COINS", "not-a-real-coin")
    adapter = CoinGeckoPriceAdapter()
    async with _mock_client(b"[]") as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _WINDOW)
    assert exc_info.value.transient is False
    assert "empty markets response" in str(exc_info.value)


async def test_non_list_response_raises_terminal_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # CoinGecko sometimes responds with a JSON object (e.g., error
    # envelope) instead of an array — terminal failure for the adapter.
    monkeypatch.setenv("INVESTO_COINGECKO_COINS", "bitcoin")
    adapter = CoinGeckoPriceAdapter()
    async with _mock_client(b'{"error": "rate limited"}') as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _WINDOW)
    assert exc_info.value.transient is False


async def test_outside_r7_window_drops_item(monkeypatch: pytest.MonkeyPatch) -> None:
    # Last updated 30 days ago → not inside the target_date's window.
    # Adapter applies strict R7 (no relaxation for crypto since 24/7
    # source guarantees recent last_updated in production).
    monkeypatch.setenv("INVESTO_COINGECKO_COINS", "bitcoin")
    body = json.dumps([_build_entry(last_updated="2026-03-15T12:00:00Z")]).encode("utf-8")
    adapter = CoinGeckoPriceAdapter()
    async with _mock_client(body) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert items == []


async def test_published_at_in_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_COINGECKO_COINS", "bitcoin")
    body = json.dumps([_build_entry(last_updated="2026-04-30T17:25:01.044Z")]).encode("utf-8")
    adapter = CoinGeckoPriceAdapter()
    async with _mock_client(body) as client:
        items = await adapter.fetch(client, _WINDOW)
    item = items[0]
    assert item.published_at == datetime(2026, 4, 30, 17, 25, 1, 44_000, tzinfo=UTC)


# ---------------------------------------------------------------------------
# R12 — env-var override sent to API
# ---------------------------------------------------------------------------


async def test_env_override_passed_in_query_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_COINGECKO_COINS", "ethereum,solana")
    body = json.dumps(
        [
            _build_entry(id="ethereum", symbol="eth"),
            _build_entry(id="solana", symbol="sol"),
        ]
    ).encode("utf-8")
    adapter = CoinGeckoPriceAdapter()
    client, captured = _capturing_client(body)
    async with client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 2
    # The query string MUST carry exactly the override list, not the
    # default 3-coin tuple.
    assert len(captured) == 1
    assert captured[0].url.params["ids"] == "ethereum,solana"
    assert captured[0].url.params["vs_currency"] == "usd"


async def test_env_unset_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INVESTO_COINGECKO_COINS", raising=False)
    adapter = CoinGeckoPriceAdapter()
    body = json.dumps([_build_entry()]).encode("utf-8")
    client, captured = _capturing_client(body)
    async with client:
        await adapter.fetch(client, _WINDOW)
    # Default list is bitcoin,ethereum,solana.
    assert captured[0].url.params["ids"] == "bitcoin,ethereum,solana"


async def test_env_empty_falls_back_to_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_COINGECKO_COINS", "")
    adapter = CoinGeckoPriceAdapter()
    body = json.dumps([_build_entry()]).encode("utf-8")
    client, captured = _capturing_client(body)
    async with client:
        await adapter.fetch(client, _WINDOW)
    assert captured[0].url.params["ids"] == "bitcoin,ethereum,solana"


# ---------------------------------------------------------------------------
# Class identity
# ---------------------------------------------------------------------------


def test_class_attributes() -> None:
    assert CoinGeckoPriceAdapter.name == "coingecko-price"
    assert CoinGeckoPriceAdapter.category == "price"
