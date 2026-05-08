"""Tests for ``investo.sources.us_economic_calendar``."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from investo.sources._window import FetchWindow
from investo.sources.us_economic_calendar import UsEconomicCalendarAdapter

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "us-economic-calendar"
_SCHEDULE_URL = "https://www.bea.gov/news/schedule"


def _mock_client(body: bytes) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == _SCHEDULE_URL
        return httpx.Response(200, content=body, headers={"content-type": "text/html"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_parses_upcoming_bea_schedule() -> None:
    adapter = UsEconomicCalendarAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with _mock_client((_FIXTURE_DIR / "bea-schedule.html").read_bytes()) as client:
        items = await adapter.fetch(client, window)

    assert [item.title for item in items] == [
        "BEA GDP (Second Estimate) and Corporate Profits, 1st Quarter 2026",
        "BEA Personal Income and Outlays, April 2026",
    ]
    assert items[0].source_name == "us-economic-calendar"
    assert items[0].category == "calendar"
    assert items[0].scheduled_at == datetime(2026, 5, 28, 12, 30, tzinfo=UTC)
    assert items[0].raw_metadata["agency"] == "BEA"
    assert items[0].raw_metadata["scheduled_date"] == "2026-05-28"


async def test_empty_or_unparseable_schedule_returns_no_items() -> None:
    adapter = UsEconomicCalendarAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with _mock_client(b"<html><body>No rows</body></html>") as client:
        assert await adapter.fetch(client, window) == []
