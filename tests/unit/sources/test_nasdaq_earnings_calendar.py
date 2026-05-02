"""Tests for ``investo.sources.nasdaq_earnings_calendar``."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.nasdaq_earnings_calendar import NasdaqEarningsCalendarAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "nasdaq-earnings-calendar"
_CALENDAR_FIXTURE = _FIXTURE_DIR / "calendar.json"
_WINDOW = FetchWindow.from_kst_date(date(2026, 5, 4))
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
)


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


async def test_fetch_returns_earnings_items_from_fixture() -> None:
    adapter = NasdaqEarningsCalendarAdapter()
    async with _mock_client(_CALENDAR_FIXTURE.read_bytes()) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert len(items) == 2
    assert all(item.source_name == "nasdaq-earnings-calendar" for item in items)
    assert all(item.category == "earnings" for item in items)


async def test_fetch_maps_first_fixture_row() -> None:
    adapter = NasdaqEarningsCalendarAdapter()
    async with _mock_client(_CALENDAR_FIXTURE.read_bytes()) as client:
        items = await adapter.fetch(client, _WINDOW)

    item = items[0]
    assert item.title == "PLTR earnings — after-hours — EPS forecast $0.22"
    assert item.summary == (
        "Palantir Technologies Inc.; Fiscal quarter: Mar/2026; "
        "Market cap: $333,468,525,433; Estimates: 8; Last year EPS: $0.04"
    )
    assert str(item.url) == "https://www.nasdaq.com/market-activity/stocks/pltr/earnings"
    assert item.published_at == datetime(2026, 5, 4, tzinfo=UTC)
    assert item.raw_metadata == {
        "symbol": "PLTR",
        "company_name": "Palantir Technologies Inc.",
        "report_time": "after-hours",
        "fiscal_quarter_ending": "Mar/2026",
        "eps_forecast": "$0.22",
        "no_of_ests": "8",
        "market_cap": "$333,468,525,433",
        "last_year_eps": "$0.04",
        "last_year_report_date": "5/05/2025",
    }


async def test_empty_optional_values_are_omitted() -> None:
    adapter = NasdaqEarningsCalendarAdapter()
    async with _mock_client(_CALENDAR_FIXTURE.read_bytes()) as client:
        items = await adapter.fetch(client, _WINDOW)

    item = items[1]
    assert item.title == "L earnings — pre-market"
    assert "eps_forecast" not in item.raw_metadata
    assert "last_year_report_date" not in item.raw_metadata
    assert item.raw_metadata["last_year_eps"] == "$1.74"


async def test_request_uses_target_date_and_browser_headers() -> None:
    adapter = NasdaqEarningsCalendarAdapter()
    client, captured = _capturing_client(_CALENDAR_FIXTURE.read_bytes())

    async with client:
        await adapter.fetch(client, _WINDOW)

    assert len(captured) == 1
    request = captured[0]
    assert request.url.params["date"] == "2026-05-04"
    assert request.headers["user-agent"] == _USER_AGENT
    assert request.headers["origin"] == "https://www.nasdaq.com"
    assert request.headers["referer"] == "https://www.nasdaq.com/market-activity/earnings"


async def test_rows_none_returns_empty_list() -> None:
    body = json.dumps({"data": {"rows": None}, "status": {"rCode": 200}}).encode("utf-8")
    adapter = NasdaqEarningsCalendarAdapter()

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert items == []


async def test_missing_required_symbol_or_name_dropped() -> None:
    body = json.dumps(
        {
            "data": {
                "rows": [
                    {"symbol": "AAPL", "name": "Apple Inc.", "time": "time-not-supplied"},
                    {"symbol": "", "name": "No Symbol Inc.", "time": "time-not-supplied"},
                    {"symbol": "NONAME", "name": "", "time": "time-not-supplied"},
                ]
            },
            "status": {"rCode": 200},
        }
    ).encode("utf-8")
    adapter = NasdaqEarningsCalendarAdapter()

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert len(items) == 1
    assert items[0].raw_metadata["symbol"] == "AAPL"


async def test_html_is_stripped_from_text_fields() -> None:
    body = json.dumps(
        {
            "data": {
                "rows": [
                    {
                        "symbol": "<b>MSFT</b>",
                        "name": "<i>Microsoft</i> Corporation",
                        "time": "time-after-hours",
                        "epsForecast": "<b>$3.10</b>",
                    }
                ]
            },
            "status": {"rCode": 200},
        }
    ).encode("utf-8")
    adapter = NasdaqEarningsCalendarAdapter()

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert len(items) == 1
    assert items[0].title == "MSFT earnings — after-hours — EPS forecast $3.10"
    assert items[0].summary == "Microsoft Corporation"


async def test_summary_is_truncated_to_280_chars() -> None:
    body = json.dumps(
        {
            "data": {
                "rows": [
                    {
                        "symbol": "LONG",
                        "name": "X" * 400,
                        "time": "time-not-supplied",
                    }
                ]
            },
            "status": {"rCode": 200},
        }
    ).encode("utf-8")
    adapter = NasdaqEarningsCalendarAdapter()

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert len(items) == 1
    assert items[0].summary is not None
    assert len(items[0].summary) == 280


async def test_malformed_json_raises_terminal_error() -> None:
    adapter = NasdaqEarningsCalendarAdapter()

    async with _mock_client(b"{") as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _WINDOW)

    assert exc_info.value.transient is False
    assert "malformed JSON" in str(exc_info.value)


async def test_terminal_http_status_is_reported() -> None:
    adapter = NasdaqEarningsCalendarAdapter()

    async with _mock_client(b'{"data":{"rows":[]}}', status=404) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _WINDOW)

    assert exc_info.value.transient is False
    assert "status 404 (terminal)" in str(exc_info.value)


@pytest.mark.parametrize(
    "body, message",
    [
        ([], "expected object response"),
        ({"status": {"rCode": 500}, "data": {"rows": []}}, "unexpected status rCode"),
        ({"status": {"rCode": 200}}, "missing data object"),
        ({"status": {"rCode": 200}, "data": {"rows": {}}}, "expected data.rows list"),
    ],
)
async def test_bad_response_shapes_raise_terminal_error(body: object, message: str) -> None:
    adapter = NasdaqEarningsCalendarAdapter()

    async with _mock_client(json.dumps(body).encode("utf-8")) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _WINDOW)

    assert exc_info.value.transient is False
    assert message in str(exc_info.value)


def test_adapter_class_attributes() -> None:
    assert NasdaqEarningsCalendarAdapter.name == "nasdaq-earnings-calendar"
    assert NasdaqEarningsCalendarAdapter.category == "earnings"
    assert NasdaqEarningsCalendarAdapter._ENDPOINT == "https://api.nasdaq.com/api/calendar/earnings"
