"""Tests for ``investo.sources.nasdaq_symbol_directory.NasdaqSymbolDirectoryAdapter``."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.nasdaq_symbol_directory import NasdaqSymbolDirectoryAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "nasdaq-symbol-directory"
_NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
_OTHER_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"


def _mock_client(
    fixtures: dict[str, bytes],
    *,
    status: int = 200,
    captured: list[httpx.Request] | None = None,
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        body = fixtures.get(str(request.url), b"not found")
        return httpx.Response(status, content=body, headers={"content-type": "text/plain"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_returns_configured_symbols_from_recorded_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_NASDAQ_SYMBOLS", "AAPL,SPY")
    adapter = NasdaqSymbolDirectoryAdapter()

    async with _mock_client(
        {
            _NASDAQ_URL: (_FIXTURE_DIR / "nasdaqlisted.txt").read_bytes(),
            _OTHER_URL: (_FIXTURE_DIR / "otherlisted.txt").read_bytes(),
        }
    ) as client:
        items = await adapter.fetch(client, FetchWindow.from_kst_date(date(2026, 6, 18)))

    assert {item.raw_metadata["symbol"] for item in items} == {"AAPL", "SPY"}
    assert {item.category for item in items} == {"macro"}
    aapl = next(item for item in items if item.raw_metadata["symbol"] == "AAPL")
    spy = next(item for item in items if item.raw_metadata["symbol"] == "SPY")
    assert aapl.raw_metadata["listing_type"] == "nasdaq"
    assert aapl.raw_metadata["exchange"] == "NASDAQ"
    assert aapl.raw_metadata["etf"] == "N"
    assert spy.raw_metadata["listing_type"] == "other"
    assert spy.raw_metadata["etf"] == "Y"


async def test_requests_are_bounded_to_two_directory_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_NASDAQ_SYMBOLS", "AAPL")
    captured: list[httpx.Request] = []
    adapter = NasdaqSymbolDirectoryAdapter()

    async with _mock_client(
        {
            _NASDAQ_URL: (_FIXTURE_DIR / "nasdaqlisted.txt").read_bytes(),
            _OTHER_URL: (_FIXTURE_DIR / "otherlisted.txt").read_bytes(),
        },
        captured=captured,
    ) as client:
        await adapter.fetch(client, FetchWindow.from_kst_date(date(2026, 6, 18)))

    assert [str(request.url) for request in captured] == [_NASDAQ_URL, _OTHER_URL]
    assert all("Investo/1.0" in request.headers["user-agent"] for request in captured)


async def test_unknown_configured_symbol_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_NASDAQ_SYMBOLS", "NOT_A_SYMBOL")
    adapter = NasdaqSymbolDirectoryAdapter()

    async with _mock_client(
        {
            _NASDAQ_URL: (_FIXTURE_DIR / "nasdaqlisted.txt").read_bytes(),
            _OTHER_URL: (_FIXTURE_DIR / "otherlisted.txt").read_bytes(),
        }
    ) as client:
        items = await adapter.fetch(client, FetchWindow.from_kst_date(date(2026, 6, 18)))

    assert items == []


async def test_malformed_rows_are_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_NASDAQ_SYMBOLS", "AAPL")
    nasdaq = (
        b"Symbol|Security Name|Market Category|Test Issue|Financial Status|"
        b"Round Lot Size|ETF|NextShares\n"
        b"AAPL|Apple Inc. Common Stock|Q|N|N|100|N|N\n"
        b"BROKEN|too|few\n"
    )
    other = (
        b"ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|"
        b"Test Issue|NASDAQ Symbol\n"
    )
    adapter = NasdaqSymbolDirectoryAdapter()

    async with _mock_client({_NASDAQ_URL: nasdaq, _OTHER_URL: other}) as client:
        items = await adapter.fetch(client, FetchWindow.from_kst_date(date(2026, 6, 18)))

    assert [item.raw_metadata["symbol"] for item in items] == ["AAPL"]


async def test_status_error_raises_source_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_NASDAQ_SYMBOLS", "AAPL")
    adapter = NasdaqSymbolDirectoryAdapter()

    async with _mock_client({_NASDAQ_URL: b"temporary"}, status=503) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, FetchWindow.from_kst_date(date(2026, 6, 18)))

    assert exc_info.value.transient is True
