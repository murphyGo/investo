"""Yahoo public collector: exact requests, strict rows, bounded resources and task ownership."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from hypothesis import given
from hypothesis import strategies as st

from investo.models.market_calendar import is_trading_day
from investo.models.sector import SectorTicker
from investo.models.sector_public import (
    PUBLIC_REQUEST_TICKERS,
    PublicParsedSet,
    PublicSourceIssueCode,
)
from investo.sector_dashboard import yahoo_data as adapter
from investo.sector_dashboard.public_metrics import (
    build_public_series_bundle,
    compute_public_sector_snapshot,
)
from investo.sector_dashboard.public_render import render_public_sector_projection
from investo.sector_dashboard.yahoo_data import (
    YahooAdapterConfig,
    YahooRequestBudget,
    collect_public_bars,
    compute_yahoo_retry_delay,
)

_TARGET = date(2026, 10, 2)
_ZONE = ZoneInfo("America/New_York")


def _days(count: int = 100) -> list[date]:
    days = []
    cursor = _TARGET
    while len(days) < count:
        if is_trading_day("us-equity", cursor):
            days.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(days))


def _payload(ticker: str = "SPY", days: list[date] | None = None) -> dict[str, Any]:
    days = _days() if days is None else days
    prices = [100.0 + i for i in range(len(days))]
    return {
        "chart": {
            "error": None,
            "result": [
                {
                    "meta": {
                        "symbol": ticker,
                        "currency": "USD",
                        "instrumentType": "ETF",
                        "exchangeTimezoneName": "America/New_York",
                        "dataGranularity": "1d",
                    },
                    "timestamp": [
                        int(datetime.combine(day, datetime.min.time(), _ZONE).timestamp())
                        for day in days
                    ],
                    "indicators": {
                        "quote": [
                            {
                                "open": prices.copy(),
                                "high": [p + 1 for p in prices],
                                "low": [p - 1 for p in prices],
                                "close": prices.copy(),
                                "volume": [1000] * len(days),
                            }
                        ],
                        "adjclose": [{"adjclose": [1.0] * len(days)}],
                    },
                }
            ],
        }
    }


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=_payload(request.url.path.rsplit("/", 1)[1]))


async def _collect(handler: Any, **kwargs: Any) -> PublicParsedSet:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await collect_public_bars(client, target_date=_TARGET, **kwargs)


def _failure(result: PublicParsedSet) -> PublicSourceIssueCode:
    assert result.benchmark is None
    assert len(result.failures) == 12
    return result.failures[0].issue_code


@pytest.mark.asyncio
async def test_exact_twelve_requests_no_credentials_and_uses_quote_close() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.scheme == "https"
        assert request.url.host == "query2.finance.yahoo.com"
        assert request.url.path.startswith("/v8/finance/chart/")
        assert request.headers == httpx.Headers(
            {
                "Host": adapter.YAHOO_API_HOST,
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "User-Agent": adapter.YAHOO_USER_AGENT,
            }
        )
        params = request.url.params
        assert set(params) == {"interval", "includePrePost", "period1", "period2"}
        assert params["interval"] == "1d" and params["includePrePost"] == "false"
        assert datetime.fromtimestamp(int(params["period1"]), _ZONE).date() == _TARGET - timedelta(
            days=200
        )
        assert datetime.fromtimestamp(int(params["period2"]), _ZONE).date() == _TARGET + timedelta(
            days=1
        )
        response = _ok(request)
        response.headers["Set-Cookie"] = "ignored=session"
        return response

    budget = YahooRequestBudget()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={
            "Authorization": "Bearer ambient-secret",
            "X-API-Key": "ambient-key",
            "Cookie": "ambient-cookie",
            "X-Fallback": "unused",
        },
        auth=("ambient", "password"),
        follow_redirects=True,
    ) as client:
        result = await collect_public_bars(client, target_date=_TARGET, budget=budget)
        assert not client.cookies
    assert result.failures == ()
    assert budget.request_count == budget.successful_response_count == 12
    assert requests[0].url.path.endswith("/SPY")
    assert {r.url.path.rsplit("/", 1)[1] for r in requests} == {
        t.value for t in PUBLIC_REQUEST_TICKERS
    }
    assert result.benchmark is not None and len(result.benchmark.points) == 64
    assert result.benchmark.points[-1].close == 199
    assert SectorTicker.XLRE in result.sectors


@pytest.mark.asyncio
@pytest.mark.parametrize("config_kind", ["params", "cookies", "hooks", "budget"])
async def test_ambient_client_overrides_fail_before_network(config_kind: str) -> None:
    calls = []

    async def hook(_: httpx.Request) -> None:
        calls.append("hook")

    options: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    if config_kind == "params":
        options["params"] = {"interval": "1m"}
    elif config_kind == "cookies":
        options["cookies"] = {"session": "secret"}
    elif config_kind == "hooks":
        options["event_hooks"] = {"request": [hook]}
    else:
        extra = {"budget": YahooRequestBudget(YahooAdapterConfig(max_collection_requests=2))}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append("network")
        return _ok(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), **options) as client:
        result = await collect_public_bars(client, target_date=_TARGET, **extra)
    assert calls == []
    assert _failure(result) is PublicSourceIssueCode.AUTH_CONFIGURATION


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code", "attempts"),
    [
        (401, PublicSourceIssueCode.AUTH_REJECTED, 1),
        (403, PublicSourceIssueCode.AUTH_REJECTED, 1),
        (404, PublicSourceIssueCode.STATUS, 1),
        (302, PublicSourceIssueCode.STATUS, 1),
        (429, PublicSourceIssueCode.THROTTLE, 3),
        (503, PublicSourceIssueCode.STATUS, 3),
    ],
)
async def test_status_retry_and_redirect_contract(
    status: int, code: PublicSourceIssueCode, attempts: int
) -> None:
    calls = []
    sleeps = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            status,
            text="provider secret",
            headers={"Location": "https://unapproved.example/", "Retry-After": "999"},
        )

    result = await _collect(handler, sleep=sleep)
    assert len(calls) == attempts
    assert _failure(result) is code
    assert "provider secret" not in result.model_dump_json()
    assert sleeps == ([30.0, 30.0] if status == 429 else [1.0, 2.0] if status == 503 else [])


@pytest.mark.asyncio
async def test_retry_after_lower_cap_and_recovery() -> None:
    calls = 0
    sleeps = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "20"}) if calls == 1 else _ok(request)

    result = await _collect(handler, config=YahooAdapterConfig(max_retry_after_s=1.0), sleep=sleep)
    assert result.failures == () and calls == 13 and sleeps == [1.0]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["timeout", "exception"])
async def test_transport_errors_are_closed_and_retried(kind: str) -> None:
    calls = []

    async def sleep(_: float) -> None:
        pass

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if kind == "timeout":
            raise httpx.ReadTimeout("secret-transport-text")
        raise RuntimeError("secret-transport-text")

    result = await _collect(handler, sleep=sleep)
    assert len(calls) == 3
    assert _failure(result) is PublicSourceIssueCode.TRANSPORT
    assert "secret-transport-text" not in result.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        b"{",
        b'{"chart":{},"chart":{}}',
        b'{"chart":NaN}',
        b'{"chart":1e999}',
        b'"' + b"a" * 2049 + b'"',
        b"[" * 17 + b"0" + b"]" * 17,
        b'{"chart":{"error":{"description":"secret"},"result":[]}}',
    ],
)
async def test_malformed_json_fails_closed(body: bytes) -> None:
    result = await _collect(
        lambda _: httpx.Response(200, content=body, headers={"Content-Type": "application/json"})
    )
    assert _failure(result) is PublicSourceIssueCode.SCHEMA


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("symbol", "XLK"),
        ("currency", "CAD"),
        ("instrumentType", "INDEX"),
        ("dataGranularity", "1m"),
        ("exchangeTimezoneName", "Europe/London"),
    ],
)
async def test_metadata_identity_is_required(field: str, value: str) -> None:
    payload = _payload()
    payload["chart"]["result"][0]["meta"][field] = value
    result = await _collect(lambda _: httpx.Response(200, json=payload))
    assert _failure(result) is PublicSourceIssueCode.SCHEMA


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("null", PublicSourceIssueCode.ROW),
        ("zero", PublicSourceIssueCode.ROW),
        ("negative_volume", PublicSourceIssueCode.ROW),
        ("bool_volume", PublicSourceIssueCode.ROW),
        ("float_volume", PublicSourceIssueCode.ROW),
        ("bounds", PublicSourceIssueCode.ROW),
        ("duplicate", PublicSourceIssueCode.ROW),
        ("reversed", PublicSourceIssueCode.ROW),
        ("non_integer_stamp", PublicSourceIssueCode.ROW),
        ("length", PublicSourceIssueCode.SCHEMA),
        ("empty", PublicSourceIssueCode.INSUFFICIENT_HISTORY),
        ("future", PublicSourceIssueCode.CALENDAR),
        ("old", PublicSourceIssueCode.CALENDAR),
        ("weekend", PublicSourceIssueCode.CALENDAR),
        ("overflow", PublicSourceIssueCode.ROW),
    ],
)
async def test_bad_rows_are_rejected_before_retention(
    mutation: str, code: PublicSourceIssueCode
) -> None:
    payload = _payload()
    result = payload["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    if mutation == "null":
        quote["close"][0] = None
    elif mutation == "zero":
        quote["close"][0] = 0
    elif mutation == "negative_volume":
        quote["volume"][0] = -1
    elif mutation == "bool_volume":
        quote["volume"][0] = True
    elif mutation == "float_volume":
        quote["volume"][0] = 1.5
    elif mutation == "bounds":
        quote["high"][0] = 1
    elif mutation == "duplicate":
        result["timestamp"][1] = result["timestamp"][0]
    elif mutation == "reversed":
        result["timestamp"].reverse()
    elif mutation == "non_integer_stamp":
        result["timestamp"][0] = True
    elif mutation == "length":
        quote["close"].pop()
    elif mutation == "empty":
        result["timestamp"] = []
        for key in quote:
            quote[key] = []
    elif mutation == "overflow":
        result["timestamp"][0] = 10**100
    else:
        day = {
            "future": _TARGET + timedelta(days=3),
            "old": _TARGET - timedelta(days=201),
            "weekend": date(2026, 9, 26),
        }[mutation]
        result["timestamp"][0] = int(datetime.combine(day, datetime.min.time(), _ZONE).timestamp())
    parsed = await _collect(lambda _: httpx.Response(200, json=payload))
    assert _failure(parsed) is code


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["media", "length", "stream", "rows"])
async def test_response_envelope_limits(kind: str) -> None:
    config = YahooAdapterConfig(max_rows=2) if kind == "rows" else YahooAdapterConfig()
    if kind == "media":
        response = httpx.Response(200, text="{not-json}")
        expected = PublicSourceIssueCode.SCHEMA
    else:
        content = json.dumps(_payload()).encode()
        headers = {"Content-Type": "application/json"}
        if kind == "length":
            headers["Content-Length"] = str(1024 * 1024 + 1)
        if kind == "stream":
            content = b" " * (1024 * 1024 + 1)
        response = httpx.Response(200, content=content, headers=headers)
        expected = PublicSourceIssueCode.RESPONSE_SIZE
    assert _failure(await _collect(lambda _: response, config=config)) is expected


@pytest.mark.asyncio
@pytest.mark.parametrize("encoding", ["gzip", "deflate", "br", "identity, gzip"])
async def test_compressed_response_is_rejected_before_body_iteration(encoding: str) -> None:
    touched = []

    class ForbiddenBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            touched.append("read")
            raise AssertionError("compressed input must not enter the decoder")
            yield b""  # pragma: no cover

        async def aclose(self) -> None:
            touched.append("closed")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            stream=ForbiddenBody(),
            headers={"Content-Type": "application/json", "Content-Encoding": encoding},
        )

    assert _failure(await _collect(handler)) is PublicSourceIssueCode.SCHEMA
    assert touched == ["closed"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["none", "sleep", "child_cancel", "parent_cancel", "deadline"])
async def test_concurrency_and_owned_tasks_are_drained(failure: str) -> None:
    active = maximum = calls = 0
    sectors_started = asyncio.Event()

    async def sleep(_: float) -> None:
        raise RuntimeError("sleep failed")

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, maximum, calls
        calls += 1
        ticker = request.url.path.rsplit("/", 1)[1]
        if ticker == "XLB" and failure == "sleep":
            return httpx.Response(503)
        if ticker == "XLB" and failure == "child_cancel":
            raise asyncio.CancelledError
        active += 1
        maximum = max(maximum, active)
        try:
            if ticker != "SPY":
                sectors_started.set()
                await asyncio.sleep(0.1 if failure in {"parent_cancel", "deadline"} else 0.001)
            return _ok(request)
        finally:
            active -= 1

    config = (
        YahooAdapterConfig(collection_timeout_s=0.03)
        if failure == "deadline"
        else YahooAdapterConfig()
    )
    task = asyncio.create_task(_collect(handler, sleep=sleep, config=config))
    if failure == "parent_cancel":
        await sectors_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        result = await task
        assert len(result.failures) == (
            0 if failure == "none" else 11 if failure == "deadline" else 1
        )
    at_return = calls
    await asyncio.sleep(0.01)
    assert calls == at_return and active == 0 and maximum <= 2


@pytest.mark.asyncio
async def test_rolling_and_whole_collection_budgets() -> None:
    now = [0.0]
    sleeps = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)
        now[0] += delay

    config = YahooAdapterConfig(requests_per_minute=2, max_collection_requests=3)
    budget = YahooRequestBudget(config, clock=lambda: now[0], sleep=sleep)
    for _ in range(3):
        await budget.acquire()
    assert sleeps == [60.0]
    with pytest.raises(adapter._AdapterError) as error:
        await budget.acquire()
    assert error.value.issue_code is PublicSourceIssueCode.THROTTLE
    assert budget.request_count == 3


@given(attempt=st.integers(-10, 10), retry_after=st.one_of(st.none(), st.text(max_size=16)))
def test_retry_delay_is_bounded(attempt: int, retry_after: str | None) -> None:
    assert 0.0 <= compute_yahoo_retry_delay(attempt, retry_after) <= 30.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"json_response_limit": 1024 * 1024 + 1},
        {"max_rows": 257},
        {"requests_per_minute": 37},
        {"max_collection_requests": 37},
        {"concurrency": 3},
        {"retries": 3},
        {"connect_timeout_s": 5.1},
        {"read_timeout_s": 10.1},
        {"request_timeout_s": 15.1},
        {"collection_timeout_s": 120.1},
        {"max_retry_after_s": float("nan")},
        {"read_timeout_s": float("inf")},
        {"retry_backoffs": (float("nan"), 2.0)},
    ],
)
def test_config_cannot_raise_resource_ceilings(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        YahooAdapterConfig(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_rows": True},
        {"json_response_limit": 1.0},
        {"retries": False},
        {"connect_timeout_s": 1},
        {"retry_backoffs": [1.0, 2.0]},
        {"retry_backoffs": (1, 2)},
        {"max_retry_after_s": 1},
    ],
)
def test_config_rejects_wrong_runtime_types(kwargs: dict[str, Any]) -> None:
    with pytest.raises(TypeError):
        YahooAdapterConfig(**kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario", ["complete", "warming", "stale", "newer_sector", "gap", "zero", "one"]
)
async def test_retained_input_preserves_full_history_projection(scenario: str) -> None:
    benchmark_days = _days()
    sector_days = benchmark_days.copy()
    if scenario == "warming":
        benchmark_days = sector_days = benchmark_days[-32:]
    elif scenario == "stale":
        benchmark_days = sector_days = benchmark_days[:-1]
    elif scenario == "newer_sector":
        benchmark_days = benchmark_days[:-1]
    elif scenario == "gap":
        sector_days.remove(benchmark_days[-30])
    elif scenario in {"zero", "one"}:
        sector_days = benchmark_days[:2]
        if scenario == "one":
            sector_days.append(benchmark_days[-1])
    bodies = {
        t: json.dumps(
            _payload(t.value, benchmark_days if t is SectorTicker.SPY else sector_days)
        ).encode()
        for t in PUBLIC_REQUEST_TICKERS
    }
    full = {
        t: adapter._decode_public_json(body, t, _TARGET, adapter.DEFAULT_YAHOO_ADAPTER_CONFIG)
        for t, body in bodies.items()
    }
    expected = PublicParsedSet(
        benchmark=full[SectorTicker.SPY],
        sectors={t: bars for t, bars in full.items() if t is not SectorTicker.SPY},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=bodies[SectorTicker(request.url.path.rsplit("/", 1)[1])],
            headers={"Content-Type": "application/json"},
        )

    retained = await _collect(handler)
    assert retained.benchmark is not None and len(retained.benchmark.points) <= 64
    for ticker, series in retained.sectors.items():
        assert len(series.points) <= 66 and series.latest_date == full[ticker].latest_date
    original_snapshot = compute_public_sector_snapshot(
        build_public_series_bundle(expected, target_date=_TARGET)
    )
    retained_snapshot = compute_public_sector_snapshot(
        build_public_series_bundle(retained, target_date=_TARGET)
    )
    assert render_public_sector_projection(original_snapshot) == render_public_sector_projection(
        retained_snapshot
    )
