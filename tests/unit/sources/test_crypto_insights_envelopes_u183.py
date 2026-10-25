"""Existing recordings replayed; mutation/decimal/clock edge cases are synthetic."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.alternative_fng import AlternativeFearGreedAdapter
from investo.sources.bybit_derivatives import BybitDerivativesAdapter, _insight_bybit
from investo.sources.coingecko_global_market import CoinGeckoGlobalMarketAdapter, _insight_global
from investo.sources.defillama_market_structure import (
    DefiLlamaMarketStructureAdapter,
    _insight_sum,
    _ObservedPayload,
)
from investo.sources.okx_derivatives import OkxDerivativesAdapter, _insight_okx

BASE = Path(__file__).parent / "fixtures/api"
NOW = datetime(2026, 5, 23, 16, tzinfo=UTC)


def payload(source, name):
    return json.loads((BASE / source / name).read_bytes())


@pytest.mark.parametrize(
    "adapter",
    [
        CoinGeckoGlobalMarketAdapter(),
        AlternativeFearGreedAdapter(),
        DefiLlamaMarketStructureAdapter(),
        BybitDerivativesAdapter(),
        OkxDerivativesAdapter(),
    ],
)
async def test_opt_in_keeps_exact_legacy_bytes_requests_and_fallback(adapter):
    requests = []

    def respond(request):
        requests.append((request.method, request.url))
        route = {
            "api.coingecko.com": ("coingecko-global-market", "global.json"),
            "api.alternative.me": ("alternative-fng", "fng.json"),
            "api.llama.fi": ("defillama-market-structure", "chains.json"),
            "stablecoins.llama.fi": ("defillama-market-structure", "stablecoins.json"),
            "api.bybit.com": ("bybit-derivatives", "tickers.json"),
        }.get(request.url.host)
        if route is None:
            route = (
                "okx-derivatives",
                "funding-rate.json"
                if request.url.path.endswith("funding-rate")
                else "open-interest.json",
            )
        return httpx.Response(200, content=(BASE / route[0] / route[1]).read_bytes())

    window = FetchWindow.from_kst_date(NOW.date())
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        off = await adapter.fetch(client, window)
        before = tuple(requests)
        requests.clear()
        on = await adapter.fetch(client, replace(window, insights_enabled=True))
    assert [i.model_dump_json() for i in off] == [i.model_dump_json() for i in on]
    assert tuple(requests) == before
    assert all(i.insight_envelope is None for i in off)
    assert any(i.insight_envelope for i in on)
    rows = [r for i in on if i.insight_envelope for r in i.insight_envelope.metrics]
    if adapter.name == "defillama-market-structure":
        assert all(
            r.time.basis == "collection_window"
            and r.time.exact_at is None
            and r.time.source_updated_at is None
            for r in rows
        )
        assert all(r.time.window_end != window.end_utc for r in rows)
    if adapter.name == "coingecko-global-market":
        assert next(r for r in rows if r.metric_id == "market_cap_usd").value == Decimal(
            "2623499078661.475"
        )


async def test_bybit_failure_keeps_okx_fallback_requests_and_legacy_payload():
    requests = []

    def respond(request):
        requests.append((request.method, request.url))
        if request.url.host == "api.bybit.com":
            return httpx.Response(403)
        name = (
            "funding-rate.json"
            if request.url.path.endswith("funding-rate")
            else "open-interest.json"
        )
        return httpx.Response(200, content=(BASE / "okx-derivatives" / name).read_bytes())

    window = FetchWindow.from_kst_date(NOW.date())
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        a = await BybitDerivativesAdapter().fetch(client, window)
        first = tuple(requests)
        requests.clear()
        b = await BybitDerivativesAdapter().fetch(client, replace(window, insights_enabled=True))
    assert tuple(requests) == first and len(first) == 3
    assert [i.model_dump_json() for i in a] == [i.model_dump_json() for i in b]
    assert all(i.source_name == "okx-derivatives" for i in b)
    assert b[0].insight_envelope.source_name == "okx-derivatives"


def test_bybit_fraction_cycle_and_usd_value_preserve_original_tokens():
    result = _insight_bybit(payload("bybit-derivatives", "tickers.json"))
    by_id = {r.metric_id: r for r in result.metrics}
    assert by_id["btc_funding"].value == Decimal("0.00003545")
    assert (
        by_id["btc_funding"].time.applicable_end - by_id["btc_funding"].time.applicable_start
    ) == timedelta(hours=8)
    assert by_id["btc_oi_usd"].value == Decimal("4103494619.75")
    assert by_id["btc_oi_usd"].time.basis == "source_response"


@pytest.mark.parametrize(
    "field,value",
    [
        ("fundingIntervalHour", None),
        ("fundingIntervalHour", "bad"),
        ("fundingIntervalHour", True),
        ("nextFundingTime", "0"),
    ],
)
def test_bybit_missing_cycle_suppresses_only_funding(field, value):
    body = payload("bybit-derivatives", "tickers.json")
    body["result"]["list"][0][field] = value
    assert {r.metric_id for r in _insight_bybit(body).metrics} == {"btc_oi_usd"}


def test_wrong_contract_does_not_receive_btc_scope_and_missing_clock_is_not_window_end():
    body = payload("bybit-derivatives", "tickers.json")
    body["result"]["list"][0]["symbol"] = "ETHUSDT"
    assert _insight_bybit(body) is None
    body = payload("bybit-derivatives", "tickers.json")
    body.pop("time")
    rows = _insight_bybit(body).metrics
    assert len(rows) == 1 and rows[0].time.precision == "unknown"


def test_okx_current_rate_is_indicative_even_when_sett_state_says_settled():
    funding = payload("okx-derivatives", "funding-rate.json")
    oi = payload("okx-derivatives", "open-interest.json")
    result = _insight_okx(funding, oi)
    row = next(r for r in result.metrics if r.metric_id == "btc_funding")
    assert row.value == Decimal("-0.0000258648920016")
    assert "indicative" in row.definition_id
    assert row.value != Decimal(funding["data"][0]["settFundingRate"])
    assert next(r for r in result.metrics if r.metric_id == "btc_oi_usd").value == Decimal(
        "470195869.999999998"
    )


def test_okx_unknown_or_changed_cycle_does_not_assume_eight_hours():
    f = payload("okx-derivatives", "funding-rate.json")
    o = payload("okx-derivatives", "open-interest.json")
    f["data"][0].pop("prevFundingTime")
    assert {r.metric_id for r in _insight_okx(f, o).metrics} == {"btc_oi_usd"}
    f = payload("okx-derivatives", "funding-rate.json")
    f["data"][0]["nextFundingTime"] = str(int(f["data"][0]["nextFundingTime"]) + 3600000)
    assert {r.metric_id for r in _insight_okx(f, o).metrics} == {"btc_oi_usd"}
    o["data"][0].pop("oiUsd")
    assert _insight_okx(f, o) is None  # coin OI is never converted by an assumed price


def test_defi_sum_preserves_decimal_and_ignores_non_usd_pegs_with_real_collection_interval():
    body = {
        "peggedAssets": [
            {
                "id": "1",
                "symbol": "USD-A",
                "circulating": {"peggedUSD": "10.12345678901234567890123456789"},
            },
            {"id": "2", "symbol": "USD-B", "circulating": {"peggedUSD": "0.1"}},
            {"id": "3", "symbol": "EUR-A", "circulating": {"peggedEUR": "999"}},
        ]
    }
    observed = _ObservedPayload(None, body, NOW - timedelta(seconds=1), NOW)
    row = _insight_sum(observed, stable=True).metrics[0]
    assert row.value == Decimal("10.22345678901234567890123456789")
    assert row.time.source_updated_at is None and row.time.exact_at is None
    duplicate = {"peggedAssets": [body["peggedAssets"][0]] * 2}
    assert (
        _insight_sum(_ObservedPayload(None, duplicate, observed.start, observed.end), stable=True)
        is None
    )


def test_coingecko_missing_update_time_remains_unknown_and_bool_is_not_a_value():
    body = payload("coingecko-global-market", "global.json")
    body["data"].pop("updated_at")
    body["data"]["market_cap_percentage"]["btc"] = True
    rows = _insight_global(httpx.Response(200, json=body)).metrics
    assert len(rows) == 1 and rows[0].time.precision == "unknown"
    assert rows[0].time.exact_at is None
