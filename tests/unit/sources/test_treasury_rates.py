"""Tests for ``investo.sources.treasury_rates``."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from investo.sources._window import FetchWindow
from investo.sources.treasury_rates import TreasuryRatesAdapter

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "treasury-rates"


def _mock_client(fixtures: dict[str, bytes]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        year = request.url.params.get("field_tdr_date_value", "")
        body = fixtures.get(
            year, b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"/>'
        )
        return httpx.Response(200, content=body, headers={"content-type": "application/xml"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_uses_latest_available_curve_on_or_before_target_date() -> None:
    adapter = TreasuryRatesAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with _mock_client({"2026": (_FIXTURE_DIR / "2026.xml").read_bytes()}) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    item = items[0]
    assert item.source_name == "treasury-rates"
    assert item.category == "macro"
    assert item.title == "UST curve 2026-05-07: 10Y 4.31%, 2Y10Y +0.43pp"
    assert item.summary == "3M:4.41% 2Y:3.88% 10Y:4.31% 30Y:4.86% 3M10Y:-0.10pp"
    assert item.published_at == datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    assert item.raw_metadata["spread_2y10y_pp"] == "0.430000"
    assert item.raw_metadata["source_date_lag_days"] == "1"


async def test_empty_year_returns_no_items() -> None:
    adapter = TreasuryRatesAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with _mock_client({}) as client:
        assert await adapter.fetch(client, window) == []


async def test_malformed_rate_row_is_dropped() -> None:
    malformed = b"""
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
          xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">
      <entry><content><m:properties>
        <d:NEW_DATE>2026-05-07T00:00:00</d:NEW_DATE>
        <d:BC_3MONTH>bad</d:BC_3MONTH>
        <d:BC_2YEAR>3.88</d:BC_2YEAR>
        <d:BC_10YEAR>4.31</d:BC_10YEAR>
        <d:BC_30YEAR>4.86</d:BC_30YEAR>
      </m:properties></content></entry>
    </feed>
    """
    adapter = TreasuryRatesAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with _mock_client({"2026": malformed}) as client:
        assert await adapter.fetch(client, window) == []
