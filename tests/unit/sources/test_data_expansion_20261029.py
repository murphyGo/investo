"""Synthetic replay, routing and failure tests for u43/u66 expansion."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import localcontext

import httpx
import pytest

from investo._internal.crypto_indicators import render_crypto_indicator_block
from investo._internal.source_specs import SOURCE_SPECS_BY_NAME
from investo.briefing.segments import LOOKAHEAD_AWARE_SOURCES
from investo.models.exchange_flows import ExchangeFlow
from investo.models.market_calendar import KRX_HOLIDAYS_2026, is_holiday
from investo.publisher.crypto_indicators import inject_crypto_indicator_block
from investo.sources import FetchWindow, SourceFetchError
from investo.sources.coinmetrics_exchange_flows import CoinMetricsExchangeFlowsAdapter
from investo.sources.krx_option_expiry import KrxOptionExpiryAdapter, _monthly_expiry

AS_OF = datetime(2026, 10, 28, 8, tzinfo=UTC)
WINDOW = replace(FetchWindow.from_kst_date(date(2026, 10, 28)), evidence_received_at=AS_OF)


def row(asset: str = "btc", day: str = "2026-10-27") -> dict[str, object]:
    return {
        "asset": asset,
        "time": f"{day}T00:00:00.000000000Z",
        "FlowInExNtv": "10.123456789012345678901234567890",
        "FlowOutExNtv": "11.123456789012345678901234567889",
        "FlowInExNtv-status": "flash",
        "FlowOutExNtv-status": "reviewed",
        "FlowInExNtv-status-time": "2026-10-28T01:00:00.000000000Z",
        "FlowOutExNtv-status-time": "2026-10-28T02:00:00.000000000Z",
    }


async def fetch(payload: object, *, window: FetchWindow = WINDOW):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    ) as client:
        return await CoinMetricsExchangeFlowsAdapter().fetch(client, window)


async def test_flow_request_boundaries_exact_subtraction_and_final_attribution():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "community-api.coinmetrics.io"
        params = request.url.params
        assert params["assets"] == "btc,eth"
        assert params["metrics"] == "FlowInExNtv,FlowOutExNtv"
        assert params["start_time"] == "2026-10-25"
        assert params["end_time"] == "2026-10-27"
        assert params["page_size"] == "6"
        assert "api_key" not in params
        return httpx.Response(200, json={"data": [row(), row("eth")]})

    with localcontext() as context:
        context.prec = 5
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            items = await CoinMetricsExchangeFlowsAdapter().fetch(client, WINDOW)
        assert len(items) == 2
        assert items[0].raw_metadata["netflow_native"] == "-0.999999999999999999999999999999"
    assert items[0].published_at == datetime(2026, 10, 28, 2, tzinfo=UTC)
    assert ExchangeFlow.from_metadata(items[0].raw_metadata).asset == "btc"
    block = render_crypto_indicator_block(items)
    assert "2026-10-27 UTC 일별" in block
    assert "유입 잠정 / 유출 검토됨" in block
    assert "CC BY-NC 4.0" in block
    assert "거래소 간 이체 제외" in block
    assert "24h 스냅샷" not in block
    document = "# 브리핑\n\n## ⓪-A 크립토 지표 (UTC 24h 스냅샷)\n\n가짜 수치\n\n## ① 요약\n본문\n"
    rendered = inject_crypto_indicator_block(document, block)
    assert "가짜 수치" not in rendered
    assert "CC BY-NC 4.0" in rendered
    assert "## ① 요약\n본문" in rendered
    assert inject_crypto_indicator_block(rendered, block) == rendered


@pytest.mark.parametrize(
    "key,value",
    [
        ("FlowInExNtv", None),
        ("FlowInExNtv", True),
        ("FlowInExNtv", 2.5),
        ("FlowInExNtv", "NaN"),
        ("FlowInExNtv", "Infinity"),
        ("FlowInExNtv", "-1"),
        ("FlowInExNtv", "1e1000000"),
        ("FlowInExNtv", "1" * 100),
        ("FlowInExNtv-status", "unknown"),
        ("FlowInExNtv-status", None),
        ("FlowInExNtv-status-time", "2026-10-29T01:00:00Z"),
        ("FlowInExNtv-status-time", "2026-10-27T01:00:00Z"),
        ("FlowInExNtv-status-time", "2026-10-28T01:00:00"),
        ("time", "2026-10-27T01:00:00Z"),
        ("time", "2026-10-28T00:00:00Z"),
        ("time", "2026-09-27T00:00:00Z"),
        ("asset", "doge"),
    ],
)
async def test_bad_pair_never_becomes_zero_or_confirmed(key, value):
    bad = row()
    bad[key] = value
    with pytest.raises(SourceFetchError, match="no valid"):
        await fetch({"data": [bad]})
    items = await fetch({"data": [bad, row("eth")]})
    assert len(items) == 1
    assert items[0].raw_metadata["asset"] == "eth"
    assert "| BTC 거래소 일별 순유입 | 수집 안 됨 |" in render_crypto_indicator_block(items)


async def test_conflicting_duplicates_are_excluded_and_identical_rows_deduplicated():
    changed = row()
    changed["FlowInExNtv"] = "999"
    with pytest.raises(SourceFetchError):
        await fetch({"data": [row(), changed]})
    assert len(await fetch({"data": [row(), row()]})) == 1


async def test_latest_observation_selected_per_asset_and_revised_label_preserved():
    revised = row()
    revised["FlowOutExNtv-status"] = "revised"
    items = await fetch({"data": [revised, row(day="2026-10-26"), row("eth")]})
    assert len(items) == 2
    assert items[0].raw_metadata["observation_date"] == "2026-10-27"
    assert "유출 수정됨" in render_crypto_indicator_block(items)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"data": None},
        {"data": [row()] * 7},
        {"data": [], "next_page_url": "https://evil.example/"},
    ],
)
async def test_schema_and_pagination_fail_closed(payload):
    with pytest.raises(SourceFetchError):
        await fetch(payload)


async def test_empty_is_normal_but_historical_replay_rejects_later_revision():
    assert await fetch({"data": []}) == []
    with pytest.raises(SourceFetchError):
        await fetch({"data": [row()]}, window=FetchWindow.from_kst_date(date(2026, 10, 27)))


@pytest.mark.parametrize("status", [403, 429, 500])
async def test_http_failures_use_source_contract(status, monkeypatch):
    async def no_sleep(_):
        pass

    monkeypatch.setattr("investo.sources._retry.asyncio.sleep", no_sleep)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceFetchError) as error:
            await CoinMetricsExchangeFlowsAdapter().fetch(client, WINDOW)
    assert error.value.transient is (status != 403)
    assert len(calls) == (1 if status == 403 else 3)


async def test_timeout_and_malformed_json_are_reported(monkeypatch):
    async def no_sleep(_):
        pass

    monkeypatch.setattr("investo.sources._retry.asyncio.sleep", no_sleep)

    def timeout(request):
        raise httpx.ReadTimeout("test", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(SourceFetchError):
            await CoinMetricsExchangeFlowsAdapter().fetch(client, WINDOW)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text="not JSON"))
    ) as client:
        with pytest.raises(SourceFetchError, match="malformed JSON"):
            await CoinMetricsExchangeFlowsAdapter().fetch(client, WINDOW)


async def test_tampered_derived_metadata_is_not_rendered():
    items = await fetch({"data": [row()]})
    item = items[0].model_copy(
        update={"raw_metadata": {**items[0].raw_metadata, "netflow_native": "999"}}
    )
    block = render_crypto_indicator_block([item])
    assert "| BTC 거래소 일별 순유입 | 수집 안 됨 |" in block
    assert "CC BY-NC" not in block


async def test_december_event_survives_partial_year_boundary():
    async with httpx.AsyncClient() as client:
        items = await KrxOptionExpiryAdapter().fetch(
            client, FetchWindow.from_kst_date(date(2026, 12, 8))
        )
    assert len(items) == 1
    assert items[0].scheduled_at == datetime(2026, 12, 10, 6, 20, tzinfo=UTC)


async def test_monthly_calendar_no_network_and_domestic_clock():
    def forbidden(request):
        raise AssertionError("calendar must not fetch")

    async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as client:
        items = await KrxOptionExpiryAdapter().fetch(client, WINDOW)
    assert len(items) == 1
    assert items[0].scheduled_at == datetime(2026, 11, 12, 6, 20, tzinfo=UTC)
    assert "규칙 기반 계산" in items[0].title
    assert items[0].raw_metadata["calendar_valid_through"] == "2026-12-31"
    assert items[0].published_at == WINDOW.start_utc


def test_all_2026_monthly_dates_and_annual_holiday_corrections():
    expected = [8, 12, 12, 9, 14, 11, 9, 13, 10, 8, 12, 10]
    for month, day in enumerate(expected, 1):
        assert _monthly_expiry(2026, month, KRX_HOLIDAYS_2026) == date(2026, month, day)
    assert is_holiday("domestic-equity", date(2026, 5, 1))
    assert is_holiday("domestic-equity", date(2026, 7, 17))


def test_holiday_adjustment_crosses_weekend_and_fails_boundedly():
    closed = frozenset(date(2026, 1, day) for day in (5, 6, 7, 8))
    assert _monthly_expiry(2026, 1, closed) == date(2026, 1, 2)
    closed = frozenset(date(2026, 2, day) for day in range(1, 13)) | frozenset(
        {date(2026, 1, 30), date(2026, 1, 31)}
    )
    with pytest.raises(ValueError):
        _monthly_expiry(2026, 2, closed)


@pytest.mark.parametrize("day", [date(2025, 11, 1), date(2027, 1, 1), date(2026, 12, 30)])
async def test_unknown_year_is_not_reported_as_empty_calendar(day):
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceFetchError, match="annual qualification"):
            await KrxOptionExpiryAdapter().fetch(client, FetchWindow.from_kst_date(day))


def test_new_sources_route_to_only_their_own_segments():
    for name, segment in [
        ("krx-option-expiry", "domestic-equity"),
        ("coinmetrics-exchange-flows", "crypto"),
    ]:
        spec = SOURCE_SPECS_BY_NAME[name]
        assert spec.item_segments == spec.outcome_segments == {segment}
        assert spec.market_window_segment == segment
        assert spec.default_enabled
    assert "krx-option-expiry" in LOOKAHEAD_AWARE_SOURCES
