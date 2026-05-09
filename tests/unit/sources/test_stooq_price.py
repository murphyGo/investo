"""Tests for ``investo.sources.stooq_price.StooqPriceAdapter``.

Pins the algorithm declared in ``stooq_price.py``:

* Recorded fixtures replay (``fixtures/api/stooq-price/``) — happy path,
  field mapping, header-row CSV parse.
* ``N/D`` placeholder rows (e.g. ``^VIX``) are silently skipped — the
  adapter must not raise and must not emit a NormalizedItem for them.
* Per-ticker isolation — a 5xx on one ticker does not drop sibling
  tickers.
* R12 env-var override (``INVESTO_STOOQ_TICKERS``).
* Mapping override — an operator-supplied ticker that has no entry in
  ``_TICKER_MAP`` is skipped silently.
* R11 — ``published_at`` resolves to 16:00 ET on the trading day,
  converted to UTC, regardless of whether the trading day was in EST
  or EDT.
* URL builder — pegs to ``https://stooq.com/q/?s={stooq_symbol}``.
* Concurrency override (``INVESTO_STOOQ_CONCURRENCY``).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.stooq_price import StooqPriceAdapter

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "stooq-price"

# Window value is unused — see R11 docstring on the adapter.
_WINDOW = FetchWindow.from_kst_date(date(2026, 5, 9))


def _override_tickers(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("INVESTO_STOOQ_TICKERS", value)


def _fixture_bytes(name: str) -> bytes:
    return (_FIXTURE_DIR / f"{name}.csv").read_bytes()


def _stooq_handler(
    *,
    bodies: dict[str, bytes],
    statuses: dict[str, int] | None = None,
) -> httpx.MockTransport:
    """Build a MockTransport that routes by Stooq ``?s=`` query param.

    ``bodies`` and ``statuses`` are keyed by Stooq symbol (e.g. ``"^spx"``,
    ``"aapl.us"``). Unknown symbols receive 404.
    """
    statuses = statuses or {}

    def handler(request: httpx.Request) -> httpx.Response:
        symbol = request.url.params.get("s") or ""
        body = bodies.get(symbol)
        if body is None:
            return httpx.Response(404, content=b"not found")
        return httpx.Response(
            statuses.get(symbol, 200),
            content=body,
            headers={"content-type": "text/csv"},
        )

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Class identity — adapter contract
# ---------------------------------------------------------------------------


def test_class_attributes() -> None:
    assert StooqPriceAdapter.name == "stooq-price"
    assert StooqPriceAdapter.category == "price"


# ---------------------------------------------------------------------------
# Recorded-fixture happy path
# ---------------------------------------------------------------------------


async def test_fetch_two_us_tickers_real_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    _override_tickers(monkeypatch, "^GSPC,AAPL")
    bodies = {"^spx": _fixture_bytes("GSPC"), "aapl.us": _fixture_bytes("AAPL")}
    transport = _stooq_handler(bodies=bodies)
    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 2
    by_ticker = {item.raw_metadata["ticker"]: item for item in items}
    assert set(by_ticker) == {"^GSPC", "AAPL"}
    for item in items:
        assert item.source_name == "stooq-price"
        assert item.category == "price"
        assert item.published_at.tzinfo is UTC


async def test_aapl_field_mapping_from_real_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    _override_tickers(monkeypatch, "AAPL")
    bodies = {"aapl.us": _fixture_bytes("AAPL")}
    transport = _stooq_handler(bodies=bodies)
    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    item = items[0]
    # Recorded row: AAPL.US,2026-05-08,22:00:21,290.01,294.76,290,293.32,52692761
    assert item.title == "AAPL 293.32"
    assert item.summary is not None
    assert item.summary.startswith("O:290.01 H:294.76 L:290.00 C:293.32 V:52692761")
    assert item.raw_metadata["ticker"] == "AAPL"
    assert item.raw_metadata["stooq_symbol"] == "aapl.us"
    assert item.raw_metadata["close"] == "293.320000"
    assert item.raw_metadata["volume"] == "52692761"
    assert str(item.url) == "https://stooq.com/q/?s=aapl.us"


async def test_raw_metadata_keys_all_strings(monkeypatch: pytest.MonkeyPatch) -> None:
    _override_tickers(monkeypatch, "AAPL")
    bodies = {"aapl.us": _fixture_bytes("AAPL")}
    transport = _stooq_handler(bodies=bodies)
    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, _WINDOW)
    item = items[0]
    expected = {"ticker", "stooq_symbol", "open", "high", "low", "close", "volume"}
    assert set(item.raw_metadata) == expected
    assert all(isinstance(v, str) for v in item.raw_metadata.values())


async def test_crypto_ticker_volume_truncates_fractional(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stooq crypto rows ship fractional volume; we coerce to int (truncating)."""
    _override_tickers(monkeypatch, "BTC-USD")
    bodies = {"btc.v": _fixture_bytes("BTC-USD")}
    transport = _stooq_handler(bodies=bodies)
    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    item = items[0]
    # Recorded volume: 14237.042997827913 → int → 14237
    assert item.raw_metadata["volume"] == "14237"
    assert item.raw_metadata["ticker"] == "BTC-USD"
    assert item.raw_metadata["stooq_symbol"] == "btc.v"


# ---------------------------------------------------------------------------
# N/D placeholder — Stooq's "unknown / unsupported ticker" sentinel
# ---------------------------------------------------------------------------


async def test_nd_placeholder_skipped_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _override_tickers(monkeypatch, "^VIX")
    bodies = {"^vix": _fixture_bytes("VIX")}
    transport = _stooq_handler(bodies=bodies)
    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert items == []


async def test_unknown_ticker_response_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stooq returns 200 + N/D row for fabricated symbols (NOTFOUND fixture)."""
    _override_tickers(monkeypatch, "^GSPC")
    # Re-route the ^spx Stooq symbol to the NOTFOUND fixture.
    bodies = {"^spx": _fixture_bytes("NOTFOUND")}
    transport = _stooq_handler(bodies=bodies)
    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert items == []


async def test_nd_placeholder_does_not_drop_sibling_tickers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """^VIX returns N/D, AAPL returns happy-path → exactly one item."""
    _override_tickers(monkeypatch, "^VIX,AAPL")
    bodies = {"^vix": _fixture_bytes("VIX"), "aapl.us": _fixture_bytes("AAPL")}
    transport = _stooq_handler(bodies=bodies)
    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    assert items[0].raw_metadata["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# Per-ticker isolation (intra-adapter R6 analogue)
# ---------------------------------------------------------------------------


async def test_5xx_on_one_ticker_isolated_from_siblings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _override_tickers(monkeypatch, "^GSPC,AAPL")
    bodies = {"^spx": _fixture_bytes("GSPC"), "aapl.us": _fixture_bytes("AAPL")}
    transport = _stooq_handler(bodies=bodies, statuses={"^spx": 503})
    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, _WINDOW)
    # ^GSPC drops (5xx after retry budget); AAPL succeeds.
    assert len(items) == 1
    assert items[0].raw_metadata["ticker"] == "AAPL"


async def test_malformed_csv_row_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    _override_tickers(monkeypatch, "^GSPC,AAPL")
    malformed = (
        b"Symbol,Date,Time,Open,High,Low,Close,Volume\n^SPX,not-a-date,xx,abc,def,ghi,jkl,mno\n"
    )
    bodies = {"^spx": malformed, "aapl.us": _fixture_bytes("AAPL")}
    transport = _stooq_handler(bodies=bodies)
    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    assert items[0].raw_metadata["ticker"] == "AAPL"


async def test_empty_body_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    _override_tickers(monkeypatch, "^GSPC,AAPL")
    bodies = {"^spx": b"", "aapl.us": _fixture_bytes("AAPL")}
    transport = _stooq_handler(bodies=bodies)
    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    assert items[0].raw_metadata["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# Mapping — unknown ticker tokens are silently skipped
# ---------------------------------------------------------------------------


async def test_unmapped_ticker_silently_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Operator passes a token we have no Stooq mapping for — drop, don't raise."""
    _override_tickers(monkeypatch, "AAPL,XYZ_NOMAPPING")
    bodies = {"aapl.us": _fixture_bytes("AAPL")}
    transport = _stooq_handler(bodies=bodies)
    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    assert items[0].raw_metadata["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# R11 — published_at pinned to 16:00 ET on the trading day
# ---------------------------------------------------------------------------


async def test_published_at_pinned_to_us_close(monkeypatch: pytest.MonkeyPatch) -> None:
    _override_tickers(monkeypatch, "AAPL")
    bodies = {"aapl.us": _fixture_bytes("AAPL")}
    transport = _stooq_handler(bodies=bodies)
    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, _WINDOW)
    item = items[0]
    # Recorded date: 2026-05-08 (Friday). EDT (UTC-4) → 16:00 ET == 20:00 UTC.
    assert item.published_at == datetime(2026, 5, 8, 20, 0, tzinfo=UTC)


async def test_published_at_winter_est_close(monkeypatch: pytest.MonkeyPatch) -> None:
    """Synthetic January row → EST (UTC-5) → 16:00 ET == 21:00 UTC."""
    _override_tickers(monkeypatch, "AAPL")
    body = (
        b"Symbol,Date,Time,Open,High,Low,Close,Volume\n"
        b"AAPL.US,2026-01-14,22:00:00,150.00,152.00,149.00,151.00,1000000\n"
    )
    bodies = {"aapl.us": body}
    transport = _stooq_handler(bodies=bodies)
    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=transport) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    assert items[0].published_at == datetime(2026, 1, 14, 21, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# R12 — env-var override
# ---------------------------------------------------------------------------


async def test_env_override_uses_only_specified_tickers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _override_tickers(monkeypatch, "META,GOOGL")
    bodies = {"meta.us": _fixture_bytes("META"), "googl.us": _fixture_bytes("GOOGL")}
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        symbol = request.url.params.get("s") or ""
        requested.append(symbol)
        body = bodies.get(symbol)
        if body is None:
            return httpx.Response(404, content=b"not found")
        return httpx.Response(200, content=body, headers={"content-type": "text/csv"})

    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert sorted(requested) == ["googl.us", "meta.us"]
    assert {item.raw_metadata["ticker"] for item in items} == {"META", "GOOGL"}


async def test_env_unset_uses_default_thirteen_tickers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INVESTO_STOOQ_TICKERS", raising=False)
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        symbol = request.url.params.get("s") or ""
        requested.append(symbol)
        # All symbols hit the NOTFOUND fixture — adapter emits 0 items
        # but we capture the requested set for the count assertion.
        return httpx.Response(
            200, content=_fixture_bytes("NOTFOUND"), headers={"content-type": "text/csv"}
        )

    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert items == []
    # 13 default tickers — the union of the 11 yfinance equity/index
    # set plus BTC-USD / ETH-USD.
    assert set(requested) == {
        "^spx",
        "^ndq",
        "^dji",
        "^vix",
        "aapl.us",
        "msft.us",
        "googl.us",
        "amzn.us",
        "nvda.us",
        "meta.us",
        "tsla.us",
        "btc.v",
        "eth.v",
    }


async def test_user_agent_is_investo_branded(monkeypatch: pytest.MonkeyPatch) -> None:
    _override_tickers(monkeypatch, "AAPL")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("user-agent", ""))
        return httpx.Response(
            200, content=_fixture_bytes("AAPL"), headers={"content-type": "text/csv"}
        )

    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await adapter.fetch(client, _WINDOW)
    assert seen == ["Investo/1.0 (https://murphygo.github.io/investo)"]


async def test_concurrency_override_caps_in_flight(monkeypatch: pytest.MonkeyPatch) -> None:
    _override_tickers(monkeypatch, "AAPL,MSFT,GOOGL,AMZN,NVDA")
    monkeypatch.setenv("INVESTO_STOOQ_CONCURRENCY", "1")
    active = 0
    max_active = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(
            200, content=_fixture_bytes("AAPL"), headers={"content-type": "text/csv"}
        )

    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 5
    assert max_active == 1


async def test_concurrency_default_caps_at_three(monkeypatch: pytest.MonkeyPatch) -> None:
    _override_tickers(monkeypatch, "AAPL,MSFT,GOOGL,AMZN,NVDA,META")
    monkeypatch.delenv("INVESTO_STOOQ_CONCURRENCY", raising=False)
    active = 0
    max_active = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(
            200, content=_fixture_bytes("AAPL"), headers={"content-type": "text/csv"}
        )

    adapter = StooqPriceAdapter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 6
    assert max_active == 3
