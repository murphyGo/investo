"""Tests for ``investo.sources._retry``.

Pins:

* AC-1.2 — 60-s outer wall-clock cap (timing test with shrunken config)
* AC-6.3 — ``compute_sleep`` PBT: bounded ``0 <= sleep <= 30``,
  Retry-After precedence, fallback to deterministic exp schedule
* AC-7.1 — payload > 5 MB cap (test uses shrunken cap)
* FD R4 — retry policy
* FD R5 — Retry-After honoring with cap
* FD R6 — failure surfaces as :class:`SourceFetchError`

Tests use ``httpx.MockTransport`` so the suite stays offline.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from investo.sources._retry import (
    DEFAULT_CONFIG,
    RetryConfig,
    SourceFetchError,
    _parse_retry_after,
    compute_sleep,
    retry_get,
)

_PBT_SETTINGS = settings(max_examples=100, deadline=None)
_NO_SLEEP = RetryConfig(backoffs=(0.0, 0.0))  # Same defaults but skip real sleeps.


class _TrackingStream(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks
        self.was_read = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        self.was_read = True
        for chunk in self._chunks:
            yield chunk


# ---------------------------------------------------------------------------
# SourceFetchError
# ---------------------------------------------------------------------------


def test_source_fetch_error_attributes() -> None:
    cause = RuntimeError("boom")
    err = SourceFetchError("fomc-rss", "kaboom", transient=True, cause=cause)
    assert err.source_name == "fomc-rss"
    assert err.transient is True
    assert err.cause is cause
    assert "fomc-rss" in str(err)
    assert "kaboom" in str(err)


def test_source_fetch_error_is_exception_subclass() -> None:
    err = SourceFetchError("x", "y", transient=False)
    assert isinstance(err, Exception)


# ---------------------------------------------------------------------------
# RetryConfig validation
# ---------------------------------------------------------------------------


def test_retry_config_defaults() -> None:
    cfg = RetryConfig()
    assert cfg.timeout_s == 30.0
    assert cfg.retries == 2
    assert cfg.backoffs == (1.0, 2.0)
    assert cfg.total_budget_s == 60.0
    assert cfg.max_retry_after_s == 30.0
    assert cfg.max_response_bytes == 5 * 1024 * 1024


def test_retry_config_rejects_negative_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_s must be positive"):
        RetryConfig(timeout_s=0)


def test_retry_config_rejects_negative_retries() -> None:
    with pytest.raises(ValueError, match="retries must be non-negative"):
        RetryConfig(retries=-1, backoffs=())


def test_retry_config_rejects_short_backoffs() -> None:
    with pytest.raises(ValueError, match=r"backoffs.*must cover retries"):
        RetryConfig(retries=3, backoffs=(1.0, 2.0))


def test_retry_config_rejects_negative_backoff() -> None:
    with pytest.raises(ValueError, match="backoffs must be non-negative"):
        RetryConfig(backoffs=(-1.0, 2.0))


def test_retry_config_rejects_zero_budget() -> None:
    with pytest.raises(ValueError, match="total_budget_s must be positive"):
        RetryConfig(total_budget_s=0)


def test_retry_config_rejects_zero_max_response_bytes() -> None:
    with pytest.raises(ValueError, match="max_response_bytes must be positive"):
        RetryConfig(max_response_bytes=0)


# ---------------------------------------------------------------------------
# _parse_retry_after
# ---------------------------------------------------------------------------


def test_parse_retry_after_none_returns_none() -> None:
    assert _parse_retry_after(None) is None


def test_parse_retry_after_empty_returns_none() -> None:
    assert _parse_retry_after("") is None
    assert _parse_retry_after("   ") is None


def test_parse_retry_after_seconds() -> None:
    assert _parse_retry_after("5") == 5.0
    assert _parse_retry_after("0") == 0.0
    assert _parse_retry_after("0.5") == 0.5


def test_parse_retry_after_negative_clamped_to_zero() -> None:
    assert _parse_retry_after("-10") == 0.0


def test_parse_retry_after_garbage_returns_none() -> None:
    assert _parse_retry_after("abc") is None
    assert _parse_retry_after("not-a-date") is None


def test_parse_retry_after_nan_returns_none() -> None:
    # `float("NaN")` succeeds but a NaN bound would silently bypass
    # compute_sleep's [0, max_retry_after_s] invariant (NaN
    # comparisons always return False). Pinned by hypothesis on
    # 2026-04-27 — falsifying example was retry_after_header="NaN".
    assert _parse_retry_after("NaN") is None
    assert _parse_retry_after("nan") is None


def test_parse_retry_after_infinity_returns_none() -> None:
    assert _parse_retry_after("Infinity") is None
    assert _parse_retry_after("-Infinity") is None
    assert _parse_retry_after("inf") is None


def test_parse_retry_after_http_date_in_past() -> None:
    # "Sun, 06 Nov 1994 08:49:37 GMT" — RFC 7231 example, far in past.
    result = _parse_retry_after("Sun, 06 Nov 1994 08:49:37 GMT")
    assert result == 0.0


def test_parse_retry_after_http_date_in_future() -> None:
    # Far-future HTTP-date — returns a large positive number; the
    # caller (compute_sleep) will cap it.
    result = _parse_retry_after("Sat, 01 Jan 2200 00:00:00 GMT")
    assert result is not None
    assert result > 30.0


# ---------------------------------------------------------------------------
# compute_sleep — anchors
# ---------------------------------------------------------------------------


def test_compute_sleep_default_first_retry() -> None:
    assert compute_sleep(1, None) == 1.0


def test_compute_sleep_default_second_retry() -> None:
    assert compute_sleep(2, None) == 2.0


def test_compute_sleep_out_of_range_high() -> None:
    assert compute_sleep(3, None) == 0.0


def test_compute_sleep_out_of_range_low() -> None:
    assert compute_sleep(0, None) == 0.0
    assert compute_sleep(-1, None) == 0.0


def test_compute_sleep_retry_after_overrides_default() -> None:
    assert compute_sleep(1, "5") == 5.0


def test_compute_sleep_retry_after_capped() -> None:
    assert compute_sleep(1, "1000") == 30.0


def test_compute_sleep_retry_after_unparseable_falls_back() -> None:
    assert compute_sleep(1, "garbage") == 1.0


def test_compute_sleep_retry_after_http_date_capped() -> None:
    assert compute_sleep(1, "Sat, 01 Jan 2200 00:00:00 GMT") == 30.0


# ---------------------------------------------------------------------------
# compute_sleep — PBT for AC-6.3 (bounded, Retry-After precedence)
# ---------------------------------------------------------------------------


@given(
    attempt=st.integers(min_value=-2, max_value=10),
    retry_after_header=st.one_of(st.none(), st.text(max_size=64)),
)
@_PBT_SETTINGS
def test_property_compute_sleep_bounded(attempt: int, retry_after_header: str | None) -> None:
    sleep = compute_sleep(attempt, retry_after_header, DEFAULT_CONFIG)
    assert 0.0 <= sleep <= DEFAULT_CONFIG.max_retry_after_s


@given(seconds=st.floats(min_value=0.0, max_value=10_000.0, allow_nan=False, allow_infinity=False))
@_PBT_SETTINGS
def test_property_compute_sleep_retry_after_capped(seconds: float) -> None:
    sleep = compute_sleep(1, str(seconds), DEFAULT_CONFIG)
    assert sleep == min(seconds, DEFAULT_CONFIG.max_retry_after_s)


# ---------------------------------------------------------------------------
# retry_get — happy path
# ---------------------------------------------------------------------------


def _mock_client(handler: object) -> httpx.AsyncClient:
    if isinstance(handler, httpx.MockTransport):
        transport = handler
    else:
        transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return httpx.AsyncClient(transport=transport)


async def test_retry_get_first_try_success() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"ok")

    async with _mock_client(handler) as client:
        response = await retry_get(client, "http://x", source_name="test", config=_NO_SLEEP)
    assert response.status_code == 200
    assert response.content == b"ok"
    assert calls == 1


async def test_retry_get_passes_headers_and_params() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["agent"] = request.headers.get("User-Agent", "")
        return httpx.Response(200, content=b"ok")

    async with _mock_client(handler) as client:
        await retry_get(
            client,
            "http://x/path",
            source_name="test",
            headers={"User-Agent": "investo/1.0"},
            params={"q": "v"},
            config=_NO_SLEEP,
        )
    assert seen["url"] == "http://x/path?q=v"
    assert seen["agent"] == "investo/1.0"


# ---------------------------------------------------------------------------
# retry_get — retry on transient failure
# ---------------------------------------------------------------------------


async def test_retry_get_retries_on_5xx_then_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 2:
            return httpx.Response(503)
        return httpx.Response(200, content=b"ok")

    async with _mock_client(handler) as client:
        response = await retry_get(client, "http://x", source_name="test", config=_NO_SLEEP)
    assert response.status_code == 200
    assert calls == 2


async def test_retry_get_retries_on_429_then_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 2:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, content=b"ok")

    async with _mock_client(handler) as client:
        response = await retry_get(client, "http://x", source_name="test", config=_NO_SLEEP)
    assert response.status_code == 200
    assert calls == 2


async def test_retry_get_retries_on_network_error_then_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise httpx.ConnectError("network down")
        return httpx.Response(200, content=b"ok")

    async with _mock_client(handler) as client:
        response = await retry_get(client, "http://x", source_name="test", config=_NO_SLEEP)
    assert response.status_code == 200
    assert calls == 2


async def test_retry_get_exhausts_retries_on_persistent_5xx() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    async with _mock_client(handler) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await retry_get(client, "http://x", source_name="test", config=_NO_SLEEP)
    assert exc_info.value.transient is True
    assert exc_info.value.source_name == "test"
    assert "503" in str(exc_info.value)
    # 1 initial attempt + 2 retries = 3 calls
    assert calls == 3


async def test_retry_get_exhausts_retries_on_persistent_network_error() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("timed out")

    async with _mock_client(handler) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await retry_get(client, "http://x", source_name="test", config=_NO_SLEEP)
    assert exc_info.value.transient is True
    assert isinstance(exc_info.value.cause, httpx.ReadTimeout)
    assert calls == 3


# ---------------------------------------------------------------------------
# retry_get — terminal (non-retryable) outcomes
# ---------------------------------------------------------------------------


async def test_retry_get_4xx_not_429_is_terminal() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404)

    async with _mock_client(handler) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await retry_get(client, "http://x", source_name="test", config=_NO_SLEEP)
    assert exc_info.value.transient is False
    assert "404" in str(exc_info.value)
    # No retries on 4xx-not-429.
    assert calls == 1


async def test_retry_get_oversized_body_is_terminal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 10_000)

    config = RetryConfig(backoffs=(0.0, 0.0), max_response_bytes=1_000)
    async with _mock_client(handler) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await retry_get(client, "http://x", source_name="test", config=config)
    assert exc_info.value.transient is False
    assert "exceeds" in str(exc_info.value)


async def test_retry_get_rejects_oversized_content_length_before_reading_body() -> None:
    stream = _TrackingStream([b"x" * 10_000])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Length": "10000"},
            stream=stream,
        )

    config = RetryConfig(backoffs=(0.0, 0.0), max_response_bytes=1_000)
    async with _mock_client(handler) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await retry_get(client, "http://x", source_name="test", config=config)

    assert exc_info.value.transient is False
    assert "Content-Length" in str(exc_info.value)
    assert stream.was_read is False


async def test_retry_get_aborts_stream_when_body_exceeds_cap_without_length() -> None:
    stream = _TrackingStream([b"x" * 600, b"y" * 600])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=stream)

    config = RetryConfig(backoffs=(0.0, 0.0), max_response_bytes=1_000)
    async with _mock_client(handler) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await retry_get(client, "http://x", source_name="test", config=config)

    assert exc_info.value.transient is False
    assert "streaming" in str(exc_info.value)
    assert stream.was_read is True


async def test_retry_get_unsupported_scheme_is_terminal() -> None:
    # httpx raises UnsupportedProtocol synchronously for file:// — we
    # want it surfaced as terminal SourceFetchError, not retried.
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await retry_get(client, "file:///etc/passwd", source_name="test", config=_NO_SLEEP)
    assert exc_info.value.transient is False
    assert isinstance(exc_info.value.cause, httpx.UnsupportedProtocol)


# ---------------------------------------------------------------------------
# retry_get — Retry-After honoring (FD R5)
# ---------------------------------------------------------------------------


async def test_retry_get_honors_retry_after_header() -> None:
    # Default backoff is 1 s on first retry; Retry-After=0.05 should
    # take precedence and shorten the wait.
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 2:
            return httpx.Response(429, headers={"Retry-After": "0.05"})
        return httpx.Response(200)

    config = RetryConfig(backoffs=(1.0, 1.0))  # would otherwise sleep 1 s
    async with _mock_client(handler) as client:
        start = time.monotonic()
        await retry_get(client, "http://x", source_name="test", config=config)
        elapsed = time.monotonic() - start
    assert calls == 2
    # Retry-After (50 ms) overrode the 1 s default; allow 500 ms slack
    # for scheduling jitter on slow CI hosts.
    assert elapsed < 0.5


# ---------------------------------------------------------------------------
# retry_get — outer 60-s wall-clock budget (AC-1.2)
# ---------------------------------------------------------------------------


async def test_retry_get_budget_enforced() -> None:
    # Use a shrunken budget so the test is fast. Handler sleeps longer
    # than the budget, so the wait_for fires.

    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1.0)
        return httpx.Response(200)

    config = RetryConfig(backoffs=(0.0, 0.0), total_budget_s=0.1, timeout_s=10.0)
    async with _mock_client(handler) as client:
        start = time.monotonic()
        with pytest.raises(SourceFetchError) as exc_info:
            await retry_get(client, "http://x", source_name="test", config=config)
        elapsed = time.monotonic() - start
    assert exc_info.value.transient is True
    assert "budget" in str(exc_info.value)
    # Should bail at ~0.1 s, not ~1 s.
    assert elapsed < 0.5
