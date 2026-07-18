"""Tests for ``investo.sources.yfinance_history`` (u49).

Pins the 1-year daily-bar history fetcher contract:

* Recorded-fixture replay via :class:`httpx.MockTransport` (R10).
* Per-ticker isolation: a 429 / 5xx / malformed body for one ticker
  must NOT drop sibling tickers from the result dict.
* Empty / shape-broken payload → empty tuple, no exception.
* Concurrency env override.
* Error payload (``chart.error.code``) → :class:`SourceFetchError`.

The fixtures live under
``tests/unit/sources/fixtures/api/yfinance-history/``; recording
session is documented in that directory's ``_meta.json`` sidecar.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from investo.sources.protocol import SourceFetchError
from investo.sources.yfinance_history import (
    DEFAULT_HISTORY_TICKERS,
    fetch_price_history,
    parse_chart_payload,
)

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "yfinance-history"


def _fixture_bytes(name: str) -> bytes:
    return (_FIXTURE_DIR / f"{name}.json").read_bytes()


def _fixture_payload(name: str) -> dict[str, object]:
    return json.loads((_FIXTURE_DIR / f"{name}.json").read_text())


_TICKER_FIXTURE_MAP: dict[str, str] = {
    "^GSPC": "GSPC",
    "^IXIC": "IXIC",
    "^DJI": "DJI",
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "GOOGL": "GOOGL",
    "AMZN": "AMZN",
    "NVDA": "NVDA",
    "META": "META",
    "TSLA": "TSLA",
    "BTC-USD": "BTC-USD",
    "ETH-USD": "ETH-USD",
}


def _build_handler(
    *,
    overrides: dict[str, tuple[int, bytes]] | None = None,
) -> httpx.MockTransport:
    """MockTransport that maps URL path basename to fixture bytes.

    ``overrides`` lets a test inject a non-default status / body for
    a specific Yahoo URL-encoded ticker (e.g. ``%5EGSPC`` for ^GSPC).
    """
    overrides = overrides or {}

    def handler(request: httpx.Request) -> httpx.Response:
        # The path is ``/v8/finance/chart/{ticker}``; the basename is
        # the URL-encoded ticker (e.g. ``%5EGSPC``).
        path = request.url.path
        encoded_ticker = path.rsplit("/", 1)[-1]
        # Decode percent-encoding for fixture lookup.
        from urllib.parse import unquote

        ticker = unquote(encoded_ticker)
        if encoded_ticker in overrides:
            status, body = overrides[encoded_ticker]
            return httpx.Response(status, content=body)
        fixture_name = _TICKER_FIXTURE_MAP.get(ticker)
        if fixture_name is None:
            return httpx.Response(404, content=b'{"chart":{"result":null,"error":null}}')
        return httpx.Response(
            200,
            content=_fixture_bytes(fixture_name),
            headers={"content-type": "application/json"},
        )

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# parse_chart_payload (pure parser)
# ---------------------------------------------------------------------------


def test_parse_chart_payload_returns_ordered_rows() -> None:
    payload = _fixture_payload("AAPL")
    rows = parse_chart_payload(payload, ticker="AAPL")
    assert len(rows) >= 250
    # Rows must be ordered ascending by trading_date.
    dates = [row.trading_date for row in rows]
    assert dates == sorted(dates)


def test_parse_chart_payload_sorts_rows_with_values_still_aligned() -> None:
    payload: dict[str, object] = {
        "chart": {
            "result": [
                {
                    "timestamp": [1700086400, 1700000000],
                    "indicators": {
                        "quote": [
                            {
                                "open": [2.0, 1.0],
                                "high": [2.5, 1.5],
                                "low": [1.5, 0.5],
                                "close": [2.25, 1.25],
                                "volume": [20, 10],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }
    rows = parse_chart_payload(payload, ticker="X")
    assert [row.close for row in rows] == [Decimal("1.25"), Decimal("2.25")]


def test_parse_chart_payload_empty_input_returns_empty() -> None:
    assert parse_chart_payload({}, ticker="AAPL") == ()


def test_parse_chart_payload_missing_chart_key_returns_empty() -> None:
    assert parse_chart_payload({"foo": "bar"}, ticker="AAPL") == ()


def test_parse_chart_payload_null_result_returns_empty() -> None:
    payload: dict[str, object] = {"chart": {"result": None, "error": None}}
    assert parse_chart_payload(payload, ticker="AAPL") == ()


def test_parse_chart_payload_error_block_raises_source_fetch_error() -> None:
    payload: dict[str, object] = {
        "chart": {
            "result": None,
            "error": {"code": "Not Found", "description": "No data found"},
        }
    }
    with pytest.raises(SourceFetchError) as ctx:
        parse_chart_payload(payload, ticker="ZZZ")
    assert ctx.value.transient is False
    assert "Not Found" in str(ctx.value)


def test_parse_chart_payload_skips_rows_with_none_close() -> None:
    payload: dict[str, object] = {
        "chart": {
            "result": [
                {
                    "timestamp": [1700000000, 1700086400],
                    "indicators": {
                        "quote": [
                            {
                                "open": [1.0, 2.0],
                                "high": [1.0, 2.0],
                                "low": [1.0, 2.0],
                                "close": [1.0, None],
                                "volume": [10, 20],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }
    rows = parse_chart_payload(payload, ticker="X")
    assert len(rows) == 1


def test_parse_chart_payload_volume_optional() -> None:
    payload: dict[str, object] = {
        "chart": {
            "result": [
                {
                    "timestamp": [1700000000],
                    "indicators": {
                        "quote": [
                            {
                                "open": [1.0],
                                "high": [1.0],
                                "low": [1.0],
                                "close": [1.0],
                                "volume": [None],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }
    rows = parse_chart_payload(payload, ticker="X")
    assert len(rows) == 1
    assert rows[0].volume is None


# ---------------------------------------------------------------------------
# fetch_price_history (httpx.MockTransport replay)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_returns_history_for_default_basket() -> None:
    transport = _build_handler()
    async with httpx.AsyncClient(transport=transport) as client:
        history = await fetch_price_history(client)
    # Default basket excludes ^VIX; should land 12 tickers from fixtures.
    expected = set(DEFAULT_HISTORY_TICKERS)
    assert set(history) == expected
    # All tickers have at least 250 rows.
    for ticker, rows in history.items():
        if ticker in {"BTC-USD", "ETH-USD"}:
            assert len(rows) >= 360, f"{ticker} rows={len(rows)}"
        else:
            assert len(rows) >= 250, f"{ticker} rows={len(rows)}"


@pytest.mark.asyncio
async def test_fetch_explicit_tickers_argument() -> None:
    transport = _build_handler()
    async with httpx.AsyncClient(transport=transport) as client:
        history = await fetch_price_history(client, tickers=("^GSPC", "AAPL"))
    assert set(history) == {"^GSPC", "AAPL"}


@pytest.mark.asyncio
async def test_fetch_per_ticker_isolation_on_error_status() -> None:
    """A 429 on one ticker drops it; sibling tickers continue."""
    transport = _build_handler(
        overrides={"AAPL": (429, b"Too Many Requests")},
    )
    async with httpx.AsyncClient(transport=transport) as client:
        history = await fetch_price_history(
            client,
            tickers=("^GSPC", "AAPL", "MSFT"),
        )
    assert set(history) == {"^GSPC", "MSFT"}


@pytest.mark.asyncio
async def test_fetch_malformed_json_drops_only_that_ticker() -> None:
    transport = _build_handler(
        overrides={"AAPL": (200, b"not valid json")},
    )
    async with httpx.AsyncClient(transport=transport) as client:
        history = await fetch_price_history(client, tickers=("^GSPC", "AAPL"))
    assert "AAPL" not in history
    assert "^GSPC" in history


@pytest.mark.asyncio
async def test_fetch_empty_basket_returns_empty_dict() -> None:
    transport = _build_handler()
    async with httpx.AsyncClient(transport=transport) as client:
        history = await fetch_price_history(client, tickers=())
    assert history == {}


@pytest.mark.asyncio
async def test_fetch_env_var_override_replaces_default_basket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_YFINANCE_HISTORY_TICKERS", "^GSPC,AAPL")
    transport = _build_handler()
    async with httpx.AsyncClient(transport=transport) as client:
        history = await fetch_price_history(client)
    assert set(history) == {"^GSPC", "AAPL"}


def test_default_history_tickers_is_a_tuple() -> None:
    assert isinstance(DEFAULT_HISTORY_TICKERS, tuple)
    # Snapshot: the basket mirrors the stooq-price / yfinance-price
    # adapters minus ^VIX (Stooq returns N/D and Yahoo's volume is
    # zero-filled — anchors would degrade to None across the board).
    assert "^GSPC" in DEFAULT_HISTORY_TICKERS
    assert "BTC-USD" in DEFAULT_HISTORY_TICKERS
    assert "^VIX" not in DEFAULT_HISTORY_TICKERS
