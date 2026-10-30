"""Bounded network counts and separately typed KRX weekly expiry contracts."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import localcontext

import httpx
import pytest

from investo._internal.crypto_indicators import render_crypto_indicator_block
from investo._internal.market_reference import (
    render_option_expiry_reference,
    source_market_reference,
)
from investo._internal.network_activity import (
    render_network_activity_reference,
    validated_network_activity,
)
from investo._internal.numeric_verify import verify_core_facts
from investo._internal.source_specs import SOURCE_SPECS_BY_NAME
from investo.models import NormalizedItem
from investo.models.network_activity import NetworkActivity
from investo.models.option_expiry import OptionExpiry, option_expiries
from investo.sources import FetchWindow, SourceFetchError
from investo.sources.coinmetrics_network_activity import CoinMetricsNetworkActivityAdapter
from investo.sources.krx_option_expiry import KrxOptionExpiryAdapter

AS_OF = datetime(2026, 10, 28, 8, tzinfo=UTC)
WINDOW = replace(FetchWindow.from_kst_date(date(2026, 10, 28)), evidence_received_at=AS_OF)


def activity_rows():
    return [
        {
            "asset": asset,
            "time": f"2026-10-{day:02}T00:00:00.000000000Z",
            "AdrActCnt": str(day * 100),
            "TxCnt": str(day * 200),
        }
        for asset in ("btc", "eth")
        for day in range(20, 28)
    ]


async def fetch(payload, *, window=WINDOW):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    ) as client:
        return await CoinMetricsNetworkActivityAdapter().fetch(client, window)


async def test_request_bounds_metrics_attribution_and_exact_mean():
    def handler(request):
        assert request.url.host == "community-api.coinmetrics.io"
        assert dict(request.url.params) == {
            "assets": "btc,eth",
            "metrics": "AdrActCnt,TxCnt",
            "frequency": "1d",
            "start_time": "2026-10-20",
            "end_time": "2026-10-27",
            "page_size": "16",
        }
        return httpx.Response(200, json={"data": activity_rows()})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await CoinMetricsNetworkActivityAdapter().fetch(client, WINDOW)
    assert len(items) == 4
    activities = validated_network_activity(items)
    with localcontext() as ctx:
        ctx.prec = 2
        assert activities[0].previous_mean == "2,300.0"
        assert replace(activities[0], previous_seven=("0",) * 7).previous_mean == "0.0"
    for activity in activities:
        assert NetworkActivity.from_metadata(activity.metadata()) == activity
        assert activity.as_of == AS_OF
        assert activity.collected_at >= AS_OF
    block = render_crypto_indicator_block(items)
    assert "2,700개 · 2026-10-27 UTC · 직전 7일 평균 2,300.0개" in block
    assert "5,400건" in block
    assert "검토 상태 미제공" in block and "ETH는 L1" in block
    assert "creativecommons.org/licenses/by-nc/4.0/" in block
    assert all("status" not in item.raw_metadata for item in items)
    spec = SOURCE_SPECS_BY_NAME["coinmetrics-network-activity"]
    assert spec.item_segments == spec.outcome_segments == {"crypto"}


@pytest.mark.parametrize("value", [None, True, 4, 4.2, "-1", "0.1", "01", "NaN", "1e6", "1" * 19])
async def test_bad_count_isolated_per_metric_and_never_invented_zero(value):
    row = {**activity_rows()[7], "AdrActCnt": value}
    items = await fetch({"data": [row]})
    assert len(items) == 1 and items[0].raw_metadata["metric"] == "TxCnt"
    assert "활성 주소 수 |" not in render_network_activity_reference(
        validated_network_activity(items)
    )


async def test_missing_nonconsecutive_or_conflicting_day_never_has_partial_mean():
    rows = activity_rows()[:8]
    rows[2]["AdrActCnt"] = None
    items = await fetch({"data": rows})
    activities = validated_network_activity(items)
    assert activities[0].previous_seven == ()
    assert activities[1].previous_mean == "4,600.0"
    assert "직전 7일 비교 자료 부족" in render_network_activity_reference(activities)
    conflict = {**rows[-1], "AdrActCnt": "1"}
    items = await fetch({"data": [rows[-1], conflict]})
    assert len(items) == 1 and items[0].raw_metadata["metric"] == "TxCnt"
    assert len(await fetch({"data": [rows[-1], rows[-1]]})) == 2


@pytest.mark.parametrize(
    "updates",
    [
        {"time": "2026-10-28T00:00:00Z"},
        {"time": "2026-10-27T00:00:00"},
        {"time": "2026-10-27T01:00:00Z"},
        {"time": "2026-10-20T00:00:00Z"},
        {"asset": "doge"},
        {"asset": []},
    ],
)
async def test_incomplete_stale_nonutc_and_unknown_rows_fail_closed(updates):
    with pytest.raises(SourceFetchError, match="no valid"):
        await fetch({"data": [{**activity_rows()[7], **updates}]})


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        [],
        {"data": None},
        {"data": activity_rows() + activity_rows()[:1]},
        {"data": [], "next_page_url": "https://example.com"},
    ],
)
async def test_unexpected_schema_pagination_and_size(payload):
    with pytest.raises(SourceFetchError):
        await fetch(payload)


async def test_empty_and_oversized_response():
    assert await fetch({"data": []}) == []
    with pytest.raises(SourceFetchError):
        await fetch({"data": [], "padding": "x" * 65536})


@pytest.mark.parametrize("status", [403, 429, 500])
async def test_http_failure_contract(status, monkeypatch):
    async def no_sleep(_):
        pass

    monkeypatch.setattr("investo.sources._retry.asyncio.sleep", no_sleep)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(status))
    ) as c:
        with pytest.raises(SourceFetchError) as error:
            await CoinMetricsNetworkActivityAdapter().fetch(c, WINDOW)
    assert error.value.transient == (status != 403)


async def test_only_exact_trusted_count_rows_bypass_usd_price_detection():
    items = await fetch({"data": activity_rows()})
    block = render_network_activity_reference(validated_network_activity(items))
    assert verify_core_facts(block, items).actions == {}
    price = NormalizedItem(
        source_name="prices",
        category="price",
        title="USD",
        published_at=AS_OF,
        raw_metadata={"core_fact:btc_usd": "65000", "core_fact:eth_usd": "2500"},
    )
    report = verify_core_facts(block + "\nBTC 65000 USD\nETH 2500 USD", [*items, price])
    assert set(report.verified) == {"btc_usd", "eth_usd"}
    assert verify_core_facts(block.replace("2,700개", "99999 USD"), [*items, price]).conflicts
    assert verify_core_facts(block + "\nBTC 99999 USD", [*items, price]).conflicts
    assert (
        validated_network_activity([items[0].model_copy(update={"source_name": "unknown"})]) == ()
    )
    invalid = items[0].model_copy(
        update={"raw_metadata": {**items[0].raw_metadata, "count": "NaN"}}
    )
    assert validated_network_activity([invalid]) == ()


async def test_native_reference_only_crypto_with_recent_target_cutoff():
    items = await fetch({"data": activity_rows()})

    def panel(segment="crypto", observed=AS_OF):
        return source_market_reference(
            items, anchors=(), segment=segment, target_date=WINDOW.target_date, observed_at=observed
        )

    assert len(panel().daily_network_activity) == 4
    assert not panel("domestic-equity").daily_network_activity
    assert not panel(observed=AS_OF + timedelta(days=2)).daily_network_activity
    assert not panel(observed=AS_OF - timedelta(seconds=1)).daily_network_activity


@pytest.mark.parametrize(
    "kind,nominal,expected",
    [
        ("monday_weekly", date(2026, 2, 16), date(2026, 2, 19)),
        ("monday_weekly", date(2026, 5, 25), date(2026, 5, 26)),
        ("monday_weekly", date(2026, 10, 5), date(2026, 10, 6)),
        ("thursday_weekly", date(2026, 9, 24), date(2026, 9, 23)),
        ("thursday_weekly", date(2026, 12, 31), date(2026, 12, 30)),
        ("monthly", date(2026, 11, 12), date(2026, 11, 12)),
    ],
)
def test_weekly_holiday_direction_kind_and_metadata(kind, nominal, expected):
    expiry = OptionExpiry(kind, nominal)
    assert expiry.day == expected
    assert expiry.scheduled_at.hour == 6 and expiry.scheduled_at.minute == 20
    assert OptionExpiry.from_metadata(expiry.metadata()) == expiry
    with pytest.raises(ValueError):
        OptionExpiry.from_metadata({**expiry.metadata(), "scheduled_date": "2026-01-01"})
    with pytest.raises(ValueError):
        OptionExpiry.from_metadata({**expiry.metadata(), "rule_version": "unknown"})


def test_monthly_second_thursday_excludes_weekly_and_unknown_year():
    with pytest.raises(ValueError):
        OptionExpiry("thursday_weekly", date(2026, 11, 12))
    with pytest.raises(ValueError):
        OptionExpiry("monthly", date(2026, 11, 5))
    with pytest.raises(ValueError):
        OptionExpiry("monday_weekly", date(2027, 1, 4))
    for offset in range(365):
        start = date(2026, 1, 1) + timedelta(days=offset)
        if start == date(2026, 12, 31):
            with pytest.raises(ValueError):
                option_expiries(start)
            continue
        expiries = option_expiries(start)
        assert all(start <= expiry.day < start + timedelta(days=30) for expiry in expiries)
        assert all(expiry.day.weekday() < 5 and expiry.day.year == 2026 for expiry in expiries)
        assert len(expiries) == len(set(expiries))
        assert all(
            not (e.kind == "thursday_weekly" and 8 <= e.nominal_day.day <= 14) for e in expiries
        )


async def test_domestic_panel_keeps_monthly_and_nearest_weekly_distinct():
    async with httpx.AsyncClient() as c:
        items = await KrxOptionExpiryAdapter().fetch(c, WINDOW)
    panel = source_market_reference(
        items,
        anchors=(),
        segment="domestic-equity",
        target_date=WINDOW.target_date,
        observed_at=AS_OF,
    )
    assert [(e.kind, e.day) for e in panel.calculated_option_expiries] == [
        ("thursday_weekly", date(2026, 10, 29)),
        ("monthly", date(2026, 11, 12)),
    ]
    block = render_option_expiry_reference(panel.calculated_option_expiries)
    assert "KOSPI 200 목요일 위클리" in block and "KOSPI 200 월물" in block
    assert "2026년 달력만 지원" in block
    tampered = items[0].model_copy(update={"scheduled_at": datetime(2026, 11, 1, tzinfo=UTC)})
    panel = source_market_reference(
        [tampered],
        anchors=(),
        segment="domestic-equity",
        target_date=WINDOW.target_date,
        observed_at=AS_OF,
    )
    assert panel.calculated_option_expiries == ()


def test_csat_clock_not_invented_until_exchange_notice_is_qualified():
    with pytest.raises(ValueError, match="special session"):
        OptionExpiry("thursday_weekly", date(2026, 11, 19))
    expiries = option_expiries(date(2026, 11, 19))
    assert all(e.day != date(2026, 11, 19) for e in expiries)
    assert any(e.day == date(2026, 11, 23) for e in expiries)


async def test_non_utc_cutoff_preserves_same_completed_utc_days():
    from zoneinfo import ZoneInfo

    window = replace(WINDOW, evidence_received_at=AS_OF.astimezone(ZoneInfo("Asia/Seoul")))
    items = await fetch({"data": activity_rows()}, window=window)
    assert len(items) == 4
    assert all(a.as_of == AS_OF for a in validated_network_activity(items))


async def test_activity_failure_does_not_drop_exchange_flows(monkeypatch):
    from investo.sources import aggregator
    from investo.sources.coinmetrics_exchange_flows import CoinMetricsExchangeFlowsAdapter
    from tests.unit.sources.test_data_expansion_20261029 import row

    adapters = [CoinMetricsNetworkActivityAdapter(), CoinMetricsExchangeFlowsAdapter()]
    monkeypatch.setattr(aggregator, "list_sources", lambda: adapters)
    monkeypatch.delenv("INVESTO_SOURCE_ENABLE", raising=False)
    monkeypatch.delenv("INVESTO_SOURCE_DISABLE", raising=False)
    original_client = httpx.AsyncClient

    def handler(request):
        if request.url.params["metrics"] == "AdrActCnt,TxCnt":
            return httpx.Response(403)
        return httpx.Response(200, json={"data": [row(), row("eth")]})

    monkeypatch.setattr(
        aggregator.httpx,
        "AsyncClient",
        lambda: original_client(transport=httpx.MockTransport(handler)),
    )
    report = await aggregator.collect_sources(WINDOW.target_date, evidence_received_at=AS_OF)
    assert len(report.items) == 2
    assert all(item.source_name == "coinmetrics-exchange-flows" for item in report.items)
    assert len(report.outcomes) == 2
    assert report.outcomes[0].status == "failed"
    assert report.outcomes[1].status == "ok"
