"""Bounded HF Data Library adapter for the limited public sector radar.

The provider boundary is intentionally closed: one host, one daily-clean
Parquet request shape, and the fixed public request set. Provider-controlled
text, token JSON, signed URLs, and Parquet bytes never cross this module.
"""

from __future__ import annotations

import asyncio
import io
import json
import math
import time
import unicodedata
from collections import deque
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import date, datetime
from datetime import time as datetime_time
from decimal import Decimal
from typing import Final, NoReturn, cast
from urllib.parse import urlencode, urlsplit

import httpx

from investo._internal.redaction import install_secret_log_filters
from investo.models.sector import BENCHMARK_TICKER, SectorTicker
from investo.models.sector_public import (
    PUBLIC_REQUEST_TICKERS,
    PUBLIC_SUPPORTED_SECTOR_TICKERS,
    PublicBarPoint,
    PublicBarSeries,
    PublicParsedSet,
    PublicSourceFailure,
    PublicSourceIssueCode,
)

HF_API_BASE: Final = "https://api.hfdatalibrary.com/v1"
HF_API_HOST: Final = "api.hfdatalibrary.com"
HF_API_KEY_ENV: Final = "HF_DATA_API_KEY"
HF_USER_AGENT: Final = "investo-sector-dashboard/1.0"
HF_TOKEN_QUERY: Final[tuple[tuple[str, str], ...]] = (
    ("timeframe", "daily"),
    ("format", "parquet"),
    ("version", "clean"),
)

_TOKEN_RESPONSE_LIMIT: Final = 64 * 1024
_PARQUET_RESPONSE_LIMIT: Final = 2 * 1024 * 1024
_PARQUET_DECODED_LIMIT: Final = 16 * 1024 * 1024
_MAX_ROWS: Final = 10_000
# The public metric layer uses the last 64 SPY observations (63D plus anchor).
_CALCULATION_POINTS: Final = 64
_MAX_JSON_DEPTH: Final = 4
_MAX_JSON_STRING: Final = 256
_MAX_API_KEY_LENGTH: Final = 512
_MAX_REQUESTS_PER_MINUTE: Final = 100
_MAX_COLLECTION_REQUESTS: Final = 66
_MAX_CONCURRENCY: Final = 3
_MAX_RETRIES: Final = 2
_MAX_RETRY_AFTER_S: Final = 30.0
_CONNECT_TIMEOUT_S: Final = 5.0
_READ_TIMEOUT_S: Final = 10.0
_REQUEST_TIMEOUT_S: Final = 15.0
_COLLECTION_TIMEOUT_S: Final = 120.0

_TOKEN_MEDIA_TYPE: Final = "application/json"
_PARQUET_MEDIA_TYPE: Final = "application/octet-stream"
_SENSITIVE_REQUEST_HEADERS: Final = (
    "Authorization",
    "Proxy-Authorization",
    "Cookie",
    "X-API-Key",
)
_HTTP_LOGGER_NAMES: Final = (
    "httpx",
    "httpcore.connection",
    "httpcore.http11",
    "httpcore.http2",
    "httpcore.proxy",
    "httpcore.socks",
)
_PLACEHOLDER_KEYS: Final = frozenset(
    {
        "changeme",
        "hf_data_api_key",
        "placeholder",
        "replace_me",
        "your_api_key",
        "your_hf_data_api_key",
    }
)

Sleep = Callable[[float], Awaitable[None]]
Clock = Callable[[], float]


@dataclass(frozen=True, slots=True)
class HFAdapterConfig:
    """Downward-only resource knobs; endpoint and request identity are not configurable."""

    token_response_limit: int = _TOKEN_RESPONSE_LIMIT
    parquet_response_limit: int = _PARQUET_RESPONSE_LIMIT
    parquet_decoded_limit: int = _PARQUET_DECODED_LIMIT
    max_rows: int = _MAX_ROWS
    requests_per_minute: int = _MAX_REQUESTS_PER_MINUTE
    max_collection_requests: int = _MAX_COLLECTION_REQUESTS
    concurrency: int = _MAX_CONCURRENCY
    retries: int = _MAX_RETRIES
    retry_backoffs: tuple[float, ...] = (1.0, 2.0)
    max_retry_after_s: float = _MAX_RETRY_AFTER_S
    connect_timeout_s: float = _CONNECT_TIMEOUT_S
    read_timeout_s: float = _READ_TIMEOUT_S
    request_timeout_s: float = _REQUEST_TIMEOUT_S
    collection_timeout_s: float = _COLLECTION_TIMEOUT_S

    def __post_init__(self) -> None:
        bounded_integers = (
            ("token_response_limit", self.token_response_limit, _TOKEN_RESPONSE_LIMIT),
            ("parquet_response_limit", self.parquet_response_limit, _PARQUET_RESPONSE_LIMIT),
            ("parquet_decoded_limit", self.parquet_decoded_limit, _PARQUET_DECODED_LIMIT),
            ("max_rows", self.max_rows, _MAX_ROWS),
            ("requests_per_minute", self.requests_per_minute, _MAX_REQUESTS_PER_MINUTE),
            (
                "max_collection_requests",
                self.max_collection_requests,
                _MAX_COLLECTION_REQUESTS,
            ),
            ("concurrency", self.concurrency, _MAX_CONCURRENCY),
        )
        for int_name, int_value, int_ceiling in bounded_integers:
            if type(int_value) is not int:
                raise TypeError(f"{int_name} must have integer type")
            if int_value <= 0 or int_value > int_ceiling:
                raise ValueError(f"{int_name} must be within the production ceiling")

        bounded_floats = (
            ("connect_timeout_s", self.connect_timeout_s, _CONNECT_TIMEOUT_S),
            ("read_timeout_s", self.read_timeout_s, _READ_TIMEOUT_S),
            ("request_timeout_s", self.request_timeout_s, _REQUEST_TIMEOUT_S),
            ("collection_timeout_s", self.collection_timeout_s, _COLLECTION_TIMEOUT_S),
        )
        for float_name, float_value, float_ceiling in bounded_floats:
            if type(float_value) is not float:
                raise TypeError(f"{float_name} must have float type")
            if not math.isfinite(float_value) or float_value <= 0 or float_value > float_ceiling:
                raise ValueError(f"{float_name} must be within the production ceiling")
        if type(self.retries) is not int:
            raise TypeError("retries must have integer type")
        if not 0 <= self.retries <= _MAX_RETRIES:
            raise ValueError("retries must be within the production ceiling")
        if type(self.retry_backoffs) is not tuple or any(
            type(delay) is not float for delay in self.retry_backoffs
        ):
            raise TypeError("retry_backoffs must be a tuple of floats")
        if len(self.retry_backoffs) < self.retries:
            raise ValueError("retry_backoffs must cover retries")
        if any(
            not math.isfinite(delay) or delay < 0 or delay > _MAX_RETRY_AFTER_S
            for delay in self.retry_backoffs
        ):
            raise ValueError("retry backoffs must stay within the retry ceiling")
        if type(self.max_retry_after_s) is not float:
            raise TypeError("max_retry_after_s must have float type")
        if (
            not math.isfinite(self.max_retry_after_s)
            or not 0 <= self.max_retry_after_s <= _MAX_RETRY_AFTER_S
        ):
            raise ValueError("max_retry_after_s must stay within the production ceiling")


DEFAULT_HF_ADAPTER_CONFIG: Final = HFAdapterConfig()


class _AdapterError(Exception):
    """Internal closed failure that cannot carry provider-controlled text."""

    __slots__ = ("issue_code", "retry_after_s", "retryable")

    def __init__(
        self,
        issue_code: PublicSourceIssueCode,
        *,
        retryable: bool,
        retry_after_s: float | None = None,
    ) -> None:
        super().__init__(issue_code.value)
        self.issue_code = issue_code
        self.retryable = retryable
        self.retry_after_s = retry_after_s


class HFRequestBudget:
    """Shared rolling-minute and whole-collection request budget."""

    def __init__(
        self,
        config: HFAdapterConfig = DEFAULT_HF_ADAPTER_CONFIG,
        *,
        clock: Clock = time.monotonic,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._config = config
        self._clock = clock
        self._sleep = sleep
        self._timestamps: deque[float] = deque()
        self._request_count = 0
        self._successful_response_count = 0
        self._lock = asyncio.Lock()

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def successful_response_count(self) -> int:
        """HTTP 200 responses fully read within the accepted media/size envelope."""
        return self._successful_response_count

    def record_successful_response(self) -> None:
        self._successful_response_count += 1

    @property
    def config(self) -> HFAdapterConfig:
        return self._config

    async def acquire(self) -> None:
        while True:
            delay = 0.0
            async with self._lock:
                now = self._clock()
                while self._timestamps and now - self._timestamps[0] >= 60.0:
                    self._timestamps.popleft()
                if self._request_count >= self._config.max_collection_requests:
                    raise _AdapterError(PublicSourceIssueCode.THROTTLE, retryable=False)
                if len(self._timestamps) < self._config.requests_per_minute:
                    self._timestamps.append(now)
                    self._request_count += 1
                    return
                delay = max(60.0 - (now - self._timestamps[0]), 0.0)
            await self._sleep(delay)


def compute_hf_retry_delay(
    attempt: int,
    retry_after_header: str | None,
    config: HFAdapterConfig = DEFAULT_HF_ADAPTER_CONFIG,
) -> float:
    """Return a deterministic retry delay bounded to 30 seconds."""

    if retry_after_header is not None:
        try:
            parsed = float(retry_after_header.strip())
        except ValueError:
            parsed = math.nan
        if math.isfinite(parsed):
            return min(max(parsed, 0.0), config.max_retry_after_s)
    if 1 <= attempt <= len(config.retry_backoffs):
        return min(config.retry_backoffs[attempt - 1], config.max_retry_after_s)
    return 0.0


def _retry_after_seconds(header: str | None, config: HFAdapterConfig) -> float | None:
    if header is None:
        return None
    try:
        parsed = float(header.strip())
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return min(max(parsed, 0.0), config.max_retry_after_s)


def _failure_for(
    ticker: SectorTicker,
    failure: _AdapterError,
) -> PublicSourceFailure:
    return PublicSourceFailure(
        ticker=ticker,
        issue_code=failure.issue_code,
        retryable=failure.retryable,
    )


def _all_failures(failure: _AdapterError) -> PublicParsedSet:
    return PublicParsedSet(
        failures=tuple(_failure_for(ticker, failure) for ticker in PUBLIC_REQUEST_TICKERS)
    )


def _validated_api_key(environ: Mapping[str, str]) -> str:
    value = environ.get(HF_API_KEY_ENV, "")
    normalized_placeholder = value.casefold().replace("-", "_")
    if (
        not value
        or len(value) > _MAX_API_KEY_LENGTH
        or any(
            character.isspace() or unicodedata.category(character).startswith("C")
            for character in value
        )
        or normalized_placeholder in _PLACEHOLDER_KEYS
    ):
        raise _AdapterError(PublicSourceIssueCode.AUTH_CONFIGURATION, retryable=False)
    return value


def _token_url(ticker: SectorTicker) -> str:
    return f"{HF_API_BASE}/download-token/{ticker.value}?{urlencode(HF_TOKEN_QUERY)}"


def _validated_signed_url(payload: object, ticker: SectorTicker) -> str:
    if not isinstance(payload, dict) or not set(payload).issubset({"url", "expires_at"}):
        raise _AdapterError(PublicSourceIssueCode.SCHEMA, retryable=False)
    signed_url = payload.get("url")
    expires_at = payload.get("expires_at")
    if not isinstance(signed_url, str) or (
        expires_at is not None and not isinstance(expires_at, str)
    ):
        raise _AdapterError(PublicSourceIssueCode.SCHEMA, retryable=False)
    try:
        parsed = urlsplit(signed_url)
        port = parsed.port
    except ValueError:
        raise _AdapterError(PublicSourceIssueCode.SCHEMA, retryable=False) from None
    if (
        parsed.scheme != "https"
        or parsed.netloc != HF_API_HOST
        or parsed.hostname != HF_API_HOST
        or port is not None
        or parsed.path != f"/v1/download/{ticker.value}"
        or not parsed.query
        or any(character.isspace() or character in "'\"" for character in parsed.query)
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise _AdapterError(PublicSourceIssueCode.SCHEMA, retryable=False)
    return signed_url


def _reject_json_constant(_: str) -> NoReturn:
    raise ValueError


def _pairs_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _validate_json_envelope(value: object, *, depth: int = 1) -> None:
    if depth > _MAX_JSON_DEPTH:
        raise _AdapterError(PublicSourceIssueCode.SCHEMA, retryable=False)
    if isinstance(value, str):
        if len(value) > _MAX_JSON_STRING:
            raise _AdapterError(PublicSourceIssueCode.SCHEMA, retryable=False)
        return
    if value is None or isinstance(value, (bool, int, float)):
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if len(key) > _MAX_JSON_STRING:
                raise _AdapterError(PublicSourceIssueCode.SCHEMA, retryable=False)
            _validate_json_envelope(child, depth=depth + 1)
        return
    if isinstance(value, list):
        for child in value:
            _validate_json_envelope(child, depth=depth + 1)
        return
    raise _AdapterError(PublicSourceIssueCode.SCHEMA, retryable=False)


def _parse_token(body: bytes, ticker: SectorTicker) -> str:
    try:
        payload = json.loads(
            body,
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        raise _AdapterError(PublicSourceIssueCode.SCHEMA, retryable=False) from None
    _validate_json_envelope(payload)
    return _validated_signed_url(payload, ticker)


def _media_type(headers: httpx.Headers) -> str:
    value = cast(str, headers.get("Content-Type", ""))
    return value.split(";", maxsplit=1)[0].strip().lower()


def _content_length_exceeds(headers: httpx.Headers, limit: int) -> bool:
    try:
        content_length = int(headers.get("Content-Length", ""))
    except ValueError:
        return False
    return content_length > limit


async def _read_bounded(response: httpx.Response, limit: int) -> bytes:
    if _content_length_exceeds(response.headers, limit):
        raise _AdapterError(PublicSourceIssueCode.RESPONSE_SIZE, retryable=False)
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > limit:
            raise _AdapterError(PublicSourceIssueCode.RESPONSE_SIZE, retryable=False)
        chunks.append(chunk)
    return b"".join(chunks)


def _status_failure(response: httpx.Response, config: HFAdapterConfig) -> _AdapterError:
    status = response.status_code
    if status in {401, 403}:
        return _AdapterError(PublicSourceIssueCode.AUTH_REJECTED, retryable=False)
    if status == 429:
        retry_after = _retry_after_seconds(response.headers.get("Retry-After"), config)
        return _AdapterError(
            PublicSourceIssueCode.THROTTLE,
            retryable=True,
            retry_after_s=retry_after,
        )
    if status >= 500:
        return _AdapterError(PublicSourceIssueCode.STATUS, retryable=True)
    return _AdapterError(PublicSourceIssueCode.STATUS, retryable=False)


async def _request_bounded(
    client: httpx.AsyncClient,
    url: str,
    *,
    api_key: str | None,
    accept: str,
    expected_media_type: str,
    response_limit: int,
    budget: HFRequestBudget,
    config: HFAdapterConfig,
) -> bytes:
    await budget.acquire()
    response: httpx.Response | None = None
    try:
        async with asyncio.timeout(config.request_timeout_s):
            timeout = httpx.Timeout(
                config.request_timeout_s,
                connect=config.connect_timeout_s,
                read=config.read_timeout_s,
            )
            request = client.build_request(
                "GET",
                url,
                headers={
                    "Accept": accept,
                    "Accept-Encoding": "identity",
                    "User-Agent": HF_USER_AGENT,
                },
                timeout=timeout,
            )
            for header in _SENSITIVE_REQUEST_HEADERS:
                request.headers.pop(header, None)
            request.headers = httpx.Headers(
                {
                    "Host": HF_API_HOST,
                    "Accept": accept,
                    "Accept-Encoding": "identity",
                    "User-Agent": HF_USER_AGENT,
                }
            )
            if api_key is not None:
                request.headers["X-API-Key"] = api_key
            response = await client.send(
                request,
                stream=True,
                auth=None,
                follow_redirects=False,
            )
            if response.status_code != 200:
                raise _status_failure(response, config)
            if _media_type(response.headers) != expected_media_type:
                raise _AdapterError(PublicSourceIssueCode.SCHEMA, retryable=False)
            body = await _read_bounded(response, response_limit)
            budget.record_successful_response()
            return body
    except _AdapterError:
        raise
    except (TimeoutError, httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
        raise _AdapterError(PublicSourceIssueCode.TRANSPORT, retryable=True) from None
    except Exception:
        # Never let an exception created by the transport or a client hook
        # carry a signed URL, request headers, or API-key sentinel outward.
        raise _AdapterError(PublicSourceIssueCode.TRANSPORT, retryable=True) from None
    finally:
        # A provider-controlled Set-Cookie must not persist on the injected
        # client or influence any later request in the bounded fan-out.
        with suppress(Exception):
            client.cookies.clear()
        if response is not None:
            # Closing an injected transport must not override the safe closed
            # result with request material from its exception.
            with suppress(Exception):
                await response.aclose()


def _decode_public_parquet(
    body: bytes,
    ticker: SectorTicker,
    target_date: date,
    config: HFAdapterConfig,
) -> PublicBarSeries:
    try:
        import pyarrow as pa  # type: ignore[import-untyped]
        import pyarrow.parquet as pq  # type: ignore[import-untyped]
    except ImportError:
        raise _AdapterError(PublicSourceIssueCode.SCHEMA, retryable=False) from None

    expected_schema = pa.schema(
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
    try:
        parquet_file = pq.ParquetFile(io.BytesIO(body))
        schema = parquet_file.schema_arrow
        row_count = parquet_file.metadata.num_rows
        decoded_bytes = sum(
            parquet_file.metadata.row_group(group_index)
            .column(column_index)
            .total_uncompressed_size
            for group_index in range(parquet_file.metadata.num_row_groups)
            for column_index in range(parquet_file.metadata.num_columns)
        )
        if decoded_bytes < 0:
            raise _AdapterError(PublicSourceIssueCode.SCHEMA, retryable=False)
        if not schema.equals(expected_schema, check_metadata=False):
            raise _AdapterError(PublicSourceIssueCode.SCHEMA, retryable=False)
        if row_count > config.max_rows or decoded_bytes > config.parquet_decoded_limit:
            raise _AdapterError(PublicSourceIssueCode.RESPONSE_SIZE, retryable=False)
        if row_count == 0:
            raise _AdapterError(
                PublicSourceIssueCode.INSUFFICIENT_HISTORY,
                retryable=False,
            )
        table = parquet_file.read(columns=expected_schema.names)
        rows = table.to_pylist()
    except _AdapterError:
        raise
    except Exception:
        raise _AdapterError(PublicSourceIssueCode.SCHEMA, retryable=False) from None

    points: list[PublicBarPoint] = []
    previous_date: date | None = None
    observed_iex = False
    try:
        for row in rows:
            timestamp = row["datetime"]
            if (
                not isinstance(timestamp, datetime)
                or timestamp.tzinfo is not None
                or timestamp.time() != datetime_time.min
            ):
                raise _AdapterError(PublicSourceIssueCode.ROW, retryable=False)
            trading_date = timestamp.date()
            if trading_date > target_date:
                raise _AdapterError(PublicSourceIssueCode.CALENDAR, retryable=False)
            if previous_date is not None and trading_date <= previous_date:
                raise _AdapterError(PublicSourceIssueCode.ROW, retryable=False)
            previous_date = trading_date

            source = row["source"]
            if source not in {"iex", "pitrading"}:
                raise _AdapterError(PublicSourceIssueCode.ROW, retryable=False)
            if source == "pitrading" and observed_iex:
                raise _AdapterError(PublicSourceIssueCode.ROW, retryable=False)

            prices = tuple(row[name] for name in ("Open", "High", "Low", "Close"))
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
                for value in prices
            ):
                raise _AdapterError(PublicSourceIssueCode.ROW, retryable=False)
            open_value, high_value, low_value, close_value = prices
            if low_value > min(open_value, close_value) or high_value < max(
                open_value, close_value
            ):
                raise _AdapterError(PublicSourceIssueCode.ROW, retryable=False)
            volume = row["Volume"]
            if isinstance(volume, bool) or not isinstance(volume, int) or volume < 0:
                raise _AdapterError(PublicSourceIssueCode.ROW, retryable=False)

            if source == "iex":
                observed_iex = True
                points.append(
                    PublicBarPoint(
                        trading_date=trading_date,
                        open=Decimal(str(open_value)),
                        high=Decimal(str(high_value)),
                        low=Decimal(str(low_value)),
                        close=Decimal(str(close_value)),
                        volume=volume,
                    )
                )
    except _AdapterError:
        raise
    except Exception:
        raise _AdapterError(PublicSourceIssueCode.ROW, retryable=False) from None

    if len(points) < 2:
        raise _AdapterError(PublicSourceIssueCode.INSUFFICIENT_HISTORY, retryable=False)
    try:
        return PublicBarSeries(
            ticker=ticker,
            points=tuple(points),
            first_date=points[0].trading_date,
            latest_date=points[-1].trading_date,
        )
    except Exception:
        raise _AdapterError(PublicSourceIssueCode.ROW, retryable=False) from None


async def _fetch_ticker_once(
    client: httpx.AsyncClient,
    *,
    ticker: SectorTicker,
    api_key: str,
    target_date: date,
    budget: HFRequestBudget,
    config: HFAdapterConfig,
) -> PublicBarSeries:
    token_body = await _request_bounded(
        client,
        _token_url(ticker),
        api_key=api_key,
        accept=_TOKEN_MEDIA_TYPE,
        expected_media_type=_TOKEN_MEDIA_TYPE,
        response_limit=config.token_response_limit,
        budget=budget,
        config=config,
    )
    signed_url = _parse_token(token_body, ticker)
    parquet_body = await _request_bounded(
        client,
        signed_url,
        api_key=None,
        accept=_PARQUET_MEDIA_TYPE,
        expected_media_type=_PARQUET_MEDIA_TYPE,
        response_limit=config.parquet_response_limit,
        budget=budget,
        config=config,
    )
    return _decode_public_parquet(parquet_body, ticker, target_date, config)


async def _fetch_ticker(
    client: httpx.AsyncClient,
    *,
    ticker: SectorTicker,
    api_key: str,
    target_date: date,
    budget: HFRequestBudget,
    config: HFAdapterConfig,
    sleep: Sleep,
) -> PublicBarSeries | PublicSourceFailure:
    for zero_based_attempt in range(config.retries + 1):
        try:
            return await _fetch_ticker_once(
                client,
                ticker=ticker,
                api_key=api_key,
                target_date=target_date,
                budget=budget,
                config=config,
            )
        except _AdapterError as failure:
            if not failure.retryable or zero_based_attempt >= config.retries:
                return _failure_for(ticker, failure)
            retry_number = zero_based_attempt + 1
            delay = (
                failure.retry_after_s
                if failure.retry_after_s is not None
                else compute_hf_retry_delay(retry_number, None, config)
            )
            await sleep(delay)
    raise AssertionError("bounded retry loop must return")


def _client_has_observing_hooks(client: httpx.AsyncClient) -> bool:
    return any(client.event_hooks.get(kind, ()) for kind in ("request", "response"))


def _retain_calculation_window(
    series: PublicBarSeries,
    benchmark_dates: frozenset[date] | None,
) -> PublicBarSeries:
    """Discard validated history before collecting the next rich OHLCV series.

    Sector dates follow SPY, not an independent tail that could lose a required
    anchor. The final two sector points preserve parser success and the latest
    endpoint even when fewer than two observations overlap the SPY window.
    """
    if benchmark_dates is None:
        points = series.points[-_CALCULATION_POINTS:]
    else:
        retained_dates = benchmark_dates | {point.trading_date for point in series.points[-2:]}
        points = tuple(point for point in series.points if point.trading_date in retained_dates)
    return PublicBarSeries(
        ticker=series.ticker,
        points=points,
        first_date=points[0].trading_date,
        latest_date=points[-1].trading_date,
    )


async def collect_public_bars(
    client: httpx.AsyncClient,
    *,
    environ: Mapping[str, str],
    target_date: date,
    config: HFAdapterConfig = DEFAULT_HF_ADAPTER_CONFIG,
    budget: HFRequestBudget | None = None,
    sleep: Sleep = asyncio.sleep,
) -> PublicParsedSet:
    """Collect SPY first, then ten sectors, returning only normalized types.

    Invalid credential/client configuration is represented as a closed failure
    for the fixed request partition and performs zero network calls.
    """

    if not isinstance(target_date, date) or isinstance(target_date, datetime):
        raise ValueError("target_date must be date-only")
    install_secret_log_filters(_HTTP_LOGGER_NAMES)
    try:
        api_key = _validated_api_key(environ)
        if (
            _client_has_observing_hooks(client)
            or client.params
            or client.cookies
            or (budget is not None and budget.config != config)
        ):
            raise _AdapterError(PublicSourceIssueCode.AUTH_CONFIGURATION, retryable=False)
    except _AdapterError as failure:
        return _all_failures(failure)

    shared_budget = budget or HFRequestBudget(config, sleep=sleep)
    results: dict[SectorTicker, PublicBarSeries | PublicSourceFailure] = {}
    benchmark_dates: frozenset[date] | None = None

    async def fetch_and_record(ticker: SectorTicker) -> None:
        try:
            result = await _fetch_ticker(
                client,
                ticker=ticker,
                api_key=api_key,
                target_date=target_date,
                budget=shared_budget,
                config=config,
                sleep=sleep,
            )
            # Decode and validate every row first. Retain only the calculation
            # window so eleven maximum-size rich-model histories never coexist.
            results[ticker] = (
                _retain_calculation_window(result, benchmark_dates)
                if isinstance(result, PublicBarSeries)
                else result
            )
        except Exception:
            # Injected clocks/sleep functions and custom transports are part
            # of this boundary too. Convert them per ticker so gather awaits
            # every sibling and no request survives collection return.
            results[ticker] = PublicSourceFailure(
                ticker=ticker,
                issue_code=PublicSourceIssueCode.TRANSPORT,
                retryable=True,
            )

    try:
        async with asyncio.timeout(config.collection_timeout_s):
            await fetch_and_record(BENCHMARK_TICKER)
            benchmark_result = results[BENCHMARK_TICKER]
            if isinstance(benchmark_result, PublicSourceFailure):
                for ticker in PUBLIC_SUPPORTED_SECTOR_TICKERS:
                    results[ticker] = PublicSourceFailure(
                        ticker=ticker,
                        issue_code=benchmark_result.issue_code,
                        retryable=benchmark_result.retryable,
                    )
            else:
                benchmark_dates = frozenset(point.trading_date for point in benchmark_result.points)
                semaphore = asyncio.Semaphore(config.concurrency)

                async def bounded_fetch(ticker: SectorTicker) -> None:
                    async with semaphore:
                        await fetch_and_record(ticker)

                tasks = [
                    asyncio.create_task(bounded_fetch(ticker))
                    for ticker in PUBLIC_SUPPORTED_SECTOR_TICKERS
                ]
                try:
                    # A child-only CancelledError is a ticker failure, not a
                    # reason to abandon live siblings. Parent cancellation
                    # still cancels and drains the entire owned task set.
                    await asyncio.gather(*tasks, return_exceptions=True)
                except BaseException:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    raise
    except TimeoutError:
        pass

    for ticker in PUBLIC_REQUEST_TICKERS:
        if ticker not in results:
            results[ticker] = PublicSourceFailure(
                ticker=ticker,
                issue_code=PublicSourceIssueCode.TRANSPORT,
                retryable=True,
            )

    benchmark = results[BENCHMARK_TICKER]
    sectors = {
        ticker: result
        for ticker in PUBLIC_SUPPORTED_SECTOR_TICKERS
        if isinstance((result := results[ticker]), PublicBarSeries)
    }
    failures = tuple(
        result
        for ticker in PUBLIC_REQUEST_TICKERS
        if isinstance((result := results[ticker]), PublicSourceFailure)
    )
    return PublicParsedSet(
        benchmark=benchmark if isinstance(benchmark, PublicBarSeries) else None,
        sectors=sectors,
        failures=failures,
    )


__all__ = [
    "DEFAULT_HF_ADAPTER_CONFIG",
    "HF_API_BASE",
    "HF_API_HOST",
    "HF_API_KEY_ENV",
    "HF_TOKEN_QUERY",
    "HF_USER_AGENT",
    "HFAdapterConfig",
    "HFRequestBudget",
    "collect_public_bars",
    "compute_hf_retry_delay",
]
