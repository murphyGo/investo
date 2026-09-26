"""TS-3/TS-4 tests for the bounded u145 HF Data Library adapter."""

from __future__ import annotations

import asyncio
import io
import json
import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

import httpx
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
from hypothesis import given
from hypothesis import strategies as st

from investo.models.sector import SectorTicker
from investo.models.sector_public import (
    PUBLIC_REQUEST_TICKERS,
    PublicBarSeries,
    PublicSourceIssueCode,
)
from investo.sector_dashboard.hf_data import (
    HF_API_HOST,
    HF_USER_AGENT,
    HFAdapterConfig,
    HFRequestBudget,
    collect_public_bars,
    compute_hf_retry_delay,
)

_API_KEY = "12345678-1234-1234-1234-123456789abc"
_TARGET_DATE = date(2026, 9, 1)


def _rows() -> list[dict[str, Any]]:
    return [
        {
            "datetime": datetime(2022, 3, 1),
            "Open": 90.0,
            "High": 91.0,
            "Low": 89.0,
            "Close": 90.5,
            "Volume": 100,
            "source": "pitrading",
        },
        {
            "datetime": datetime(2026, 8, 28),
            "Open": 100.0,
            "High": 102.0,
            "Low": 99.0,
            "Close": 101.0,
            "Volume": 1_000,
            "source": "iex",
        },
        {
            "datetime": datetime(2026, 8, 31),
            "Open": 101.0,
            "High": 104.0,
            "Low": 100.0,
            "Close": 103.0,
            "Volume": 1_200,
            "source": "iex",
        },
    ]


def _schema() -> Any:
    return pa.schema(
        [
            pa.field("datetime", pa.timestamp("ns")),
            pa.field("Open", pa.float64()),
            pa.field("High", pa.float64()),
            pa.field("Low", pa.float64()),
            pa.field("Close", pa.float64()),
            pa.field("Volume", pa.int64()),
            pa.field("source", pa.large_string()),
        ]
    )


def _parquet(
    rows: list[dict[str, Any]] | None = None,
    *,
    schema: Any | None = None,
) -> bytes:
    selected_rows = _rows() if rows is None else rows
    selected_schema = _schema() if schema is None else schema
    table = pa.Table.from_pylist(selected_rows, schema=selected_schema)
    output = io.BytesIO()
    pq.write_table(table, output, compression="NONE")
    return output.getvalue()


def _ticker_from_path(path: str) -> str:
    return path.rsplit("/", maxsplit=1)[-1]


def _token_response(ticker: str, *, signed_url: str | None = None) -> httpx.Response:
    url = signed_url or (
        f"https://{HF_API_HOST}/v1/download/{ticker}?signature=signed-{ticker.lower()}"
    )
    return httpx.Response(
        200,
        json={"url": url, "expires_at": "2026-09-01T00:10:00Z"},
    )


def _download_response(body: bytes | None = None) -> httpx.Response:
    return httpx.Response(
        200,
        content=_parquet() if body is None else body,
        headers={"Content-Type": "application/octet-stream"},
    )


def _benchmark_failure_code(result: Any) -> PublicSourceIssueCode:
    failure = next(failure for failure in result.failures if failure.ticker is SectorTicker.SPY)
    return failure.issue_code


def test_sector_reader_version_is_exactly_pinned() -> None:
    assert pa.__version__ == "25.0.1"


@pytest.mark.asyncio
async def test_clean_collection_is_benchmark_first_and_exactly_22_calls() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        ticker = _ticker_from_path(request.url.path)
        assert request.headers["User-Agent"] == HF_USER_AGENT
        assert request.headers["Accept-Encoding"] == "identity"
        if "/download-token/" in request.url.path:
            assert request.headers["X-API-Key"] == _API_KEY
            assert "authorization" not in request.headers
            assert "cookie" not in request.headers
            assert "x-fallback-provider" not in request.headers
            assert list(request.url.params.multi_items()) == [
                ("timeframe", "daily"),
                ("format", "parquet"),
                ("version", "clean"),
            ]
            response = _token_response(ticker)
            response.headers["Set-Cookie"] = "provider-session=must-not-persist"
            return response
        assert "/v1/download/" in request.url.path
        assert "x-api-key" not in request.headers
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        assert "x-fallback-provider" not in request.headers
        response = _download_response()
        response.headers["Set-Cookie"] = "provider-session=must-not-persist"
        return response

    transport = httpx.MockTransport(handler)
    budget = HFRequestBudget()
    async with httpx.AsyncClient(
        transport=transport,
        headers={
            "X-API-Key": "client-default-key-must-be-replaced",
            "Authorization": "Bearer client-default-must-be-removed",
            "Cookie": "session=client-default-must-be-removed",
            "X-Fallback-Provider": "client-default-must-be-removed",
        },
    ) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
            budget=budget,
        )
        assert not client.cookies

    assert isinstance(result.benchmark, PublicBarSeries)
    assert len(result.sectors) == 10
    assert result.failures == ()
    assert budget.request_count == 22
    assert len(requests) == 22
    assert requests[0].url.path.endswith("/download-token/SPY")
    assert requests[1].url.path.endswith("/download/SPY")
    assert all(point.source == "iex" for point in result.benchmark.points)
    assert len(result.benchmark.points) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "environ",
    [
        {},
        {"HF_DATA_API_KEY": ""},
        {"HF_DATA_API_KEY": " "},
        {"HF_DATA_API_KEY": "placeholder"},
        {"HF_DATA_API_KEY": "your-api-key"},
        {"HF_DATA_API_KEY": "line\nbreak"},
        {"HF_DATA_API_KEY": "zero\u200bwidth"},
        {"HF_DATA_API_KEY": "x" * 513},
    ],
)
async def test_invalid_key_fails_before_network(environ: dict[str, str]) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise AssertionError("network must not be reached")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ=environ,
            target_date=_TARGET_DATE,
        )

    assert calls == 0
    assert len(result.failures) == len(PUBLIC_REQUEST_TICKERS)
    assert {failure.issue_code for failure in result.failures} == {
        PublicSourceIssueCode.AUTH_CONFIGURATION
    }


@pytest.mark.asyncio
async def test_observing_client_hooks_are_rejected_before_network() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    async def request_hook(_: httpx.Request) -> None:
        raise AssertionError("hook must not observe signed request material")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        event_hooks={"request": [request_hook]},
    ) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
        )

    assert calls == 0
    assert _benchmark_failure_code(result) is PublicSourceIssueCode.AUTH_CONFIGURATION


@pytest.mark.asyncio
async def test_default_client_params_are_rejected_before_network_and_logging(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = 0
    sentinel = "runtime-query-override-sentinel"

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise AssertionError("network must not be reached")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        params={"fallback": sentinel},
    ) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
        )

    assert calls == 0
    assert sentinel not in caplog.text
    assert _benchmark_failure_code(result) is PublicSourceIssueCode.AUTH_CONFIGURATION


@pytest.mark.asyncio
async def test_preexisting_client_cookie_jar_is_rejected_before_network() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise AssertionError("network must not be reached")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        cookies={"session": "preexisting-cookie"},
    ) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
        )

    assert calls == 0
    assert _benchmark_failure_code(result) is PublicSourceIssueCode.AUTH_CONFIGURATION


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "signed_url",
    [
        "http://api.hfdatalibrary.com/v1/download/SPY?signature=x",
        "https://evil.example/v1/download/SPY?signature=x",
        "https://api.hfdatalibrary.com:443/v1/download/SPY?signature=x",
        "https://api.hfdatalibrary.com/v1/download/XLB?signature=x",
        "https://api.hfdatalibrary.com/v1/download/SPY",
        "https://user@api.hfdatalibrary.com/v1/download/SPY?signature=x",
        "https://api.hfdatalibrary.com/v1/download/SPY?signature=x#fragment",
    ],
)
async def test_hostile_signed_url_fails_closed_without_download(signed_url: str) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _token_response("SPY", signed_url=signed_url)

    budget = HFRequestBudget()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
            budget=budget,
        )

    assert calls == 1
    assert budget.request_count == 1
    assert _benchmark_failure_code(result) is PublicSourceIssueCode.SCHEMA


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        b"not-json",
        b'{"url":"a","url":"b"}',
        json.dumps({"url": 1}).encode(),
        json.dumps(
            {
                "url": "https://api.hfdatalibrary.com/v1/download/SPY?signature=x",
                "expires_at": "x" * 257,
            }
        ).encode(),
        json.dumps(
            {
                "url": "https://api.hfdatalibrary.com/v1/download/SPY?signature=x",
                "unexpected": "field",
            }
        ).encode(),
    ],
)
async def test_malformed_token_json_is_nonretryable_schema(body: bytes) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"Content-Type": "application/json"})

    budget = HFRequestBudget()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
            budget=budget,
        )

    assert budget.request_count == 1
    assert _benchmark_failure_code(result) is PublicSourceIssueCode.SCHEMA


@pytest.mark.asyncio
async def test_token_response_stream_limit_is_enforced() -> None:
    body = b"{" + b"x" * 255 + b"}"
    config = HFAdapterConfig(token_response_limit=128)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"Content-Type": "application/json"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
            config=config,
        )

    assert _benchmark_failure_code(result) is PublicSourceIssueCode.RESPONSE_SIZE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected", "retryable"),
    [
        (400, PublicSourceIssueCode.STATUS, False),
        (401, PublicSourceIssueCode.AUTH_REJECTED, False),
        (403, PublicSourceIssueCode.AUTH_REJECTED, False),
        (404, PublicSourceIssueCode.STATUS, False),
        (302, PublicSourceIssueCode.STATUS, False),
    ],
)
async def test_nonretryable_status_contract(
    status: int,
    expected: PublicSourceIssueCode,
    retryable: bool,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            status,
            headers={"Location": "https://evil.example/redirect?secret=sentinel"},
        )

    budget = HFRequestBudget()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
            budget=budget,
        )

    benchmark_failure = next(
        failure for failure in result.failures if failure.ticker is SectorTicker.SPY
    )
    assert benchmark_failure.issue_code is expected
    assert benchmark_failure.retryable is retryable
    assert len(requests) == 1
    assert budget.request_count == 1


@pytest.mark.asyncio
async def test_429_retries_whole_unit_with_fresh_token_and_capped_retry_after() -> None:
    token_calls = 0
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls
        ticker = _ticker_from_path(request.url.path)
        if "/download-token/" in request.url.path:
            token_calls += 1
            if token_calls == 1:
                return httpx.Response(429, headers={"Retry-After": "999"})
            return _token_response(ticker)
        return _download_response()

    # Stop after SPY by making the first sector token fail without retry; the
    # benchmark assertions remain independent of the ten-sector fan-out.
    config = HFAdapterConfig(concurrency=1)
    budget = HFRequestBudget(config, sleep=fake_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
            config=config,
            budget=budget,
            sleep=fake_sleep,
        )

    assert result.benchmark is not None
    assert token_calls == 12
    assert budget.request_count == 23
    assert sleeps == [30.0]


@pytest.mark.asyncio
async def test_5xx_exhausts_two_retries_with_bounded_backoff() -> None:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    config = HFAdapterConfig()
    budget = HFRequestBudget(config, sleep=fake_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
            config=config,
            budget=budget,
            sleep=fake_sleep,
        )

    assert _benchmark_failure_code(result) is PublicSourceIssueCode.STATUS
    assert budget.request_count == 3
    assert sleeps == [1.0, 2.0]


@pytest.mark.asyncio
async def test_httpx_timeout_is_closed_and_retried() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"timeout with {_API_KEY}", request=request)

    budget = HFRequestBudget()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
            budget=budget,
            sleep=lambda _: asyncio.sleep(0),
        )

    assert _benchmark_failure_code(result) is PublicSourceIssueCode.TRANSPORT
    assert _API_KEY not in repr(result)
    assert budget.request_count == 3


@pytest.mark.asyncio
async def test_signed_download_redirect_is_not_followed_or_retried() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if "/download-token/" in request.url.path:
            return _token_response("SPY")
        return httpx.Response(
            302,
            headers={"Location": "https://evil.example/file?signature=redirect-sentinel"},
        )

    budget = HFRequestBudget()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
            budget=budget,
        )

    assert _benchmark_failure_code(result) is PublicSourceIssueCode.STATUS
    assert paths == ["/v1/download-token/SPY", "/v1/download/SPY"]
    assert budget.request_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("wrong_stage", ["token", "download"])
async def test_success_status_with_wrong_media_type_fails_schema(wrong_stage: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "/download-token/" in request.url.path:
            if wrong_stage == "token":
                return httpx.Response(
                    200,
                    content=b"{}",
                    headers={"Content-Type": "text/plain"},
                )
            return _token_response("SPY")
        return httpx.Response(
            200,
            content=_parquet(),
            headers={"Content-Type": "text/plain"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
        )

    assert _benchmark_failure_code(result) is PublicSourceIssueCode.SCHEMA


@pytest.mark.asyncio
async def test_transport_exception_cannot_expose_signed_url_or_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    signed_sentinel = "signed-url-secret-sentinel"
    signed_url = f"https://{HF_API_HOST}/v1/download/SPY?signature={signed_sentinel}"

    def handler(request: httpx.Request) -> httpx.Response:
        if "/download-token/" in request.url.path:
            return _token_response("SPY", signed_url=signed_url)
        raise RuntimeError(f"transport exploded at {request.url} with {_API_KEY}")

    budget = HFRequestBudget()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
            budget=budget,
            sleep=lambda _: asyncio.sleep(0),
        )

    assert _benchmark_failure_code(result) is PublicSourceIssueCode.TRANSPORT
    rendered = repr(result) + caplog.text
    assert signed_sentinel not in rendered
    assert _API_KEY not in rendered
    assert budget.request_count == 6


@pytest.mark.asyncio
async def test_httpx_and_httpcore_logs_redact_signed_url_and_key(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signed_sentinel = "signed-log-capability-sentinel"
    monkeypatch.setenv("HF_DATA_API_KEY", _API_KEY)
    caplog.set_level(logging.DEBUG)

    def handler(request: httpx.Request) -> httpx.Response:
        ticker = _ticker_from_path(request.url.path)
        if "/download-token/" in request.url.path:
            return _token_response(
                ticker,
                signed_url=(
                    f"https://{HF_API_HOST}/v1/download/{ticker}"
                    f"?signature=prefix){signed_sentinel}-{ticker.lower()}"
                ),
            )
        return _download_response()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
        )

    assert result.failures == ()
    rendered_records = "\n".join(record.getMessage() for record in caplog.records)
    assert signed_sentinel not in rendered_records
    assert signed_sentinel not in caplog.text
    assert _API_KEY not in rendered_records
    assert _API_KEY not in caplog.text
    assert "[REDACTED_HTTP_TRANSPORT_EVENT]" in rendered_records

    logging.getLogger("httpcore.http11").debug(
        "receive_response_headers.complete return_value=%r",
        (b"HTTP/1.1", 200, b"OK", [(b"x-provider", b"provider-header-sentinel")]),
    )
    rendered_after_header = "\n".join(record.getMessage() for record in caplog.records)
    assert "provider-header-sentinel" not in rendered_after_header
    assert "x-provider" not in rendered_after_header


def _body_with_rows(transform: Callable[[list[dict[str, Any]]], None]) -> bytes:
    rows = _rows()
    transform(rows)
    return _parquet(rows)


def _missing_column_body() -> bytes:
    schema = pa.schema([field for field in _schema() if field.name != "Volume"])
    rows = [{key: value for key, value in row.items() if key != "Volume"} for row in _rows()]
    return _parquet(rows, schema=schema)


def _extra_column_body() -> bytes:
    schema = _schema().append(pa.field("ticker", pa.string()))
    rows = [dict(row, ticker="SPY") for row in _rows()]
    return _parquet(rows, schema=schema)


def _wrong_type_body() -> bytes:
    fields = [
        pa.field("source", pa.string()) if field.name == "source" else field for field in _schema()
    ]
    return _parquet(schema=pa.schema(fields))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body_factory", "expected"),
    [
        (_missing_column_body, PublicSourceIssueCode.SCHEMA),
        (_extra_column_body, PublicSourceIssueCode.SCHEMA),
        (_wrong_type_body, PublicSourceIssueCode.SCHEMA),
        (lambda: _parquet([]), PublicSourceIssueCode.INSUFFICIENT_HISTORY),
        (
            lambda: _body_with_rows(lambda rows: rows.__setitem__(2, dict(rows[1]))),
            PublicSourceIssueCode.ROW,
        ),
        (
            lambda: _body_with_rows(lambda rows: rows.reverse()),
            PublicSourceIssueCode.ROW,
        ),
        (
            lambda: _body_with_rows(
                lambda rows: rows[2].__setitem__("datetime", datetime(2026, 9, 2))
            ),
            PublicSourceIssueCode.CALENDAR,
        ),
        (
            lambda: _body_with_rows(lambda rows: rows[2].__setitem__("source", "unknown")),
            PublicSourceIssueCode.ROW,
        ),
        (
            lambda: _body_with_rows(lambda rows: rows[2].__setitem__("source", "pitrading")),
            PublicSourceIssueCode.ROW,
        ),
        (
            lambda: _body_with_rows(lambda rows: rows[2].__setitem__("Low", 999.0)),
            PublicSourceIssueCode.ROW,
        ),
        (
            lambda: _body_with_rows(lambda rows: rows[2].__setitem__("Volume", -1)),
            PublicSourceIssueCode.ROW,
        ),
    ],
)
async def test_parquet_schema_and_row_failures_are_closed(
    body_factory: Callable[[], bytes],
    expected: PublicSourceIssueCode,
) -> None:
    body = body_factory()

    def handler(request: httpx.Request) -> httpx.Response:
        if "/download-token/" in request.url.path:
            return _token_response("SPY")
        return _download_response(body)

    budget = HFRequestBudget()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
            budget=budget,
        )

    assert _benchmark_failure_code(result) is expected
    assert budget.request_count == 2


@pytest.mark.asyncio
async def test_parquet_on_wire_limit_is_enforced_before_decode() -> None:
    body = _parquet()
    config = HFAdapterConfig(parquet_response_limit=len(body) - 1)

    def handler(request: httpx.Request) -> httpx.Response:
        if "/download-token/" in request.url.path:
            return _token_response("SPY")
        return _download_response(body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
            config=config,
        )

    assert _benchmark_failure_code(result) is PublicSourceIssueCode.RESPONSE_SIZE


@pytest.mark.asyncio
async def test_parquet_row_limit_is_enforced_before_materialization() -> None:
    start = datetime(1990, 1, 1)
    rows = [
        {
            "datetime": start + timedelta(days=index),
            "Open": 100.0,
            "High": 102.0,
            "Low": 99.0,
            "Close": 101.0,
            "Volume": 1_000,
            "source": "iex",
        }
        for index in range(10_001)
    ]
    body = _parquet(rows)

    def handler(request: httpx.Request) -> httpx.Response:
        if "/download-token/" in request.url.path:
            return _token_response("SPY")
        return _download_response(body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=date(2030, 1, 1),
        )

    assert _benchmark_failure_code(result) is PublicSourceIssueCode.RESPONSE_SIZE


@pytest.mark.asyncio
async def test_sector_concurrency_never_exceeds_three() -> None:
    active = 0
    maximum_active = 0
    paths: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        paths.append(request.url.path)
        await asyncio.sleep(0.001)
        active -= 1
        ticker = _ticker_from_path(request.url.path)
        if "/download-token/" in request.url.path:
            return _token_response(ticker)
        return _download_response()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
        )

    assert result.failures == ()
    assert maximum_active <= 3
    assert paths[:2] == ["/v1/download-token/SPY", "/v1/download/SPY"]


@pytest.mark.asyncio
async def test_injected_retry_sleep_failure_does_not_orphan_sibling_tasks() -> None:
    active = 0
    completed_downloads = 0
    request_count = 0

    async def failing_sleep(_: float) -> None:
        raise RuntimeError("injected sleep failure")

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, completed_downloads, request_count
        request_count += 1
        ticker = _ticker_from_path(request.url.path)
        if "/download-token/XLB" in request.url.path:
            return httpx.Response(503)
        active += 1
        await asyncio.sleep(0.002)
        active -= 1
        if "/download-token/" in request.url.path:
            return _token_response(ticker)
        completed_downloads += 1
        return _download_response()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
            sleep=failing_sleep,
        )

    requests_at_return = request_count
    await asyncio.sleep(0.02)
    assert active == 0
    assert request_count == requests_at_return
    assert completed_downloads == 10  # SPY plus nine successful sectors
    assert len(result.failures) == 1
    assert result.failures[0].ticker is SectorTicker.XLB
    assert result.failures[0].issue_code is PublicSourceIssueCode.TRANSPORT


@pytest.mark.asyncio
async def test_child_cancelled_error_does_not_orphan_sibling_tasks() -> None:
    active = 0
    completed_downloads = 0
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, completed_downloads, request_count
        request_count += 1
        ticker = _ticker_from_path(request.url.path)
        if "/download-token/XLB" in request.url.path:
            raise asyncio.CancelledError
        active += 1
        await asyncio.sleep(0.002)
        active -= 1
        if "/download-token/" in request.url.path:
            return _token_response(ticker)
        completed_downloads += 1
        return _download_response()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
        )

    requests_at_return = request_count
    await asyncio.sleep(0.02)
    assert active == 0
    assert request_count == requests_at_return
    assert completed_downloads == 10
    assert len(result.failures) == 1
    assert result.failures[0].ticker is SectorTicker.XLB
    assert result.failures[0].issue_code is PublicSourceIssueCode.TRANSPORT


@pytest.mark.asyncio
async def test_shared_budget_waits_at_rolling_window_boundary() -> None:
    now = [0.0]
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        now[0] += delay

    config = HFAdapterConfig(requests_per_minute=2, max_collection_requests=4)
    budget = HFRequestBudget(config, clock=lambda: now[0], sleep=fake_sleep)
    await budget.acquire()
    await budget.acquire()
    await budget.acquire()

    assert budget.request_count == 3
    assert sleeps == [60.0]


@given(
    attempt=st.integers(min_value=-10, max_value=10),
    retry_after=st.one_of(
        st.none(),
        st.floats(allow_nan=False, allow_infinity=False, width=32).map(str),
        st.text(max_size=16),
    ),
)
def test_retry_delay_is_always_bounded(attempt: int, retry_after: str | None) -> None:
    delay = compute_hf_retry_delay(attempt, retry_after)
    assert 0.0 <= delay <= 30.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"token_response_limit": 64 * 1024 + 1},
        {"parquet_response_limit": 2 * 1024 * 1024 + 1},
        {"max_rows": 10_001},
        {"requests_per_minute": 101},
        {"max_collection_requests": 67},
        {"concurrency": 4},
        {"retries": 3},
        {"connect_timeout_s": 5.1},
        {"read_timeout_s": 10.1},
        {"request_timeout_s": 15.1},
        {"collection_timeout_s": 120.1},
    ],
)
def test_config_cannot_raise_production_ceilings(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="ceiling"):
        HFAdapterConfig(**kwargs)


@pytest.mark.asyncio
async def test_retry_after_honors_lower_configured_cap() -> None:
    token_calls = 0
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls
        ticker = _ticker_from_path(request.url.path)
        if "/download-token/" in request.url.path:
            token_calls += 1
            if token_calls == 1:
                return httpx.Response(429, headers={"Retry-After": "20"})
            return _token_response(ticker)
        return _download_response()

    config = HFAdapterConfig(max_retry_after_s=1.0)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
            config=config,
            sleep=fake_sleep,
        )

    assert result.failures == ()
    assert sleeps == [1.0]


@pytest.mark.asyncio
async def test_mismatched_injected_budget_is_rejected_before_network() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise AssertionError("network must not be reached")

    config = HFAdapterConfig(max_collection_requests=22)
    mismatched_budget = HFRequestBudget()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
            config=config,
            budget=mismatched_budget,
        )

    assert calls == 0
    assert mismatched_budget.request_count == 0
    assert _benchmark_failure_code(result) is PublicSourceIssueCode.AUTH_CONFIGURATION


@pytest.mark.asyncio
async def test_httpx_and_httpcore_logs_redact_signed_url_key_and_headers(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signed_sentinel = "signed-log-capability-sentinel"
    monkeypatch.setenv("HF_DATA_API_KEY", _API_KEY)
    caplog.set_level(logging.DEBUG)

    def handler(request: httpx.Request) -> httpx.Response:
        ticker = _ticker_from_path(request.url.path)
        if "/download-token/" in request.url.path:
            return _token_response(
                ticker,
                signed_url=(
                    f"https://{HF_API_HOST}/v1/download/{ticker}"
                    f"?signature=prefix){signed_sentinel}-{ticker.lower()}"
                ),
            )
        return _download_response()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await collect_public_bars(
            client,
            environ={"HF_DATA_API_KEY": _API_KEY},
            target_date=_TARGET_DATE,
        )

    assert result.failures == ()
    logging.getLogger("httpcore.http11").debug(
        "receive_response_headers.complete return_value=%r",
        (b"HTTP/1.1", 200, b"OK", [(b"x-provider", b"provider-header-sentinel")]),
    )
    rendered = "\n".join(record.getMessage() for record in caplog.records)
    assert signed_sentinel not in rendered
    assert _API_KEY not in rendered
    assert "provider-header-sentinel" not in rendered
    assert "x-provider" not in rendered
    assert "[REDACTED_HTTP_TRANSPORT_EVENT]" in rendered


@pytest.mark.parametrize(
    "kwargs",
    [
        {"token_response_limit": 1.0},
        {"max_rows": True},
        {"retries": False},
        {"connect_timeout_s": 1},
        {"max_retry_after_s": 1},
        {"retry_backoffs": [1.0, 2.0]},
        {"retry_backoffs": (1, 2)},
    ],
)
def test_config_rejects_wrong_runtime_types(kwargs: dict[str, Any]) -> None:
    with pytest.raises(TypeError, match=r"type|tuple"):
        HFAdapterConfig(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"connect_timeout_s": float("nan")},
        {"read_timeout_s": float("inf")},
        {"max_retry_after_s": float("nan")},
        {"retry_backoffs": (float("nan"), 2.0)},
    ],
)
def test_config_rejects_non_finite_floats(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="ceiling"):
        HFAdapterConfig(**kwargs)
