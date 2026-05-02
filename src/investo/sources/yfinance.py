"""Yahoo Finance v8 chart adapter — US equity / index price snapshots.

Implements the algorithm from FD L6.2 (extension 2026-05-01). Fetches
prior-trading-day OHLCV per ticker and emits one
:class:`NormalizedItem` per ticker with `category="price"`.

Design choices (audit log 2026-05-01):

* **Direct httpx GET**, not the python ``yfinance`` library (TS-10).
  We hit the same v8 endpoint the library hits internally; the
  library's sync-only ``requests.Session`` would defeat the shared
  ``httpx.AsyncClient`` injection (FD R3).
* **One HTTP per ticker**, fired concurrently via ``asyncio.gather``
  so worst-case wall-clock ≈ slowest single ticker.
* **Per-ticker isolation**: a 4xx on one ticker does not fail the
  adapter — the failed ticker contributes nothing, sibling tickers
  produce items normally. This is *intra*-adapter isolation, parallel
  to the aggregator's *inter*-adapter R6 isolation.
* **R7 window relaxation** (FD L6.2 / R11): the adapter emits the
  most recent valid trading day in the 5-day response regardless of
  strict R7 membership. KST Monday and Saturday cron fires after a US
  market weekend — Friday's close lies outside the strict R7 window
  for those targets, and strict filtering would drop all yfinance
  data on those days.

Pins (extension 2026-05-01):

* AC-5.5 — env-var override via :func:`investo.sources._config.parse_symbol_list`
* R11 — `published_at` = market close (16:00 ET) as UTC tz-aware via
  ``zoneinfo("America/New_York")``; DST handled automatically
* R12 — `INVESTO_YFINANCE_TICKERS` env-var override
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any, ClassVar
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN, format_float, format_int, parse_symbol_list
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_NY = ZoneInfo("America/New_York")
_ENV_TICKERS = "INVESTO_YFINANCE_TICKERS"


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
    )

    _BASE_URL: ClassVar[str] = "https://query1.finance.yahoo.com/v8/finance/chart"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,  # window unused — yfinance applies R7-relaxation per FD L6.2
    ) -> list[NormalizedItem]:
        tickers = parse_symbol_list(_ENV_TICKERS, self._DEFAULT_TICKERS)
        results = await asyncio.gather(
            *(self._fetch_one(client, ticker) for ticker in tickers),
            return_exceptions=True,
        )
        items: list[NormalizedItem] = []
        for result in results:
            if isinstance(result, NormalizedItem):
                items.append(result)
            elif isinstance(result, SourceFetchError):
                # Per-ticker source-side failure (404 ticker, 5xx after retries,
                # malformed body, scheme-issue URL). Per-ticker isolation: log
                # silently and let sibling tickers continue. Aggregator-level
                # R6 isolation only covers whole-adapter SourceFetchError;
                # this is *intra*-adapter isolation between tickers.
                continue
            elif isinstance(result, BaseException):
                # Programmer error escapes — re-raise so the orchestrator's
                # stage-level guard sees it and the run goes FAILED.
                raise result
        return items

    async def _fetch_one(self, client: httpx.AsyncClient, ticker: str) -> NormalizedItem | None:
        url = f"{self._BASE_URL}/{quote(ticker, safe='')}"
        response = await retry_get(
            client,
            url,
            source_name=self.name,
            params={"interval": "1d", "range": "5d"},
        )
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"malformed JSON for {ticker}: {exc}",
                transient=False,
                cause=exc,
            ) from exc

        chart = payload.get("chart") if isinstance(payload, dict) else None
        if not isinstance(chart, dict):
            raise SourceFetchError(
                source_name=self.name,
                message=f"missing 'chart' object for {ticker}",
                transient=False,
            )
        error = chart.get("error")
        if error is not None:
            # Yahoo's documented not-found shape — terminal for this ticker.
            description = error.get("description") if isinstance(error, dict) else str(error)
            raise SourceFetchError(
                source_name=self.name,
                message=f"{ticker}: {description}",
                transient=False,
            )
        result_list = chart.get("result")
        if not isinstance(result_list, list) or not result_list:
            raise SourceFetchError(
                source_name=self.name,
                message=f"empty chart.result for {ticker}",
                transient=False,
            )
        result = result_list[0]
        if not isinstance(result, dict):
            raise SourceFetchError(
                source_name=self.name,
                message=f"chart.result[0] is not an object for {ticker}",
                transient=False,
            )

        timestamps = result.get("timestamp")
        indicators = result.get("indicators")
        meta = result.get("meta")
        if (
            not isinstance(timestamps, list)
            or not isinstance(indicators, dict)
            or not isinstance(meta, dict)
        ):
            return None
        quote_list = indicators.get("quote")
        if not isinstance(quote_list, list) or not quote_list:
            return None
        quote_obj = quote_list[0]
        if not isinstance(quote_obj, dict):
            return None

        opens = quote_obj.get("open") or []
        highs = quote_obj.get("high") or []
        lows = quote_obj.get("low") or []
        closes = quote_obj.get("close") or []
        volumes = quote_obj.get("volume") or []
        n = len(timestamps)
        if not (len(opens) == len(highs) == len(lows) == len(closes) == len(volumes) == n):
            # Inconsistent array lengths — treat as malformed for this ticker.
            return None

        # Iterate from the most recent day backward; pick the first day
        # where every OHLC value is non-null. Volume may be 0 (an index
        # like ^VIX); we only require it to be non-null.
        latest_idx = self._find_latest_valid(opens, highs, lows, closes, volumes, n)
        if latest_idx is None:
            return None

        # Prior-day close for pct: prefer the most recent valid day
        # before ``latest_idx``; fall back to ``meta.chartPreviousClose``.
        prev_close = self._find_prior_close(closes, latest_idx, meta)

        ts_epoch = timestamps[latest_idx]
        if not isinstance(ts_epoch, (int, float)):
            return None
        try:
            published_at = self._resolve_close_timestamp(int(ts_epoch))
        except (OverflowError, OSError, ValueError):
            return None

        open_ = float(opens[latest_idx])
        high = float(highs[latest_idx])
        low = float(lows[latest_idx])
        close = float(closes[latest_idx])
        volume = int(volumes[latest_idx])
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
        }

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
    def _find_latest_valid(
        opens: list[Any],
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        volumes: list[Any],
        n: int,
    ) -> int | None:
        for idx in range(n - 1, -1, -1):
            if (
                opens[idx] is not None
                and highs[idx] is not None
                and lows[idx] is not None
                and closes[idx] is not None
                and volumes[idx] is not None
            ):
                return idx
        return None

    @staticmethod
    def _find_prior_close(closes: list[Any], latest_idx: int, meta: dict[str, Any]) -> float:
        for idx in range(latest_idx - 1, -1, -1):
            if closes[idx] is not None:
                return float(closes[idx])
        prev = meta.get("chartPreviousClose")
        if isinstance(prev, (int, float)):
            return float(prev)
        return 0.0

    @staticmethod
    def _resolve_close_timestamp(epoch_seconds: int) -> datetime:
        """Resolve a session-start epoch to that day's 16:00 ET as UTC.

        ``timestamps[i]`` from Yahoo's v8 chart response is the regular
        session start (9:30 ET) for trading day ``i``. We convert to NY
        local time (DST handled by ``zoneinfo``), pin to 16:00 ET, and
        return as UTC. This yields the close timestamp R11 requires
        and is robust against future API changes that might tweak the
        session-start offset.
        """

        ny_local = datetime.fromtimestamp(epoch_seconds, tz=_NY)
        close_local = ny_local.replace(hour=16, minute=0, second=0, microsecond=0)
        return close_local.astimezone(UTC)
