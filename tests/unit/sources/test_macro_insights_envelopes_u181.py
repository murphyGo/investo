"""Synthetic adapter parity and original-token mapping, no live recording claim."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.bls_macro_actuals import BlsMacroActualsAdapter
from investo.sources.fred_fx_close import FredFxCloseAdapter
from investo.sources.nyfed_reference_rates import NyfedReferenceRatesAdapter
from investo.sources.treasury_rates import TreasuryRatesAdapter


@pytest.mark.parametrize(
    ("adapter_type", "count"),
    [
        (TreasuryRatesAdapter, 6),
        (NyfedReferenceRatesAdapter, 2),
        (BlsMacroActualsAdapter, 3),
        (FredFxCloseAdapter, 1),
    ],
)
async def test_opt_in_preserves_requests_and_legacy_bytes(adapter_type, count, monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "synthetic-fixture-key")
    calls = []

    def handler(request):
        calls.append((request.method, str(request.url)))
        path = request.url.path
        if path.endswith("/xml"):
            body = (Path(__file__).parent / "fixtures/api/treasury-rates/2026.xml").read_bytes()
            return httpx.Response(200, content=body)
        if "/api/rates/" in path:
            return httpx.Response(
                200,
                content=b'{"refRates":[{"effectiveDate":"2026-05-07","percentRate":4.1250001234567890123,"volumeInBillions":800}]}',
            )
        if "/timeseries/data/" in path:
            series = path.rsplit("/", 1)[1]
            return httpx.Response(
                200,
                json={
                    "status": "REQUEST_SUCCEEDED",
                    "Results": {
                        "series": [
                            {
                                "seriesID": series,
                                "data": [
                                    {
                                        "year": "2026",
                                        "period": "M04",
                                        "value": "4.20" if series == "LNS14000000" else "300.125",
                                    }
                                ],
                            }
                        ]
                    },
                },
            )
        return httpx.Response(
            200, json={"observations": [{"date": "2026-05-07", "value": "1390.123456789012345"}]}
        )

    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        before = await adapter_type().fetch(client, window)
        request_count = len(calls)
        before_calls = tuple(calls)
        after = await adapter_type().fetch(client, replace(window, insights_enabled=True))
    assert tuple(calls[request_count:]) == before_calls
    assert [r.model_dump(mode="json") for r in before] == [r.model_dump(mode="json") for r in after]
    assert all(r.insight_envelope is None for r in before)
    metrics = [m for item in after if item.insight_envelope for m in item.insight_envelope.metrics]
    assert len(metrics) == count
    if adapter_type is NyfedReferenceRatesAdapter:
        assert metrics[0].value == Decimal("4.1250001234567890123")
    assert all(m.time.exact_at is None for m in metrics)
    assert all("?" not in m.source_href and "?" not in m.endpoint for m in metrics)
    assert "synthetic-fixture-key" not in str([r.model_dump() for r in after])


def test_treasury_decimal_spread_preserves_all_supported_digits():
    from investo.sources.treasury_rates import _insight_envelope

    envelope = _insight_envelope(
        {
            "NEW_DATE": "2026-05-07",
            "BC_3MONTH": "4.50",
            "BC_2YEAR": "4.10",
            "BC_10YEAR": "4.12345678901234567890123456789123456789",
            "BC_30YEAR": "4.80",
        }
    )
    rows = {r.metric_id: r for r in envelope.metrics}
    assert rows["ust_10y_2y_bp"].value == Decimal("2.34567890123456789012345678912345678900")


def test_treasury_derived_overflow_does_not_remove_valid_base_observations():
    from investo.sources.treasury_rates import _insight_envelope

    envelope = _insight_envelope(
        {
            "NEW_DATE": "2026-05-07",
            "BC_3MONTH": "4.50",
            "BC_2YEAR": "4.10",
            "BC_10YEAR": "1e64",
            "BC_30YEAR": "4.80",
        }
    )
    ids = {r.metric_id for r in envelope.metrics}
    assert "ust_2y" in ids and "ust_10y_2y_bp" not in ids
