"""Yahoo Finance v8 chart adapter — US equity / index price snapshots.

Implements the algorithm from FD L6.2 (extension 2026-05-01). Fetches
prior-trading-day OHLCV per ticker and emits one
:class:`NormalizedItem` per ticker with `category="price"`.

Design choices (audit log 2026-05-01):

* **Direct httpx GET**, not the python ``yfinance`` library (TS-10).
  We hit the same v8 endpoint the library hits internally; the
  library's sync-only ``requests.Session`` would defeat the shared
  ``httpx.AsyncClient`` injection (FD R3).
* **One HTTP per ticker**, with the critical basket completed before
  the enrichment basket starts. Each phase is concurrency-bounded.
* **Per-ticker isolation**: a 4xx on one ticker does not fail the
  adapter — the failed ticker contributes nothing, sibling tickers
  produce items normally. This is *intra*-adapter isolation, parallel
  to the aggregator's *inter*-adapter R6 isolation.
* **R7 window relaxation** (FD L6.2 / R11): the adapter emits the
  most recent valid trading day in the 1-year response regardless of
  strict R7 membership. KST Monday and Saturday cron fires after a US
  market weekend — Friday's close lies outside the strict R7 window
  for those targets, and strict filtering would drop all yfinance
  data on those days.

Pins (extension 2026-05-01):

* AC-5.5 — env-var override via :func:`investo.sources._config.parse_symbol_list`
* R11 — `published_at` = market close (16:00 ET) as UTC tz-aware via
  ``zoneinfo("America/New_York")``; DST handled automatically
* R12 — `INVESTO_YFINANCE_TICKERS` env-var override
* u138 — shared query2/1y chart parser plus critical-first enrichment
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Sequence
from datetime import UTC, date, datetime, time
from typing import ClassVar
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN, format_float, format_int, parse_symbol_list
from investo.sources._core_fact_map import core_fact_for_ticker, core_fact_metadata_key
from investo.sources._fanout import gather_with_error_isolation
from investo.sources._registry import register
from investo.sources._window import FetchWindow
from investo.sources._yahoo_chart import fetch_chart_data

_NY = ZoneInfo("America/New_York")
_ENV_TICKERS = "INVESTO_YFINANCE_TICKERS"
_ENV_ENRICHMENT_TICKERS = "INVESTO_YFINANCE_ENRICHMENT_TICKERS"
_ENV_CONCURRENCY = "INVESTO_YFINANCE_CONCURRENCY"
_DEFAULT_CONCURRENCY = 2


@register
class YFinancePriceAdapter:
    """Adapter for the Yahoo Finance v8 chart endpoint (FD L6.2)."""

    name: ClassVar[str] = "yfinance-price"
    category: ClassVar[Category] = "price"

    _DEFAULT_TICKERS: ClassVar[tuple[str, ...]] = (
        "^GSPC",
        "^IXIC",
        "^DJI",
        "^VIX",
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "NVDA",
        "META",
        "TSLA",
        # u53 — Brent and Russell 2000 remain part of the critical basket.
        # u138 moves the former Stooq-only macro/ETF set to the second phase.
        "BZ=F",
        "^RUT",
    )
    _DEFAULT_ENRICHMENT_TICKERS: ClassVar[tuple[str, ...]] = (
        "XLK",
        "XLE",
        "XLF",
        "XLV",
        "XLY",
        "XLI",
        "SMH",
        "IWM",
        "TLT",
        "GLD",
        "USO",
        "UUP",
        "CL=F",
        "GC=F",
    )

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,  # window unused — yfinance applies R7-relaxation per FD L6.2
    ) -> list[NormalizedItem]:
        critical_tickers = parse_symbol_list(_ENV_TICKERS, self._DEFAULT_TICKERS)
        concurrency = _parse_concurrency()
        semaphore = asyncio.Semaphore(concurrency)
        critical_items = await self._fetch_tickers(
            client,
            critical_tickers,
            semaphore,
        )
        if not critical_items:
            return []

        configured_enrichment = parse_symbol_list(
            _ENV_ENRICHMENT_TICKERS,
            self._DEFAULT_ENRICHMENT_TICKERS,
        )
        enrichment_tickers = _unique_tickers(
            configured_enrichment,
            excluded=frozenset(critical_tickers),
        )
        enrichment_items = await self._fetch_tickers(
            client,
            enrichment_tickers,
            semaphore,
        )
        return [*critical_items, *enrichment_items]

    async def _fetch_tickers(
        self,
        client: httpx.AsyncClient,
        tickers: Sequence[str],
        semaphore: asyncio.Semaphore,
    ) -> list[NormalizedItem]:
        # Per-ticker isolation: a failed ticker contributes nothing and
        # never removes successful siblings within the same phase.
        return await gather_with_error_isolation(
            (self._fetch_one_limited(client, ticker, semaphore) for ticker in tickers),
            source_name=self.name,
        )

    async def _fetch_one_limited(
        self,
        client: httpx.AsyncClient,
        ticker: str,
        semaphore: asyncio.Semaphore,
    ) -> NormalizedItem | None:
        async with semaphore:
            return await self._fetch_one(client, ticker)

    async def _fetch_one(self, client: httpx.AsyncClient, ticker: str) -> NormalizedItem | None:
        chart = await fetch_chart_data(
            client,
            ticker,
            range_param="1y",
            interval="1d",
            source_name=self.name,
        )
        rows = chart.rows
        latest_idx = next(
            (index for index in range(len(rows) - 1, -1, -1) if rows[index].volume is not None),
            None,
        )
        if latest_idx is None:
            return None

        latest = rows[latest_idx]
        previous = rows[latest_idx - 1].close if latest_idx > 0 else chart.chart_previous_close
        prev_close = float(previous) if previous is not None else 0.0
        published_at = self._resolve_close_timestamp(latest.trading_date)
        open_ = float(latest.open)
        high = float(latest.high)
        low = float(latest.low)
        close = float(latest.close)
        volume = int(latest.volume) if latest.volume is not None else 0
        pct = ((close - prev_close) / prev_close * 100.0) if prev_close else 0.0

        title = f"{ticker} {close:,.2f} ({pct:+.2f}%)"
        summary = f"O:{open_:,.2f} H:{high:,.2f} L:{low:,.2f} C:{close:,.2f} V:{volume:,}"
        if len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        raw_metadata: dict[str, str] = {
            "ticker": ticker,
            "open": format_float(open_),
            "high": format_float(high),
            "low": format_float(low),
            "close": format_float(close),
            "volume": format_int(volume),
            "prev_close": format_float(prev_close) if prev_close else "",
            "provenance": "query2-snapshot",
        }
        # u55 Step 1 — typed CoreFact stamp (see stooq-price for the
        # rationale). yfinance and stooq-price both emit the same fact
        # key for the same ticker; numeric_verify aggregates across the
        # whole candidate stream so duplicate stamps are idempotent.
        fact = core_fact_for_ticker(ticker)
        if fact is not None:
            raw_metadata[core_fact_metadata_key(fact)] = format_float(close)

        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=f"https://finance.yahoo.com/quote/{quote(ticker, safe='')}",
                published_at=published_at,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None

    @staticmethod
    def _resolve_close_timestamp(trading_date: date) -> datetime:
        """Resolve one Yahoo trading date to 16:00 New York in UTC."""

        close_local = datetime.combine(trading_date, time(16), tzinfo=_NY)
        return close_local.astimezone(UTC)


def _parse_concurrency() -> int:
    raw = os.environ.get(_ENV_CONCURRENCY, "").strip()
    if not raw:
        return _DEFAULT_CONCURRENCY
    try:
        parsed = int(raw)
    except ValueError:
        return _DEFAULT_CONCURRENCY
    if parsed < 1:
        return _DEFAULT_CONCURRENCY
    return parsed


def _unique_tickers(
    tickers: Sequence[str],
    *,
    excluded: frozenset[str],
) -> tuple[str, ...]:
    seen = set(excluded)
    unique: list[str] = []
    for ticker in tickers:
        if ticker in seen:
            continue
        seen.add(ticker)
        unique.append(ticker)
    return tuple(unique)
