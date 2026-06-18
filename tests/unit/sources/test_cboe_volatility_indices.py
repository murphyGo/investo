"""Tests for ``investo.sources.cboe_volatility_indices``."""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx

from investo.sources._window import FetchWindow
from investo.sources.cboe_volatility_indices import CboeVolatilityIndicesAdapter

_WINDOW = FetchWindow.from_kst_date(date(2026, 6, 18))


def _mock_client(fixtures: dict[str, bytes]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        code = request.url.path.rsplit("/", 1)[-1].split("_", 1)[0]
        body = fixtures.get(code, b"DATE,VALUE\n")
        return httpx.Response(200, content=body, headers={"content-type": "text/csv"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_returns_vvix_and_skew_daily_closes_without_vix_duplication() -> None:
    adapter = CboeVolatilityIndicesAdapter()
    vvix = b"DATE,VVIX\n06/16/2026,92.110000\n06/17/2026,94.530000\n"
    skew = b"DATE,SKEW\n06/16/2026,141.800000\n06/17/2026,142.620000\n"

    async with _mock_client({"VVIX": vvix, "SKEW": skew}) as client:
        items = await adapter.fetch(client, _WINDOW)

    by_code = {item.raw_metadata["index_code"]: item for item in items}
    assert set(by_code) == {"VVIX", "SKEW"}
    assert "VIX" not in by_code
    vvix_item = by_code["VVIX"]
    assert vvix_item.source_name == "cboe-volatility-indices"
    assert vvix_item.category == "macro"
    assert vvix_item.published_at == datetime(2026, 6, 17, 20, 15, tzinfo=UTC)
    assert vvix_item.raw_metadata["value"] == "94.530000"
    assert vvix_item.raw_metadata["source_lag_days"] == "1"
    assert vvix_item.raw_metadata["delayed_data_label"] == "official Cboe daily close, not intraday"
    assert "not an intraday snapshot" in vvix_item.summary


async def test_future_only_csv_returns_no_items() -> None:
    adapter = CboeVolatilityIndicesAdapter()
    vvix = b"DATE,VVIX\n06/19/2026,95.000000\n"

    async with _mock_client({"VVIX": vvix}) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert items == []
