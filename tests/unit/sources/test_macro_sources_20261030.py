"""Live-fixture replay and deliberately synthetic failure/clock boundaries."""

import gzip
import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from investo._internal.macro_reference import validated_macro_observations
from investo._internal.market_reference import source_market_reference
from investo._internal.source_specs import SOURCE_SPECS_BY_NAME
from investo.briefing.event_input import is_event_candidate_item
from investo.briefing.segments import SEGMENT_MACRO_ACTUAL_SOURCES, segment_items
from investo.models.macro_reference import MacroObservation
from investo.sources import FetchWindow, SourceFetchError, collect_sources
from investo.sources.nyfed_gscpi import NyfedGscpiAdapter
from investo.sources.ofr_financial_stress import OfrFinancialStressAdapter
from investo.sources.treasury_tga_balance import ACCOUNTS, TreasuryTgaBalanceAdapter

AS_OF = datetime(2026, 10, 30, 8, tzinfo=UTC)
WINDOW = replace(FetchWindow.from_kst_date(date(2026, 10, 30)), evidence_received_at=AS_OF)
ADAPTERS = (TreasuryTgaBalanceAdapter, NyfedGscpiAdapter, OfrFinancialStressAdapter)


def recorded(name):
    folder = Path(__file__).parent / "fixtures" / "api" / name
    body = gzip.decompress((folder / "body.gz").read_bytes())
    meta = json.loads((folder / "meta.json").read_text())
    assert hashlib.sha256(body).hexdigest() == meta["sha256"]
    assert len(body) == meta["bytes"]
    return body


async def fetch(adapter, payload=None, *, body=None, window=WINDOW):
    raw = body if body is not None else json.dumps(payload).encode()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=raw))
    ) as client:
        return await adapter().fetch(client, window)


def tga(day="2026-10-28", values=("1052530", "18463", "55361", "1015632")):
    return {
        "data": [
            {
                "record_date": day,
                "account_type": key,
                "open_today_bal": value,
                "close_today_bal": "null",
                "table_nbr": "I",
            }
            for key, value in zip(ACCOUNTS, values, strict=True)
        ],
        "meta": {
            "dataTypes": {"open_today_bal": "CURRENCY0"},
            "dataFormats": {"open_today_bal": "$1,000,000"},
        },
    }


def ofr(points=None):
    return {"OFRFSI": {"data": points if points is not None else [[1793059200000, -1.913]]}}


GSCPI = b"Date,Sep-26,Oct-26\n31-Aug-2026,1.05,1.20\n30-Sep-2026,,1.28\n"


@pytest.mark.parametrize("adapter", ADAPTERS)
async def test_live_fixture_source_clocks_units_routing_and_news_exclusion(adapter):
    items = await fetch(adapter, body=recorded(adapter.name))
    assert len(items) == 1
    item = items[0]
    (observation,) = validated_macro_observations(items)
    assert MacroObservation.from_metadata(item.raw_metadata) == observation
    assert observation.as_of == AS_OF
    assert observation.collected_at == item.published_at >= AS_OF
    assert "published_at" not in item.raw_metadata
    assert not is_event_candidate_item(item)
    assert item.raw_metadata["indicator"] == "macro_reference"
    assert adapter.name not in SEGMENT_MACRO_ACTUAL_SOURCES["us-equity"]
    spec = SOURCE_SPECS_BY_NAME[adapter.name]
    assert spec.item_segments == spec.outcome_segments == {"us-equity"}
    assert spec.market_window_segment == "us-equity" and spec.default_enabled
    routed = segment_items(items)
    assert item in routed.us_equity and item not in routed.crypto


async def test_tga_null_closing_field_is_not_zero_and_request_is_bounded():
    requests = []

    def handler(r):
        requests.append(r)
        return httpx.Response(200, json=tga())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        (item,) = await TreasuryTgaBalanceAdapter().fetch(client, WINDOW)
    assert len(requests) == 1
    assert dict(requests[0].url.params) == {
        "sort": "-record_date",
        "page[size]": "32",
        "filter": "record_date:lte:2026-10-29",
    }
    assert item.raw_metadata["value"] == "1015632"
    assert item.raw_metadata["unit"] == "백만 USD"


@pytest.mark.parametrize("value", [None, True, "null", "-1", "1.1", "01", "NaN", "1e6", "1" * 13])
async def test_tga_bad_latest_amount_never_falls_back(value):
    payload = tga(values=("1052530", "18463", "55361", value))
    payload["data"] += tga("2026-10-27")["data"]
    with pytest.raises(SourceFetchError):
        await fetch(TreasuryTgaBalanceAdapter, payload)


@pytest.mark.parametrize("damage", ["missing", "conflict", "unit", "table", "sum", "rowcap"])
async def test_tga_schema_identity_balance_and_duplicates(damage):
    payload = tga()
    if damage == "missing":
        payload["data"].pop()
    elif damage == "conflict":
        payload["data"].append({**payload["data"][0], "open_today_bal": "2"})
    elif damage == "unit":
        payload["meta"]["dataFormats"]["open_today_bal"] = "Dollars"
    elif damage == "table":
        payload["data"][0]["table_nbr"] = "II"
    elif damage == "sum":
        payload["data"][0]["open_today_bal"] = "1"
    else:
        payload["data"] *= 9
    with pytest.raises(SourceFetchError):
        await fetch(TreasuryTgaBalanceAdapter, payload)


async def test_tga_stale_empty_future_and_zero():
    assert await fetch(TreasuryTgaBalanceAdapter, tga("2026-10-10")) == []
    assert await fetch(TreasuryTgaBalanceAdapter, {**tga(), "data": []}) == []
    assert await fetch(TreasuryTgaBalanceAdapter, tga("2026-10-30")) == []
    (item,) = await fetch(TreasuryTgaBalanceAdapter, tga(values=("0", "0", "0", "0")))
    assert item.raw_metadata["value"] == "0"


async def test_gscpi_uses_newest_vintage_even_when_headers_unordered():
    body = b"Date,Oct-26,Sep-26\n31-Aug-2026,1.20,1.05\n30-Sep-2026,1.28,\n"
    (item,) = await fetch(NyfedGscpiAdapter, body=body)
    assert item.raw_metadata["value"] == "1.28"
    assert item.raw_metadata["observation_date"] == "2026-09-30"
    assert item.raw_metadata["release_vintage"] == "2026-10"
    old = replace(WINDOW, evidence_received_at=datetime(2026, 9, 30, tzinfo=UTC))
    assert await fetch(NyfedGscpiAdapter, body=body, window=old) == []


@pytest.mark.parametrize(
    "body",
    [
        b"Date,Oct-26,Oct-26\n30-Sep-2026,1,1\n",
        b"Date,Oct-26\n30-Sep-2026,1\n30-Sep-2026,2\n",
        b"Date,Oct-26\n31-Aug-2026,1\n30-Sep-2026,NaN\n",
        b"Date,Oct-26\n29-Sep-2026,1\n",
        b"Date,Oct-26\n31-Oct-2026,1\n",
        b"Date,Oct-26\n30-Sep-2026,1,2\n",
        b"Date,Bad-26\n30-Sep-2026,1\n",
        b"Date,Oct-26\n30-Sep-2026,101\n",
        b"Date,Oct-26\n" + b"30-Sep-2026,1\n" * 601,
        b"\xff",
        b"",
    ],
)
async def test_gscpi_corrupt_dates_headers_values_and_bounds_fail_closed(body):
    with pytest.raises(SourceFetchError):
        await fetch(NyfedGscpiAdapter, body=body)


async def test_gscpi_missing_or_stale_not_zero():
    assert await fetch(NyfedGscpiAdapter, body=b"Date,Oct-26\n30-Sep-2026,\n") == []
    assert await fetch(NyfedGscpiAdapter, body=b"Date,Oct-26\n31-Jul-2026,1\n") == []
    (item,) = await fetch(NyfedGscpiAdapter, body=b"Date,Oct-26\n30-Sep-2026,0\n")
    assert item.raw_metadata["value"] == "0"


@pytest.mark.parametrize(
    "point",
    [
        [1793059200000, None],
        [1793059200000, True],
        [1793059200000, "1"],
        [1793059200000, float("nan")],
        [1793059200000, float("inf")],
        [1793059200000, 101],
        [True, 1],
        [1793059200001, 1],
        [1793059200000.0, 1],
        [1793059260000, 1],
        [10**30, 1],
        [0],
    ],
)
async def test_ofr_invalid_aggregate_values_and_date_labels(point):
    with pytest.raises(SourceFetchError):
        await fetch(OfrFinancialStressAdapter, ofr([point]))


async def test_ofr_conflicts_stale_empty_future_and_only_aggregate():
    with pytest.raises(SourceFetchError):
        await fetch(OfrFinancialStressAdapter, ofr([[1793059200000, 1], [1793059200000, 2]]))
    assert await fetch(OfrFinancialStressAdapter, ofr([])) == []
    assert await fetch(OfrFinancialStressAdapter, ofr([[0, 1]])) == []
    assert await fetch(OfrFinancialStressAdapter, ofr([[1893456000000, 1]])) == []
    (item,) = await fetch(OfrFinancialStressAdapter, {**ofr(), "Credit": {"data": "invalid"}})
    assert item.raw_metadata["value"] == "-1.913"
    assert "Credit" not in str(item.raw_metadata)
    with pytest.raises(SourceFetchError):
        await fetch(OfrFinancialStressAdapter, ofr([[1793059200000, 1]] * 10001))


@pytest.mark.parametrize(
    "adapter,limit", [(ADAPTERS[0], 65536), (ADAPTERS[1], 524288), (ADAPTERS[2], 5242880)]
)
async def test_stream_size_limits(adapter, limit):
    with pytest.raises(SourceFetchError, match="cap"):
        await fetch(adapter, body=b" " * (limit + 1))


@pytest.mark.parametrize("adapter", ADAPTERS)
@pytest.mark.parametrize("status", [403, 429, 500])
async def test_transport_failure_is_bounded(adapter, status, monkeypatch):
    calls = []

    async def no_sleep(_):
        pass

    monkeypatch.setattr("investo.sources._retry.asyncio.sleep", no_sleep)

    def handler(r):
        calls.append(r)
        return httpx.Response(status)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        with pytest.raises(SourceFetchError) as error:
            await adapter().fetch(c, WINDOW)
    assert error.value.transient == (status != 403)
    assert len(calls) == (1 if status == 403 else 2)


async def test_cutoff_uses_new_york_calendar_and_normalizes_timezone():
    equivalent = AS_OF.astimezone(timezone(timedelta(hours=9)))
    (item,) = await fetch(
        TreasuryTgaBalanceAdapter, tga(), window=replace(WINDOW, evidence_received_at=equivalent)
    )
    assert item.raw_metadata["as_of"] == AS_OF.isoformat()
    # At 00:30 UTC on Oct30, NY is still Oct29; that day's cash is incomplete.
    old = replace(WINDOW, evidence_received_at=datetime(2026, 10, 30, 0, 30, tzinfo=UTC))
    assert await fetch(TreasuryTgaBalanceAdapter, tga("2026-10-29"), window=old) == []


async def test_metadata_identity_unit_conflicts_and_native_cutoff():
    (item,) = await fetch(TreasuryTgaBalanceAdapter, tga())
    for update in (
        {"source_name": "nyfed-gscpi"},
        {"url": "https://example.com"},
        {"category": "news"},
        {"published_at": AS_OF},
    ):
        assert not validated_macro_observations([item.model_copy(update=update)])
    for key, value in (("unit", "USD"), ("value", "NaN"), ("as_of", "2026-10-30T08:00:00")):
        altered = item.model_copy(update={"raw_metadata": {**item.raw_metadata, key: value}})
        assert not validated_macro_observations([altered])
    changed = item.model_copy(update={"raw_metadata": {**item.raw_metadata, "value": "1"}})
    assert not validated_macro_observations([item, changed])
    assert len(validated_macro_observations([item, item])) == 1
    for segment, instant in (
        ("crypto", AS_OF),
        ("us-equity", AS_OF + timedelta(days=2)),
        ("us-equity", AS_OF - timedelta(seconds=1)),
    ):
        panel = source_market_reference(
            [item], anchors=(), segment=segment, target_date=WINDOW.target_date, observed_at=instant
        )
        assert not panel.macro_observations


async def test_sibling_survives_aggregate_collection_failure(monkeypatch):
    def handler(request):
        if request.url.host == "api.fiscaldata.treasury.gov":
            return httpx.Response(403)
        return httpx.Response(200, content=GSCPI)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("investo.sources.aggregator.httpx.AsyncClient", lambda: client)
    monkeypatch.setattr(
        "investo.sources.aggregator.list_sources",
        lambda: [TreasuryTgaBalanceAdapter(), NyfedGscpiAdapter()],
    )
    result = await collect_sources(WINDOW.target_date, evidence_received_at=AS_OF)
    assert {item.source_name for item in result.items} == {"nyfed-gscpi"}
    assert {row.source_name: row.status for row in result.outcomes} == {
        "treasury-tga-balance": "failed",
        "nyfed-gscpi": "ok",
    }


async def test_gscpi_padding_is_allowed_but_partially_populated_missing_date_is_not():
    assert len(await fetch(NyfedGscpiAdapter, body=GSCPI + b",,\n")) == 1
    with pytest.raises(SourceFetchError):
        await fetch(NyfedGscpiAdapter, body=GSCPI + b",,1.5\n")


@pytest.mark.parametrize("adapter", [TreasuryTgaBalanceAdapter, OfrFinancialStressAdapter])
@pytest.mark.parametrize("body", [b"null", b"[]", b"{", b'{"data":[],"data":[]}'])
async def test_json_shape_or_duplicate_keys_raise_source_error(adapter, body):
    with pytest.raises(SourceFetchError):
        await fetch(adapter, body=body)


def test_optional_success_cannot_mask_required_macro_source_failure():
    from investo.briefing.segments import resolve_macro_actual_health
    from investo.models.coverage import SourceOutcome

    outcomes = [
        SourceOutcome(
            "bls-macro-actuals", "macro", "failed", failure_reason="unavailable", transient=False
        )
    ]
    outcomes.extend(
        SourceOutcome(adapter.name, "macro", "ok", item_count=1) for adapter in ADAPTERS
    )
    result = resolve_macro_actual_health(
        "us-equity", (), tuple(outcomes), macro_sensitive_claim_made=True
    )
    assert result.status == "failed"
