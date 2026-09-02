#!/usr/bin/env python3
"""Run the sanitized u145 Step 0 HF Data Library source-contract probe.

The probe deliberately keeps provider payloads in memory, emits only aggregate
schema/date/count evidence, and never prints the API key or signed download URL.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal

API_BASE: Final = "https://api.hfdatalibrary.com/v1"
API_HOST: Final = "api.hfdatalibrary.com"
USER_AGENT: Final = "investo-sector-probe/1.0 (+https://github.com/murphyGo/investo)"
REQUESTED_TICKERS: Final = (
    "SPY",
    "XLB",
    "XLC",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
)
EXPECTED_MISSING: Final = "XLRE"
TOKEN_RESPONSE_LIMIT: Final = 64 * 1024
DAILY_RESPONSE_LIMIT: Final = 8 * 1024 * 1024
MINIMUM_DAILY_ROWS: Final = 64
TIMEOUT_SECONDS: Final = 30


class ProbeError(RuntimeError):
    """A redacted source-contract failure safe to show in Actions logs."""


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        del req, fp, code, msg, headers, newurl
        return None


OPENER: Final = urllib.request.build_opener(NoRedirectHandler())


@dataclass(frozen=True)
class Response:
    status: int
    content_type: str
    body: bytes


AuthScheme = Literal["x_api_key", "bearer"]


def _read_bounded(response, limit: int) -> bytes:
    body = response.read(limit + 1)
    if len(body) > limit:
        raise ProbeError(f"response_size_exceeded:{limit}")
    return body


def _request(
    url: str,
    *,
    api_key: str | None = None,
    auth_scheme: AuthScheme = "x_api_key",
    limit: int,
) -> Response:
    headers = {"Accept": "*/*", "User-Agent": USER_AGENT}
    if api_key is not None:
        if auth_scheme == "x_api_key":
            headers["X-API-Key"] = api_key
        else:
            headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with OPENER.open(request, timeout=TIMEOUT_SECONDS) as response:
            return Response(
                status=response.status,
                content_type=response.headers.get_content_type(),
                body=_read_bounded(response, limit),
            )
    except urllib.error.HTTPError as exc:
        return Response(
            status=exc.code,
            content_type=exc.headers.get_content_type(),
            body=_read_bounded(exc, limit),
        )
    except (TimeoutError, urllib.error.URLError) as exc:
        raise ProbeError(f"transport:{type(exc).__name__}") from None


def _validated_key() -> str:
    key = os.environ.get("HF_DATA_API_KEY", "")
    if not key or key != key.strip() or any(ord(char) < 32 for char in key):
        raise ProbeError("credential:missing_or_invalid")
    if len(key) > 512:
        raise ProbeError("credential:overlong")
    return key


def _public_symbol_status(ticker: str) -> tuple[int, dict[str, object] | None]:
    response = _request(
        f"{API_BASE}/symbols/{ticker}",
        limit=TOKEN_RESPONSE_LIMIT,
    )
    if response.status != 200:
        return response.status, None
    try:
        payload = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ProbeError(f"symbol_schema:{ticker}") from None
    if not isinstance(payload, dict):
        raise ProbeError(f"symbol_schema:{ticker}")
    return response.status, payload


def _token_request(
    ticker: str,
    api_key: str,
    *,
    auth_scheme: AuthScheme,
    timeframe: str,
    output_format: str,
) -> Response:
    query = urllib.parse.urlencode(
        {"timeframe": timeframe, "format": output_format, "version": "clean"}
    )
    return _request(
        f"{API_BASE}/download-token/{ticker}?{query}",
        api_key=api_key,
        auth_scheme=auth_scheme,
        limit=TOKEN_RESPONSE_LIMIT,
    )


def _token_url(
    ticker: str,
    api_key: str,
    *,
    auth_scheme: AuthScheme,
    output_format: str,
) -> tuple[str, str]:
    response = _token_request(
        ticker,
        api_key,
        auth_scheme=auth_scheme,
        timeframe="daily",
        output_format=output_format,
    )
    if response.status != 200:
        raise ProbeError(
            f"download_token_status:{ticker}:{response.status}:{response.content_type}"
        )
    try:
        payload = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ProbeError(f"download_token_schema:{ticker}") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("url"), str):
        raise ProbeError(f"download_token_schema:{ticker}")

    signed_url = payload["url"]
    parsed = urllib.parse.urlparse(signed_url)
    expected_path = f"/v1/download/{ticker}"
    if (
        parsed.scheme != "https"
        or parsed.hostname != API_HOST
        or parsed.path != expected_path
        or not parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ProbeError(f"download_url_contract:{ticker}")
    expires_at = payload.get("expires_at")
    return signed_url, expires_at if isinstance(expires_at, str) else "unknown"


def _parse_date(value: str) -> date:
    candidate = value.strip()
    if not candidate:
        raise ValueError
    normalized = candidate.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        return date.fromisoformat(candidate[:10])


def _coerce_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return _parse_date(str(value))


def _summarize_daily_csv(ticker: str, response: Response) -> dict[str, object]:
    try:
        text = response.body.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ProbeError(f"daily_encoding:{ticker}") from None
    reader = csv.DictReader(io.StringIO(text, newline=""))
    fields = tuple(reader.fieldnames or ())
    if not fields or len(fields) > 128:
        raise ProbeError(f"daily_fields:{ticker}")
    lower_fields = {field.strip().lower(): field for field in fields}
    date_field = next(
        (lower_fields[name] for name in ("date", "datetime", "timestamp") if name in lower_fields),
        None,
    )
    required = {"open", "high", "low", "close", "volume"}
    if date_field is None or not required.issubset(lower_fields):
        raise ProbeError(f"daily_schema:{ticker}")

    row_count = 0
    first_date: date | None = None
    latest_date: date | None = None
    zero_volume_rows = 0
    for row in reader:
        row_count += 1
        try:
            row_date = _parse_date(row[date_field])
            volume = float(row[lower_fields["volume"]])
        except (KeyError, TypeError, ValueError):
            raise ProbeError(f"daily_row:{ticker}") from None
        if first_date is None or row_date < first_date:
            first_date = row_date
        if latest_date is None or row_date > latest_date:
            latest_date = row_date
        if volume == 0:
            zero_volume_rows += 1

    if row_count < MINIMUM_DAILY_ROWS or first_date is None or latest_date is None:
        raise ProbeError(f"daily_history:{ticker}:{row_count}")
    return {
        "ticker": ticker,
        "status": response.status,
        "content_type": response.content_type,
        "size_bytes": len(response.body),
        "columns": sorted(lower_fields),
        "row_count": row_count,
        "first_date": first_date.isoformat(),
        "latest_date": latest_date.isoformat(),
        "zero_volume_rows": zero_volume_rows,
    }


def _summarize_daily_parquet(ticker: str, response: Response) -> dict[str, object]:
    try:
        import pyarrow.parquet as parquet
    except ImportError:
        raise ProbeError("probe_dependency:pyarrow") from None

    try:
        parquet_file = parquet.ParquetFile(io.BytesIO(response.body))
        fields = tuple(parquet_file.schema_arrow.names)
    except Exception as exc:  # pyarrow exposes several format-specific exception types
        raise ProbeError(f"daily_parquet:{ticker}:{type(exc).__name__}") from None

    if not fields or len(fields) > 128:
        raise ProbeError(f"daily_fields:{ticker}")
    lower_fields = {field.strip().lower(): field for field in fields}
    date_field = next(
        (lower_fields[name] for name in ("date", "datetime", "timestamp") if name in lower_fields),
        None,
    )
    required = {"open", "high", "low", "close", "volume"}
    if date_field is None or not required.issubset(lower_fields):
        raise ProbeError(f"daily_schema:{ticker}")

    try:
        selected_fields = [
            date_field,
            lower_fields["open"],
            lower_fields["high"],
            lower_fields["low"],
            lower_fields["close"],
            lower_fields["volume"],
        ]
        source_field = lower_fields.get("source")
        if source_field is not None:
            selected_fields.append(source_field)
        selected = parquet_file.read(columns=selected_fields)
        date_values = selected.column(date_field).to_pylist()
        open_values = selected.column(lower_fields["open"]).to_pylist()
        high_values = selected.column(lower_fields["high"]).to_pylist()
        low_values = selected.column(lower_fields["low"]).to_pylist()
        close_values = selected.column(lower_fields["close"]).to_pylist()
        volume_values = selected.column(lower_fields["volume"]).to_pylist()
        dates = [_coerce_date(value) for value in date_values]
        volumes = [float(value) for value in volume_values]
    except (TypeError, ValueError) as exc:
        raise ProbeError(f"daily_row:{ticker}:{type(exc).__name__}") from None

    row_count = len(dates)
    if row_count < MINIMUM_DAILY_ROWS:
        raise ProbeError(f"daily_history:{ticker}:{row_count}")
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise ProbeError(f"daily_order:{ticker}")

    invalid_ohlc_rows = 0
    for open_value, high_value, low_value, close_value in zip(
        open_values,
        high_values,
        low_values,
        close_values,
        strict=True,
    ):
        try:
            open_number, high_number, low_number, close_number = (
                float(open_value),
                float(high_value),
                float(low_value),
                float(close_value),
            )
        except (TypeError, ValueError):
            invalid_ohlc_rows += 1
            continue
        if (
            not all(
                math.isfinite(value) and value > 0
                for value in (open_number, high_number, low_number, close_number)
            )
            or low_number > open_number
            or low_number > close_number
            or high_number < open_number
            or high_number < close_number
        ):
            invalid_ohlc_rows += 1
    negative_volume_rows = sum(value < 0 for value in volumes)
    if invalid_ohlc_rows or negative_volume_rows:
        raise ProbeError(f"daily_values:{ticker}:{invalid_ohlc_rows}:{negative_volume_rows}")

    source_counts: dict[str, int] = {}
    latest_source = "unknown"
    if source_field is not None:
        source_values = [str(value) for value in selected.column(source_field).to_pylist()]
        source_counts = dict(sorted(Counter(source_values).items()))
        latest_source = source_values[-1]
    return {
        "ticker": ticker,
        "status": response.status,
        "content_type": response.content_type,
        "size_bytes": len(response.body),
        "columns": sorted(lower_fields),
        "row_count": row_count,
        "first_date": min(dates).isoformat(),
        "latest_date": max(dates).isoformat(),
        "strictly_ascending_unique_dates": True,
        "invalid_ohlc_rows": invalid_ohlc_rows,
        "negative_volume_rows": negative_volume_rows,
        "zero_volume_rows": sum(value == 0 for value in volumes),
        "source_counts": source_counts,
        "latest_source": latest_source,
        "schema_types": {
            field: str(parquet_file.schema_arrow.field(field).type) for field in fields
        },
    }


def _probe_ticker(
    ticker: str,
    api_key: str,
    *,
    auth_scheme: AuthScheme,
    output_format: str,
) -> dict[str, object]:
    started = time.monotonic()
    signed_url, expires_at = _token_url(
        ticker,
        api_key,
        auth_scheme=auth_scheme,
        output_format=output_format,
    )
    response = _request(signed_url, limit=DAILY_RESPONSE_LIMIT)
    if response.status != 200:
        raise ProbeError(f"daily_status:{ticker}:{response.status}")
    if output_format == "csv":
        result = _summarize_daily_csv(ticker, response)
    else:
        result = _summarize_daily_parquet(ticker, response)
    result["duration_ms"] = round((time.monotonic() - started) * 1000)
    result["signed_url_expires_at_present"] = expires_at != "unknown"
    return result


def main() -> int:
    try:
        api_key = _validated_key()

        unauthenticated = _request(
            f"{API_BASE}/download-token/SPY?timeframe=daily&format=csv&version=clean",
            limit=TOKEN_RESPONSE_LIMIT,
        )
        public_spy_status, _ = _public_symbol_status("SPY")
        public_xlre_status, _ = _public_symbol_status(EXPECTED_MISSING)

        token_matrix: dict[str, dict[str, object]] = {}
        auth_schemes: tuple[AuthScheme, ...] = ("x_api_key", "bearer")
        for auth_scheme in auth_schemes:
            for timeframe, output_format in (
                ("daily", "csv"),
                ("daily", "parquet"),
                ("1min", "parquet"),
            ):
                matrix_key = f"{auth_scheme}:{timeframe}:{output_format}"
                response = _token_request(
                    "SPY",
                    api_key,
                    auth_scheme=auth_scheme,
                    timeframe=timeframe,
                    output_format=output_format,
                )
                token_matrix[matrix_key] = {
                    "status": response.status,
                    "content_type": response.content_type,
                }

        selected_contract: tuple[AuthScheme, str] | None = next(
            (
                (auth_scheme, output_format)
                for auth_scheme in auth_schemes
                for output_format in ("csv", "parquet")
                if token_matrix[f"{auth_scheme}:daily:{output_format}"]["status"] == 200
            ),
            None,
        )
        selected_auth = selected_contract[0] if selected_contract else None
        selected_format = selected_contract[1] if selected_contract else None
        authenticated_xlre = _token_request(
            EXPECTED_MISSING,
            api_key,
            auth_scheme=selected_auth or "x_api_key",
            timeframe="daily",
            output_format=selected_format or "parquet",
        )

        results: list[dict[str, object]] = []
        failures: list[str] = []
        if selected_auth is None or selected_format is None:
            failures.append("no_working_daily_token_contract")
        else:
            for ticker in REQUESTED_TICKERS:
                try:
                    results.append(
                        _probe_ticker(
                            ticker,
                            api_key,
                            auth_scheme=selected_auth,
                            output_format=selected_format,
                        )
                    )
                except ProbeError as exc:
                    failures.append(str(exc))

        comparable_latest_dates = sorted({item["latest_date"] for item in results})
        evidence = {
            "probe": "u145-hf-step0",
            "endpoint_contract": (
                f"download-token_then_signed_daily_{selected_format}"
                if selected_format
                else "unresolved"
            ),
            "selected_auth_header": selected_auth,
            "selected_format": selected_format,
            "token_contract_matrix": token_matrix,
            "version": "clean",
            "requested_count": len(REQUESTED_TICKERS),
            "successful_count": len(results),
            "expected_missing": {
                "ticker": EXPECTED_MISSING,
                "public_symbol_status": public_xlre_status,
                "authenticated_download_token_status": authenticated_xlre.status,
                "authenticated_content_type": authenticated_xlre.content_type,
            },
            "public_spy_status": public_spy_status,
            "unauthenticated_download_token_status": unauthenticated.status,
            "unauthenticated_content_type": unauthenticated.content_type,
            "latest_dates": comparable_latest_dates,
            "total_download_bytes": sum(int(item["size_bytes"]) for item in results),
            "tickers": results,
            "raw_payload_retained": False,
            "signed_url_logged": False,
            "failures": failures,
        }
        print(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2))

        if authenticated_xlre.status != 404:
            raise ProbeError(f"xlre_contract:{authenticated_xlre.status}")
        if unauthenticated.status != 401:
            raise ProbeError(f"unauthenticated_contract:{unauthenticated.status}")
        if failures:
            raise ProbeError(f"requested_ticker_failures:{len(failures)}")
        if len(comparable_latest_dates) != 1:
            raise ProbeError("same_as_of_contract")
        return 0
    except ProbeError as exc:
        print(f"HF source probe failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
