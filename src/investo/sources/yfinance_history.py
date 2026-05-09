"""Yahoo Finance v8 chart endpoint — 1-year daily-bar history fetcher (u49).

This is NOT a registered source adapter. It is a sibling helper that
:mod:`investo.briefing.market_anchor` consumes via the orchestrator
to compute deterministic market facts (ATH / 52-week range / MTD /
YTD / volume z-score) for the brief header.

Why a separate module (vs extending ``stooq_price`` or ``yfinance``)?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The u46 stooq-price-primary unit's plan suggested extending the
Stooq endpoint with ``&d1=...&d2=...`` for multi-row history. That
suggestion does not survive contact with the live API as of
2026-05-10:

* ``https://stooq.com/q/d/l/`` (the bulk-history endpoint) returns
  an ``apikey`` gate page for unauthenticated requests.
* ``https://stooq.com/q/l/`` (the single-day endpoint used by the
  ``stooq-price`` adapter) ignores the ``d1`` / ``d2`` query params
  and always emits the most recent trading day.

Yahoo Finance's v8 chart endpoint with ``interval=1d&range=1y`` is
the next free option: ~250 daily bars per equity / index, ~365 for
crypto, no auth, no apikey, JSON response. The existing
``yfinance-price`` adapter (u1 / u46) already speaks the same backend
for 5-day snapshots; this module is its 1-year sibling.

Caveat (R10 + GHA reality)
~~~~~~~~~~~~~~~~~~~~~~~~~~

The u46 cron-runner observation is that GitHub Actions' shared-IP
space draws ``HTTP 429 Too Many Requests`` from Yahoo Finance. That
remains a runtime risk for *this* fetcher too. The contract is
graceful degrade: a 429 / 5xx / timeout for a given ticker yields no
``OHLCRow`` for that ticker, and :mod:`investo.briefing.market_anchor`
emits a shorter header line (or omits it entirely when zero anchors
land). Tests pin the graceful-degrade branch.

Pins
~~~~

* **R3** — uses the injected ``httpx.AsyncClient``; never builds its
  own.
* **R6** — per-ticker errors are isolated via ``asyncio.gather
  (return_exceptions=True)``; ``SourceFetchError`` lands as "no
  history for this ticker" and sibling tickers continue normally.
* **R8** — output is :class:`investo.briefing.market_anchor.OHLCRow`,
  not :class:`investo.models.NormalizedItem`. The data is structurally
  multi-row time series, which a flat ``raw_metadata: dict[str, str]``
  cannot carry — :class:`OHLCRow` is the right shape.
* **R10** — recorded fixtures live in
  ``tests/unit/sources/fixtures/api/yfinance-history/``; tests use
  ``httpx.MockTransport`` to replay them byte-equal.
* **R11** (window-relaxation) — history fetch ignores ``FetchWindow``
  entirely; the trailing year is always-on.
* **R12** — ``INVESTO_YFINANCE_HISTORY_TICKERS`` env-var override
  via :func:`investo.sources._config.parse_symbol_list`.
* **R13** — Yahoo has no auth surface; no secrets to redact.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Final
from urllib.parse import quote

import httpx

from investo.briefing.market_anchor import OHLCRow
from investo.sources._config import parse_symbol_list
from investo.sources._retry import retry_get
from investo.sources.protocol import SourceFetchError

_logger = logging.getLogger(__name__)

_BASE_URL: Final[str] = "https://query2.finance.yahoo.com/v8/finance/chart"
_USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)
_ENV_TICKERS: Final[str] = "INVESTO_YFINANCE_HISTORY_TICKERS"
_ENV_CONCURRENCY: Final[str] = "INVESTO_YFINANCE_HISTORY_CONCURRENCY"
_DEFAULT_CONCURRENCY: Final[int] = 2

# Default ticker basket — mirrors the ``stooq-price`` / ``yfinance-
# price`` snapshot adapters so the anchor line covers the same set
# the snapshot cards already speak about.
DEFAULT_HISTORY_TICKERS: Final[tuple[str, ...]] = (
    "^GSPC",
    "^IXIC",
    "^DJI",
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "META",
    "TSLA",
    "BTC-USD",
    "ETH-USD",
)


async def fetch_price_history(
    client: httpx.AsyncClient,
    *,
    tickers: Sequence[str] | None = None,
    range_param: str = "1y",
    interval: str = "1d",
) -> dict[str, tuple[OHLCRow, ...]]:
    """Fetch trailing daily-bar history for a basket of tickers.

    Parameters
    ----------
    client:
        Injected per FD R3. Tests pass a transport bound to recorded
        fixtures (``httpx.MockTransport``) so this function never
        hits the network in CI.
    tickers:
        Explicit basket. ``None`` (production default) reads
        ``INVESTO_YFINANCE_HISTORY_TICKERS`` and falls back to
        :data:`DEFAULT_HISTORY_TICKERS`.
    range_param:
        Yahoo Finance ``range`` parameter. ``"1y"`` covers the
        anchor module's 252-day window with margin. Test seam.
    interval:
        Yahoo Finance ``interval`` parameter. ``"1d"`` is the only
        value the anchor module supports (intraday is out of scope
        per u49 plan §Out of scope). Test seam.

    Returns
    -------
    dict[str, tuple[OHLCRow, ...]]
        Per-ticker history, ordered ascending by ``trading_date``.
        Tickers whose fetch fails (404 / 429 / 5xx after retries
        / malformed body) are *omitted* — callers must treat the
        absence of a key as "no history available for this ticker".
        Empty input ⇒ empty dict.
    """
    basket = (
        tuple(tickers)
        if tickers is not None
        else parse_symbol_list(_ENV_TICKERS, DEFAULT_HISTORY_TICKERS)
    )
    if not basket:
        return {}
    concurrency = _parse_concurrency()
    semaphore = asyncio.Semaphore(concurrency)
    results = await asyncio.gather(
        *(
            _fetch_one_limited(client, ticker, semaphore, range_param, interval)
            for ticker in basket
        ),
        return_exceptions=True,
    )
    out: dict[str, tuple[OHLCRow, ...]] = {}
    for ticker, result in zip(basket, results, strict=True):
        if isinstance(result, tuple):
            out[ticker] = result
        elif isinstance(result, SourceFetchError):
            _logger.info(
                "[yfinance-history] %s fetch failed (transient=%s) — skipped",
                ticker,
                result.transient,
            )
            continue
        elif isinstance(result, BaseException):
            # Programmer errors propagate so the orchestrator stage-
            # level guard sees them.
            raise result
    return out


async def _fetch_one_limited(
    client: httpx.AsyncClient,
    ticker: str,
    semaphore: asyncio.Semaphore,
    range_param: str,
    interval: str,
) -> tuple[OHLCRow, ...]:
    async with semaphore:
        return await _fetch_one(client, ticker, range_param, interval)


async def _fetch_one(
    client: httpx.AsyncClient,
    ticker: str,
    range_param: str,
    interval: str,
) -> tuple[OHLCRow, ...]:
    url = f"{_BASE_URL}/{quote(ticker, safe='')}"
    response = await retry_get(
        client,
        url,
        source_name="yfinance-history",
        params={"interval": interval, "range": range_param},
        headers={"User-Agent": _USER_AGENT},
    )
    body = response.text
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SourceFetchError(
            "yfinance-history",
            f"malformed JSON for {ticker}: {exc}",
            transient=False,
        ) from exc
    return parse_chart_payload(payload, ticker=ticker)


def parse_chart_payload(
    payload: Mapping[str, Any],
    *,
    ticker: str,
) -> tuple[OHLCRow, ...]:
    """Parse a Yahoo Finance v8 chart JSON body into ordered OHLCV rows.

    Public for unit tests — they exercise the parser directly with
    recorded fixture bytes, separate from the HTTP path.

    Returns an empty tuple when the payload is empty / shape-broken.
    Raises :class:`SourceFetchError` only when the response body
    declares an explicit error (e.g. ``chart.error.code`` is set).
    """
    chart = payload.get("chart") if isinstance(payload, Mapping) else None
    if not isinstance(chart, Mapping):
        return ()
    error = chart.get("error")
    if isinstance(error, Mapping):
        code = error.get("code")
        description = error.get("description") or error.get("message") or "unknown"
        raise SourceFetchError(
            "yfinance-history",
            f"chart error code={code} for {ticker}: {description}",
            transient=False,
        )
    result_list = chart.get("result")
    if not isinstance(result_list, list) or not result_list:
        return ()
    block = result_list[0]
    if not isinstance(block, Mapping):
        return ()
    timestamps = block.get("timestamp")
    indicators = block.get("indicators")
    if not isinstance(timestamps, list) or not isinstance(indicators, Mapping):
        return ()
    quote_list = indicators.get("quote")
    if not isinstance(quote_list, list) or not quote_list:
        return ()
    quote_block = quote_list[0]
    if not isinstance(quote_block, Mapping):
        return ()
    opens = quote_block.get("open") or []
    highs = quote_block.get("high") or []
    lows = quote_block.get("low") or []
    closes = quote_block.get("close") or []
    volumes = quote_block.get("volume") or []

    rows: list[OHLCRow] = []
    for idx, ts in enumerate(timestamps):
        if not isinstance(ts, (int, float)):
            continue
        # All five quote arrays should align with timestamp; defend
        # against shape drift by skipping rows where any required
        # field is missing.
        try:
            open_ = opens[idx]
            high = highs[idx]
            low = lows[idx]
            close = closes[idx]
        except IndexError:
            continue
        if open_ is None or high is None or low is None or close is None:
            continue
        try:
            volume_raw = volumes[idx]
        except IndexError:
            volume_raw = None
        trading_date = datetime.fromtimestamp(int(ts), tz=UTC).date()
        try:
            row = OHLCRow(
                trading_date=trading_date,
                open=Decimal(str(open_)),
                high=Decimal(str(high)),
                low=Decimal(str(low)),
                close=Decimal(str(close)),
                volume=Decimal(str(volume_raw)) if volume_raw is not None else None,
            )
        except (TypeError, ValueError):
            continue
        rows.append(row)
    return tuple(rows)


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


__all__ = [
    "DEFAULT_HISTORY_TICKERS",
    "fetch_price_history",
    "parse_chart_payload",
]
