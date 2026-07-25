"""Shared Yahoo Finance chart request and parser contract (u138)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Final
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from investo.models.market_anchor import OHLCRow
from investo.sources._parse import parse_json_response
from investo.sources._retry import retry_get
from investo.sources.protocol import SourceFetchError

QUERY_HOST: Final[str] = "https://query2.finance.yahoo.com/v8/finance/chart"
USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)


@dataclass(frozen=True, slots=True)
class YahooChartData:
    """Normalized rows plus the upstream previous-close fallback."""

    rows: tuple[OHLCRow, ...]
    chart_previous_close: Decimal | None


async def fetch_chart_rows(
    client: httpx.AsyncClient,
    ticker: str,
    *,
    range_param: str = "1y",
    interval: str = "1d",
) -> tuple[OHLCRow, ...]:
    """Fetch ascending Yahoo daily rows through the shared query2 path."""

    data = await fetch_chart_data(
        client,
        ticker,
        range_param=range_param,
        interval=interval,
    )
    return data.rows


async def fetch_chart_data(
    client: httpx.AsyncClient,
    ticker: str,
    *,
    range_param: str = "1y",
    interval: str = "1d",
    source_name: str = "yahoo-chart",
) -> YahooChartData:
    """Fetch and normalize one chart response without caller-specific rendering."""

    url = f"{QUERY_HOST}/{quote(ticker, safe='')}"
    response = await retry_get(
        client,
        url,
        source_name=source_name,
        params={"interval": interval, "range": range_param},
        headers={"User-Agent": USER_AGENT},
    )
    payload = parse_json_response(
        response,
        source_name=source_name,
        message=f"malformed JSON for {ticker}",
    )
    if not isinstance(payload, Mapping):
        return YahooChartData(rows=(), chart_previous_close=None)
    return parse_chart_data(payload, ticker=ticker, source_name=source_name)


def parse_chart_rows(
    payload: Mapping[str, Any],
    *,
    ticker: str,
    source_name: str = "yahoo-chart",
) -> tuple[OHLCRow, ...]:
    """Parse ascending rows while preserving explicit chart errors."""

    return parse_chart_data(payload, ticker=ticker, source_name=source_name).rows


def parse_chart_data(
    payload: Mapping[str, Any],
    *,
    ticker: str,
    source_name: str = "yahoo-chart",
) -> YahooChartData:
    """Normalize one Yahoo chart payload and skip malformed individual rows."""

    chart = payload.get("chart")
    if not isinstance(chart, Mapping):
        return YahooChartData(rows=(), chart_previous_close=None)

    error = chart.get("error")
    if error is not None:
        code: object = "unknown"
        description: object = error
        if isinstance(error, Mapping):
            code = error.get("code") or "unknown"
            description = error.get("description") or error.get("message") or "unknown"
        raise SourceFetchError(
            source_name,
            f"chart error code={code} for {ticker}: {description}",
            transient=False,
        )

    result_list = chart.get("result")
    if not isinstance(result_list, list) or not result_list:
        return YahooChartData(rows=(), chart_previous_close=None)
    block = result_list[0]
    if not isinstance(block, Mapping):
        return YahooChartData(rows=(), chart_previous_close=None)

    previous_close = _parse_previous_close(block.get("meta"))
    timestamps = block.get("timestamp")
    indicators = block.get("indicators")
    if not isinstance(timestamps, list) or not isinstance(indicators, Mapping):
        return YahooChartData(rows=(), chart_previous_close=previous_close)
    quote_list = indicators.get("quote")
    if not isinstance(quote_list, list) or not quote_list:
        return YahooChartData(rows=(), chart_previous_close=previous_close)
    quote_block = quote_list[0]
    if not isinstance(quote_block, Mapping):
        return YahooChartData(rows=(), chart_previous_close=previous_close)

    opens = _sequence_or_empty(quote_block.get("open"))
    highs = _sequence_or_empty(quote_block.get("high"))
    lows = _sequence_or_empty(quote_block.get("low"))
    closes = _sequence_or_empty(quote_block.get("close"))
    volumes = _sequence_or_empty(quote_block.get("volume"))

    rows: list[OHLCRow] = []
    for index, timestamp in enumerate(timestamps):
        row = _parse_row(
            timestamp=timestamp,
            open_=_value_at(opens, index),
            high=_value_at(highs, index),
            low=_value_at(lows, index),
            close=_value_at(closes, index),
            volume=_value_at(volumes, index),
        )
        if row is not None:
            rows.append(row)
    rows.sort(key=lambda row: row.trading_date)
    return YahooChartData(rows=tuple(rows), chart_previous_close=previous_close)


def _sequence_or_empty(value: object) -> Sequence[object]:
    if isinstance(value, list | tuple):
        return value
    return ()


def _value_at(values: Sequence[object], index: int) -> object | None:
    try:
        return values[index]
    except IndexError:
        return None


def _parse_row(
    *,
    timestamp: object,
    open_: object,
    high: object,
    low: object,
    close: object,
    volume: object,
) -> OHLCRow | None:
    if not isinstance(timestamp, int | float):
        return None
    if any(value is None for value in (open_, high, low, close)):
        return None
    try:
        trading_date = datetime.fromtimestamp(int(timestamp), tz=UTC).date()
        parsed = OHLCRow(
            trading_date=trading_date,
            open=Decimal(str(open_)),
            high=Decimal(str(high)),
            low=Decimal(str(low)),
            close=Decimal(str(close)),
            volume=Decimal(str(volume)) if volume is not None else None,
        )
    except (InvalidOperation, OSError, OverflowError, TypeError, ValidationError, ValueError):
        return None
    required = (parsed.open, parsed.high, parsed.low, parsed.close)
    if not all(value.is_finite() for value in required):
        return None
    if parsed.volume is not None and not parsed.volume.is_finite():
        return None
    return parsed


def _parse_previous_close(meta: object) -> Decimal | None:
    if not isinstance(meta, Mapping):
        return None
    value = meta.get("chartPreviousClose")
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


__all__ = [
    "QUERY_HOST",
    "USER_AGENT",
    "YahooChartData",
    "fetch_chart_data",
    "fetch_chart_rows",
    "parse_chart_data",
    "parse_chart_rows",
]
