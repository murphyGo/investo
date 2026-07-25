"""Yahoo Finance v8 chart endpoint — 1-year daily-bar history fetcher (u49).

This is NOT a registered source adapter. It is a sibling helper that
:mod:`investo.briefing.market_anchor` consumes via the orchestrator
to compute deterministic market facts (ATH / 52-week range / MTD /
YTD / volume z-score) for the brief header.

Why a separate caller API?
~~~~~~~~~~~~~~~~~~~~~~~~~~

The u46 stooq-price-primary unit's plan suggested extending the
Stooq endpoint with ``&d1=...&d2=...`` for multi-row history. That
suggestion does not survive contact with the live API as of
2026-05-10:

* ``https://stooq.com/q/d/l/`` (the bulk-history endpoint) returns
  an ``apikey`` gate page for unauthenticated requests.
* ``https://stooq.com/q/l/`` (the single-day endpoint used by the
  ``stooq-price`` adapter) ignores the ``d1`` / ``d2`` query params
  and always emits the most recent trading day.

Yahoo Finance's v8 chart endpoint with ``interval=1d&range=1y`` returns
~250 daily bars per equity / index and ~365 for crypto. Since u138,
this module retains the history basket/concurrency API while delegating
the request, User-Agent, and payload parser to ``sources._yahoo_chart``.
The registered ``yfinance-price`` adapter reuses that same shared path.

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
import logging
import os
from collections.abc import Mapping, Sequence
from typing import Any, Final

import httpx

from investo.models.market_anchor import OHLCRow
from investo.sources._config import parse_symbol_list
from investo.sources._yahoo_chart import fetch_chart_rows, parse_chart_rows
from investo.sources.protocol import SourceFetchError
from investo.sources.yfinance import DEFAULT_CRITICAL_TICKERS

_logger = logging.getLogger(__name__)

_ENV_TICKERS: Final[str] = "INVESTO_YFINANCE_HISTORY_TICKERS"
_ENV_CONCURRENCY: Final[str] = "INVESTO_YFINANCE_HISTORY_CONCURRENCY"
_DEFAULT_CONCURRENCY: Final[int] = 2

# Default ticker basket covers every u138 critical snapshot fallback plus
# the two crypto histories retained for the u49 anchor/chart surfaces.
DEFAULT_HISTORY_TICKERS: Final[tuple[str, ...]] = (
    *DEFAULT_CRITICAL_TICKERS,
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
    return await fetch_chart_rows(
        client,
        ticker,
        range_param=range_param,
        interval=interval,
    )


def parse_chart_payload(
    payload: Mapping[str, Any],
    *,
    ticker: str,
) -> tuple[OHLCRow, ...]:
    """Compatibility wrapper around the shared u138 Yahoo parser."""

    return parse_chart_rows(payload, ticker=ticker, source_name="yfinance-history")


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
