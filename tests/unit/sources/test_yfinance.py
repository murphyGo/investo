"""Tests for ``investo.sources.yfinance.YFinancePriceAdapter``.

Pins the algorithm from FD L6.2 (extension 2026-05-01):

* Recorded fixtures (``fixtures/api/yfinance-price/``) — happy path,
  field mapping, R11 close-time resolution
* Inline synthetic JSON — null-OHLC fall-through, error-shape
  detection, mixed valid/invalid ticker isolation
* DST anchor cases — EDT (July) vs EST (January) close timestamps
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.yfinance import YFinancePriceAdapter

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "yfinance-price"
_QUERY2_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "yfinance-history"
_GSPC_FIXTURE = _FIXTURE_DIR / "GSPC.json"
_AAPL_FIXTURE = _FIXTURE_DIR / "AAPL.json"
_INVALID_FIXTURE = _FIXTURE_DIR / "INVALID.json"

# Any window — adapter applies R7 relaxation, so the window value is
# unused per L6.2. Tests use a fixed window for clarity.
_WINDOW = FetchWindow.from_kst_date(date(2026, 5, 1))


def _mock_client(
    fixtures: dict[str, bytes], *, status_per: dict[str, int] | None = None
) -> httpx.AsyncClient:
    """Mock client routing by ticker (extracted from the request path).

    ``fixtures`` maps the URL-encoded ticker (e.g. ``"%5EGSPC"``,
    ``"AAPL"``) to the JSON body bytes. ``status_per`` overrides the
    response status for specific tickers; default 200.
    """

    statuses = status_per or {}

    def handler(request: httpx.Request) -> httpx.Response:
        # Path: /v8/finance/chart/<URL-encoded-ticker>
        path = request.url.path
        encoded = path.rsplit("/", 1)[-1]
        ticker = unquote(encoded)
        body = fixtures.get(ticker) or fixtures.get(encoded)
        if body is None:
            return httpx.Response(404, json={"error": f"no fixture for {ticker}"})
        status = statuses.get(ticker, statuses.get(encoded, 200))
        return httpx.Response(status, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _override_tickers(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("INVESTO_YFINANCE_TICKERS", value)
    # Existing single-phase tests isolate the critical basket by making
    # enrichment overlap it; the adapter de-duplicates cross-phase symbols.
    monkeypatch.setenv("INVESTO_YFINANCE_ENRICHMENT_TICKERS", value)


# ---------------------------------------------------------------------------
# Recorded-fixture happy path
# ---------------------------------------------------------------------------


async def test_fetch_two_tickers_real_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    _override_tickers(monkeypatch, "^GSPC,AAPL")
    fixtures = {
        "^GSPC": _GSPC_FIXTURE.read_bytes(),
        "AAPL": _AAPL_FIXTURE.read_bytes(),
    }
    adapter = YFinancePriceAdapter()
    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 2
    by_ticker = {item.raw_metadata["ticker"]: item for item in items}
    assert set(by_ticker) == {"^GSPC", "AAPL"}
    for item in items:
        assert item.source_name == "yfinance-price"
        assert item.category == "price"
        assert item.published_at.tzinfo is UTC


async def test_query2_1y_recording_preserves_snapshot_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _override_tickers(monkeypatch, "AAPL")
    adapter = YFinancePriceAdapter()
    fixtures = {"AAPL": (_QUERY2_FIXTURE_DIR / "AAPL.json").read_bytes()}
    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert len(items) == 1
    item = items[0]
    assert item.source_name == "yfinance-price"
    assert item.category == "price"
    assert item.raw_metadata["ticker"] == "AAPL"
    assert item.raw_metadata["provenance"] == "query2-snapshot"
    assert item.summary is not None
    assert item.title.startswith("AAPL ")


async def test_title_and_summary_format_from_real_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _override_tickers(monkeypatch, "AAPL")
    adapter = YFinancePriceAdapter()
    fixtures = {"AAPL": _AAPL_FIXTURE.read_bytes()}
    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)
    item = items[0]
    # AAPL fixture closes (5 days): [271.06, 267.61, 270.71, 270.17, 272.255].
    # latest_idx = 4 (close 272.255). Adapter prefers in-array prior day
    # over meta.chartPreviousClose, so prev_close = closes[3] = 270.17.
    # pct = (272.255 - 270.17) / 270.17 * 100 ≈ +0.77%.
    assert item.title.startswith("AAPL ")
    assert "272.26" in item.title or "272.25" in item.title
    assert "(+0.77%)" in item.title
    assert item.raw_metadata["prev_close"] == "270.170013"
    assert item.summary is not None
    assert item.summary.startswith("O:")
    assert "C:" in item.summary
    assert "V:" in item.summary
    assert str(item.url) == "https://finance.yahoo.com/quote/AAPL"


async def test_raw_metadata_keys_present_and_strings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _override_tickers(monkeypatch, "AAPL")
    adapter = YFinancePriceAdapter()
    fixtures = {"AAPL": _AAPL_FIXTURE.read_bytes()}
    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)
    item = items[0]
    expected_keys = {
        "ticker",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "prev_close",
        "provenance",
    }
    assert set(item.raw_metadata) == expected_keys
    assert item.raw_metadata["provenance"] == "query2-snapshot"
    assert all(isinstance(v, str) for v in item.raw_metadata.values())


# ---------------------------------------------------------------------------
# Per-ticker isolation (intra-adapter R6 analogue)
# ---------------------------------------------------------------------------


async def test_invalid_ticker_isolated_from_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _override_tickers(monkeypatch, "AAPL,INVALID")
    adapter = YFinancePriceAdapter()
    fixtures = {
        "AAPL": _AAPL_FIXTURE.read_bytes(),
        "INVALID": _INVALID_FIXTURE.read_bytes(),
    }
    async with _mock_client(fixtures, status_per={"INVALID": 404}) as client:
        items = await adapter.fetch(client, _WINDOW)
    # Wait — INVALID at 404 means the retry helper raises *before* it
    # sees the body. That's a per-ticker terminal failure, not a body
    # parse. Either way: AAPL succeeds, INVALID drops, no exception.
    assert len(items) == 1
    assert items[0].raw_metadata["ticker"] == "AAPL"


async def test_yahoo_error_shape_drops_only_that_ticker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Yahoo sometimes returns 200 OK with a populated chart.error
    # (e.g., for the synthetic INVALID fixture shape). The adapter
    # must treat that as a terminal per-ticker failure.
    _override_tickers(monkeypatch, "AAPL,INVALID")
    adapter = YFinancePriceAdapter()
    fixtures = {
        "AAPL": _AAPL_FIXTURE.read_bytes(),
        "INVALID": _INVALID_FIXTURE.read_bytes(),
    }
    async with _mock_client(fixtures) as client:  # 200 OK by default
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    assert items[0].raw_metadata["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# Null-OHLC fall-through
# ---------------------------------------------------------------------------


def _build_synthetic_payload(
    *,
    timestamps: list[int],
    opens: list[Any],
    highs: list[Any],
    lows: list[Any],
    closes: list[Any],
    volumes: list[Any],
    chart_previous_close: float = 100.0,
) -> bytes:
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "currency": "USD",
                        "exchangeTimezoneName": "America/New_York",
                        "chartPreviousClose": chart_previous_close,
                    },
                    "timestamp": timestamps,
                    "indicators": {
                        "quote": [
                            {
                                "open": opens,
                                "high": highs,
                                "low": lows,
                                "close": closes,
                                "volume": volumes,
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }
    return json.dumps(payload).encode("utf-8")


async def test_null_latest_day_falls_through_to_prior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Day 0: complete; day 1: complete; day 2 (latest): all-null OHLC.
    # Adapter picks day 1 (the latest valid).
    body = _build_synthetic_payload(
        # 9:30 ET on three calendar days (epochs only need to be plausible)
        timestamps=[1759321800, 1759408200, 1759494600],
        opens=[100.0, 105.0, None],
        highs=[101.0, 106.0, None],
        lows=[99.0, 104.0, None],
        closes=[100.5, 105.5, None],
        volumes=[1_000_000, 1_100_000, None],
    )
    _override_tickers(monkeypatch, "TEST")
    adapter = YFinancePriceAdapter()
    async with _mock_client({"TEST": body}) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    item = items[0]
    assert item.raw_metadata["close"] == "105.500000"
    # prev close = day 0's close (100.5), pct = (105.5 - 100.5) / 100.5 * 100
    assert "+4.98%" in item.title


async def test_all_null_ohlc_drops_ticker(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _build_synthetic_payload(
        timestamps=[1759321800, 1759408200],
        opens=[None, None],
        highs=[None, None],
        lows=[None, None],
        closes=[None, None],
        volumes=[None, None],
    )
    _override_tickers(monkeypatch, "TEST")
    adapter = YFinancePriceAdapter()
    async with _mock_client({"TEST": body}) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert items == []


async def test_missing_prev_close_uses_chart_previous_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Only one valid day in the response. Pct must come from
    # meta.chartPreviousClose, not from a sibling closes[] entry.
    body = _build_synthetic_payload(
        timestamps=[1759321800],
        opens=[100.0],
        highs=[101.0],
        lows=[99.0],
        closes=[110.0],
        volumes=[1_000_000],
        chart_previous_close=100.0,
    )
    _override_tickers(monkeypatch, "TEST")
    adapter = YFinancePriceAdapter()
    async with _mock_client({"TEST": body}) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    # pct = (110 - 100) / 100 * 100 = +10%
    assert "+10.00%" in items[0].title
    assert items[0].raw_metadata["prev_close"] == "100.000000"


# ---------------------------------------------------------------------------
# R11 — DST-aware close timestamp
# ---------------------------------------------------------------------------


def _epoch_for_ny_session_start(year: int, month: int, day: int) -> int:
    """Return epoch seconds for 9:30 NY local on the given date."""
    ny = ZoneInfo("America/New_York")
    return int(datetime(year, month, day, 9, 30, tzinfo=ny).timestamp())


async def test_published_at_is_market_close_in_summer_edt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Tuesday 2026-07-14: deep in EDT (UTC-4). NY 16:00 = UTC 20:00.
    epoch = _epoch_for_ny_session_start(2026, 7, 14)
    body = _build_synthetic_payload(
        timestamps=[epoch],
        opens=[100.0],
        highs=[101.0],
        lows=[99.0],
        closes=[100.5],
        volumes=[1_000_000],
    )
    _override_tickers(monkeypatch, "TEST")
    adapter = YFinancePriceAdapter()
    async with _mock_client({"TEST": body}) as client:
        items = await adapter.fetch(client, _WINDOW)
    item = items[0]
    assert item.published_at == datetime(2026, 7, 14, 20, 0, tzinfo=UTC)


async def test_published_at_is_market_close_in_winter_est(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Wednesday 2026-01-14: deep in EST (UTC-5). NY 16:00 = UTC 21:00.
    epoch = _epoch_for_ny_session_start(2026, 1, 14)
    body = _build_synthetic_payload(
        timestamps=[epoch],
        opens=[100.0],
        highs=[101.0],
        lows=[99.0],
        closes=[100.5],
        volumes=[1_000_000],
    )
    _override_tickers(monkeypatch, "TEST")
    adapter = YFinancePriceAdapter()
    async with _mock_client({"TEST": body}) as client:
        items = await adapter.fetch(client, _WINDOW)
    item = items[0]
    assert item.published_at == datetime(2026, 1, 14, 21, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# R12 — env-var override
# ---------------------------------------------------------------------------


async def test_env_override_uses_only_specified_tickers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Override to a subset; default 11-ticker list must NOT be fetched.
    _override_tickers(monkeypatch, "META,GOOGL")
    adapter = YFinancePriceAdapter()
    body = _build_synthetic_payload(
        timestamps=[1759321800],
        opens=[100.0],
        highs=[101.0],
        lows=[99.0],
        closes=[100.5],
        volumes=[1_000_000],
    )
    fixtures = {"META": body, "GOOGL": body}
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ticker = unquote(request.url.path.rsplit("/", 1)[-1])
        requested.append(ticker)
        body_bytes = fixtures.get(ticker)
        if body_bytes is None:
            return httpx.Response(404, json={"error": "missing"})
        return httpx.Response(200, content=body_bytes, headers={"content-type": "application/json"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert sorted(requested) == ["GOOGL", "META"]
    assert len(items) == 2
    assert {item.raw_metadata["ticker"] for item in items} == {"META", "GOOGL"}


async def test_env_unset_uses_default_tickers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INVESTO_YFINANCE_TICKERS", raising=False)
    adapter = YFinancePriceAdapter()
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ticker = unquote(request.url.path.rsplit("/", 1)[-1])
        requested.append(ticker)
        # Reuse INVALID body so all default tickers fail uniformly —
        # we only care about which tickers were requested.
        return httpx.Response(
            200,
            content=_INVALID_FIXTURE.read_bytes(),
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await adapter.fetch(client, _WINDOW)
    # All defaults attempted; all fail (Yahoo error shape) → no items.
    assert items == []
    assert set(requested) == {
        "^GSPC",
        "^IXIC",
        "^DJI",
        "^VIX",
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "NVDA",
        "META",
        "TSLA",
        # u53 — Stooq returns N/D for these; yfinance covers the gap.
        "BZ=F",
        "^RUT",
    }


async def test_enrichment_runs_after_critical_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_YFINANCE_TICKERS", "AAPL")
    monkeypatch.setenv("INVESTO_YFINANCE_ENRICHMENT_TICKERS", "XLK,XLE")
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(unquote(request.url.path.rsplit("/", 1)[-1]))
        return httpx.Response(200, content=_AAPL_FIXTURE.read_bytes())

    adapter = YFinancePriceAdapter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert requested[0] == "AAPL"
    assert requested[1:] == ["XLK", "XLE"]
    assert [item.raw_metadata["ticker"] for item in items] == ["AAPL", "XLK", "XLE"]


async def test_enrichment_is_skipped_when_critical_basket_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_YFINANCE_TICKERS", "INVALID")
    monkeypatch.setenv("INVESTO_YFINANCE_ENRICHMENT_TICKERS", "XLK")
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(unquote(request.url.path.rsplit("/", 1)[-1]))
        return httpx.Response(200, content=_INVALID_FIXTURE.read_bytes())

    adapter = YFinancePriceAdapter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert items == []
    assert requested == ["INVALID"]


async def test_enrichment_failures_preserve_critical_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_YFINANCE_TICKERS", "AAPL")
    monkeypatch.setenv("INVESTO_YFINANCE_ENRICHMENT_TICKERS", "XLK,XLE")
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ticker = unquote(request.url.path.rsplit("/", 1)[-1])
        requested.append(ticker)
        if ticker == "AAPL":
            return httpx.Response(200, content=_AAPL_FIXTURE.read_bytes())
        return httpx.Response(404, content=_INVALID_FIXTURE.read_bytes())

    adapter = YFinancePriceAdapter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert requested == ["AAPL", "XLK", "XLE"]
    assert [item.raw_metadata["ticker"] for item in items] == ["AAPL"]


async def test_blank_enrichment_override_uses_fixed_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_YFINANCE_TICKERS", "AAPL")
    monkeypatch.setenv("INVESTO_YFINANCE_ENRICHMENT_TICKERS", "")
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ticker = unquote(request.url.path.rsplit("/", 1)[-1])
        requested.append(ticker)
        body = _AAPL_FIXTURE.read_bytes() if ticker == "AAPL" else _INVALID_FIXTURE.read_bytes()
        return httpx.Response(200, content=body)

    adapter = YFinancePriceAdapter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert [item.raw_metadata["ticker"] for item in items] == ["AAPL"]
    assert requested[0] == "AAPL"
    assert set(requested[1:]) == set(adapter._DEFAULT_ENRICHMENT_TICKERS)


# ---------------------------------------------------------------------------
# u53 — Brent (BZ=F) and Russell 2000 (^RUT) coverage gap
# ---------------------------------------------------------------------------


_BZ_F_FIXTURE = _QUERY2_FIXTURE_DIR / "BZ_F.json"
_RUT_FIXTURE = _QUERY2_FIXTURE_DIR / "RUT.json"


async def test_brent_futures_round_trips_through_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _override_tickers(monkeypatch, "BZ=F")
    adapter = YFinancePriceAdapter()
    fixtures = {"BZ=F": _BZ_F_FIXTURE.read_bytes()}
    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    item = items[0]
    assert item.raw_metadata["ticker"] == "BZ=F"
    assert item.source_name == "yfinance-price"
    assert item.category == "price"
    assert item.published_at.tzinfo is UTC


async def test_russell_2000_round_trips_through_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _override_tickers(monkeypatch, "^RUT")
    adapter = YFinancePriceAdapter()
    fixtures = {"^RUT": _RUT_FIXTURE.read_bytes()}
    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    item = items[0]
    assert item.raw_metadata["ticker"] == "^RUT"
    # ^RUT volumes are 0 (index, like ^VIX); the adapter requires
    # volume to be non-null but allows 0 — fixture pins this.
    assert item.raw_metadata["volume"] == "0"


async def test_fetch_sends_browser_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    _override_tickers(monkeypatch, "AAPL")
    adapter = YFinancePriceAdapter()
    seen_headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers["user-agent"])
        assert request.url.host == "query2.finance.yahoo.com"
        assert request.url.params["interval"] == "1d"
        assert request.url.params["range"] == "1y"
        return httpx.Response(
            200,
            content=_AAPL_FIXTURE.read_bytes(),
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await adapter.fetch(client, _WINDOW)

    assert seen_headers == [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    ]


async def test_fetch_limits_default_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    _override_tickers(monkeypatch, "AAPL,MSFT,GOOGL,AMZN")
    monkeypatch.delenv("INVESTO_YFINANCE_CONCURRENCY", raising=False)
    adapter = YFinancePriceAdapter()
    active = 0
    max_active = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(
            200,
            content=_AAPL_FIXTURE.read_bytes(),
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert len(items) == 4
    assert max_active == 2


async def test_fetch_allows_concurrency_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _override_tickers(monkeypatch, "AAPL,MSFT,GOOGL")
    monkeypatch.setenv("INVESTO_YFINANCE_CONCURRENCY", "1")
    adapter = YFinancePriceAdapter()
    active = 0
    max_active = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(
            200,
            content=_AAPL_FIXTURE.read_bytes(),
            headers={"content-type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert len(items) == 3
    assert max_active == 1


# ---------------------------------------------------------------------------
# Class identity — adapter contract
# ---------------------------------------------------------------------------


def test_class_attributes() -> None:
    assert YFinancePriceAdapter.name == "yfinance-price"
    assert YFinancePriceAdapter.category == "price"


def test_default_phase_baskets_are_disjoint_and_bounded() -> None:
    critical = YFinancePriceAdapter._DEFAULT_TICKERS
    enrichment = YFinancePriceAdapter._DEFAULT_ENRICHMENT_TICKERS
    assert len(critical) == 13
    assert len(enrichment) == 14
    assert set(critical).isdisjoint(enrichment)
    assert len(critical) + len(enrichment) == 27


# ---------------------------------------------------------------------------
# u55 Step 1 — CoreFact stamp in raw_metadata
# ---------------------------------------------------------------------------


async def test_core_fact_stamp_for_index_ticker(monkeypatch: pytest.MonkeyPatch) -> None:
    """``^GSPC`` lands a ``core_fact:spx_close`` flat key."""
    _override_tickers(monkeypatch, "^GSPC")
    fixtures = {"^GSPC": _GSPC_FIXTURE.read_bytes()}
    adapter = YFinancePriceAdapter()
    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    item = items[0]
    assert "core_fact:spx_close" in item.raw_metadata
    assert item.raw_metadata["core_fact:spx_close"] == item.raw_metadata["close"]


async def test_core_fact_stamp_absent_for_non_core_ticker(monkeypatch: pytest.MonkeyPatch) -> None:
    """AAPL is an equity — no ``core_fact:*`` stamp registered."""
    _override_tickers(monkeypatch, "AAPL")
    fixtures = {"AAPL": _AAPL_FIXTURE.read_bytes()}
    adapter = YFinancePriceAdapter()
    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    assert not any(k.startswith("core_fact:") for k in items[0].raw_metadata)
