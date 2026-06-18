"""Tests for ``investo.sources.nyfed_reference_rates``."""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx

from investo.sources._window import FetchWindow
from investo.sources.nyfed_reference_rates import NyfedReferenceRatesAdapter

_WINDOW = FetchWindow.from_kst_date(date(2026, 6, 17))


def _mock_client(fixtures: dict[str, bytes]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        code = request.url.path.rstrip("/").split("/")[-3]
        body = fixtures.get(code, b'{"refRates":[]}')
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_returns_official_reference_rates() -> None:
    adapter = NyfedReferenceRatesAdapter()
    sofr = (
        b'{"refRates":[{"effectiveDate":"2026-06-16","type":"SOFR","percentRate":3.63,'
        b'"percentPercentile1":3.60,"percentPercentile25":3.61,"percentPercentile75":3.69,'
        b'"percentPercentile99":3.72,"volumeInBillions":3137,"revisionIndicator":""}]}'
    )
    effr = (
        b'{"refRates":[{"effectiveDate":"2026-06-16","type":"EFFR","percentRate":3.63,'
        b'"targetRateFrom":3.50,"targetRateTo":3.75,"volumeInBillions":106}]}'
    )

    async with _mock_client({"sofr": sofr, "effr": effr}) as client:
        items = await adapter.fetch(client, _WINDOW)

    by_code = {item.raw_metadata["rate_code"]: item for item in items}
    assert set(by_code) == {"SOFR", "EFFR"}
    sofr_item = by_code["SOFR"]
    assert sofr_item.source_name == "nyfed-reference-rates"
    assert sofr_item.category == "macro"
    assert sofr_item.published_at == datetime(2026, 6, 16, 12, 0, tzinfo=UTC)
    assert sofr_item.raw_metadata["percent_rate"] == "3.630000"
    assert sofr_item.raw_metadata["volume_billions_usd"] == "3137.000000"
    assert sofr_item.raw_metadata["percentile_99"] == "3.720000"
    assert sofr_item.raw_metadata["source_lag_days"] == "1"
    assert "published after the effective date" in sofr_item.raw_metadata["delayed_data_label"]
    assert by_code["EFFR"].raw_metadata["target_rate_from"] == "3.500000"


async def test_malformed_rate_payload_is_isolated() -> None:
    adapter = NyfedReferenceRatesAdapter()

    async with _mock_client({"sofr": b"{bad"}) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert items == []
