"""Stooq daily-snapshot price adapter — primary US-equity / crypto price source.

Background (2026-05-09 GHA failure mode): the Yahoo Finance v8 chart
endpoint returns ``HTTP 429 Too Many Requests`` for every ticker when
called from the GitHub Actions shared-runner IP space (AWS US-east).
This is an IP-level rate-limit and cannot be tuned away in adapter
code. Stooq's public CSV endpoint is the chosen primary replacement —
unauthenticated, unmetered, globally reachable, and stable.

The ``yfinance-price`` adapter remains registered alongside this one;
both are listed in the same segment allow-lists, so the orchestrator
gets the union of their items in the candidate stream. Source-level
failover (stooq fail → yfinance trigger) is *not* implemented here —
that lives in a future unit; today's contract is just "more sources →
higher confidence the price segment lands non-empty".

Endpoint
~~~~~~~~

URL template:: ``https://stooq.com/q/l/?s={symbol}&i=d&h=1&f=sd2t2ohlcv``

* ``i=d`` — daily interval
* ``h=1`` — emit a header row (``Symbol,Date,Time,Open,High,Low,Close,Volume``)
* ``f=sd2t2ohlcv`` — column format token: Symbol, Date (ISO ``YYYY-MM-DD``),
  Time (``HH:MM:SS`` Stooq local), OHLCV. Without this token Stooq emits
  a compact ``YYYYMMDD`` / ``HHMMSS`` form which is harder to parse
  reliably across symbols.

Stooq returns ``200 OK`` with a placeholder ``N/D`` row for unknown or
unsupported symbols (e.g. ``^VIX``, ``^RUT`` — Stooq does not carry the
CBOE / Russell index series). The adapter skips placeholder rows
silently per FD-style "intra-adapter isolation" — sibling tickers must
not be affected.

Pins
~~~~

* **R3** — uses the injected ``httpx.AsyncClient``; never builds its own.
* **R6** — per-ticker errors are isolated; whole-adapter failure raises
  :class:`SourceFetchError` only when *every* ticker fetch raises a
  source-side error (handled by the :class:`asyncio.gather`
  ``return_exceptions=True`` pattern).
* **R8** — :class:`NormalizedItem` shape: ``source_name="stooq-price"``,
  ``category="price"``, ``raw_metadata`` is a flat ``dict[str, str]``.
* **R9** — idempotent. ``published_at`` is derived from the CSV ``Date``
  column pinned to 16:00 ET (US session close); we do not call
  ``datetime.now``.
* **R11** (window-relaxation, parallel to ``yfinance``) — Stooq returns
  the most recent trading day. We accept it regardless of strict R7
  membership; the briefing prefers a slightly stale snapshot to a
  segment with zero price items.
* **R12** — ``INVESTO_STOOQ_TICKERS`` env-var override via
  :func:`investo.sources._config.parse_symbol_list`.
* **R13** — Stooq has no auth surface; no secrets to redact.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
from datetime import UTC, datetime, time
from typing import ClassVar, Final
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN, format_float, format_int, parse_symbol_list
from investo.sources._core_fact_map import core_fact_for_ticker, core_fact_metadata_key
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_logger = logging.getLogger(__name__)

_NY = ZoneInfo("America/New_York")
_ENV_TICKERS = "INVESTO_STOOQ_TICKERS"
_ENV_CONCURRENCY = "INVESTO_STOOQ_CONCURRENCY"
_DEFAULT_CONCURRENCY = 3
_USER_AGENT = "Investo/1.0 (https://murphygo.github.io/investo)"
_NOT_AVAILABLE = "N/D"


# Canonical map: input ticker (yfinance-style, what the rest of the
# pipeline already speaks) → Stooq symbol. Keeping the *input* keys in
# yfinance form means the env-var override in
# ``INVESTO_STOOQ_TICKERS`` accepts the same vocabulary as
# ``INVESTO_YFINANCE_TICKERS`` — operators don't need a separate cheat
# sheet for the Stooq mapping.
#
# ``^VIX`` is intentionally retained even though Stooq returns ``N/D``
# today: keeping the mapping documents the intent and lets us drop in
# the working symbol the day Stooq starts carrying CBOE indices,
# without rewriting the adapter. The adapter's per-row N/D handler
# silently skips it for now.
_TICKER_MAP: Final[dict[str, str]] = {
    "^GSPC": "^spx",
    "^IXIC": "^ndq",
    "^DJI": "^dji",
    "^VIX": "^vix",
    "AAPL": "aapl.us",
    "MSFT": "msft.us",
    "GOOGL": "googl.us",
    "AMZN": "amzn.us",
    "NVDA": "nvda.us",
    "META": "meta.us",
    "TSLA": "tsla.us",
    "BTC-USD": "btc.v",
    "ETH-USD": "eth.v",
    # u53 — sector / macro ETF coverage. SPDR sector ETFs and the
    # semiconductor / small-cap / long-bond / gold / oil / USD-index
    # proxies; commodity-futures notation maps to Stooq's ``.f`` suffix.
    # ``BZ=F`` (Brent) and ``^RUT`` (Russell 2000 index) are
    # intentionally NOT mapped here — Stooq returns N/D for both, so we
    # route them via yfinance instead (see ``yfinance._DEFAULT_TICKERS``).
    "XLK": "xlk.us",
    "XLE": "xle.us",
    "XLF": "xlf.us",
    "XLV": "xlv.us",
    "XLY": "xly.us",
    "XLI": "xli.us",
    "SMH": "smh.us",
    "IWM": "iwm.us",
    "TLT": "tlt.us",
    "GLD": "gld.us",
    "USO": "uso.us",
    "UUP": "uup.us",
    "CL=F": "cl.f",
    "GC=F": "gc.f",
}


@register
class StooqPriceAdapter:
    """Adapter for Stooq's daily-snapshot CSV endpoint."""

    name: ClassVar[str] = "stooq-price"
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
        "BTC-USD",
        "ETH-USD",
        # u53 sector / macro ETF coverage extension (14 new entries).
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

    _BASE_URL: ClassVar[str] = "https://stooq.com/q/l/"

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,  # window unused — see R11 docstring above
    ) -> list[NormalizedItem]:
        tickers = parse_symbol_list(_ENV_TICKERS, self._DEFAULT_TICKERS)
        concurrency = _parse_concurrency()
        semaphore = asyncio.Semaphore(concurrency)
        results = await asyncio.gather(
            *(self._fetch_one_limited(client, ticker, semaphore) for ticker in tickers),
            return_exceptions=True,
        )
        items: list[NormalizedItem] = []
        for result in results:
            if isinstance(result, NormalizedItem):
                items.append(result)
            elif isinstance(result, SourceFetchError):
                # Per-ticker source-side failure (4xx / 5xx after retries
                # / malformed CSV row). Sibling tickers continue normally.
                continue
            elif isinstance(result, BaseException):
                # Programmer error escapes — re-raise so the orchestrator
                # stage-level guard sees it.
                raise result
        return items

    async def _fetch_one_limited(
        self,
        client: httpx.AsyncClient,
        ticker: str,
        semaphore: asyncio.Semaphore,
    ) -> NormalizedItem | None:
        async with semaphore:
            return await self._fetch_one(client, ticker)

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        ticker: str,
    ) -> NormalizedItem | None:
        stooq_symbol = _TICKER_MAP.get(ticker)
        if stooq_symbol is None:
            # Operator supplied a yfinance-vocabulary ticker we have no
            # Stooq mapping for. Skip silently — the adapter is best-
            # effort over a known map, not an arbitrary lookup service.
            _logger.info("[stooq-price] no Stooq mapping for ticker %r — skipped", ticker)
            return None

        url = self._BASE_URL
        response = await retry_get(
            client,
            url,
            source_name=self.name,
            params={
                "s": stooq_symbol,
                "i": "d",
                "h": "1",
                "f": "sd2t2ohlcv",
            },
            headers={"User-Agent": _USER_AGENT},
        )
        body = response.text
        row = _parse_csv_row(body)
        if row is None:
            # Stooq served us a header-only or malformed body. No data
            # for this ticker — skip silently.
            return None
        if _is_not_available(row):
            # Stooq's documented "unknown ticker" placeholder. Skip
            # without raising — this fires for ^VIX / ^RUT today.
            _logger.info(
                "[stooq-price] %s (%s) returned N/D placeholder — skipped",
                ticker,
                stooq_symbol,
            )
            return None

        try:
            open_ = float(row["Open"])
            high = float(row["High"])
            low = float(row["Low"])
            close = float(row["Close"])
        except (KeyError, ValueError):
            return None
        volume = _parse_volume(row.get("Volume", ""))

        try:
            published_at = _resolve_close_timestamp(row["Date"])
        except (KeyError, ValueError):
            return None

        # No prior-close from a single-row CSV. The downstream u49
        # anchor unit will compute change-rate from archive history;
        # for today the adapter emits a snapshot without pct.
        title = f"{ticker} {close:,.2f}"
        summary = f"O:{open_:,.2f} H:{high:,.2f} L:{low:,.2f} C:{close:,.2f} V:{format_int(volume)}"
        if len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        raw_metadata: dict[str, str] = {
            "ticker": ticker,
            "stooq_symbol": stooq_symbol,
            "open": format_float(open_),
            "high": format_float(high),
            "low": format_float(low),
            "close": format_float(close),
            "volume": format_int(volume),
        }
        # u55 Step 1 — stamp the typed CoreFact entry so the
        # numeric_verify gate (briefing/numeric_verify.py) can look up
        # the Decimal-as-string source value by enum key. Tickers that
        # don't map to a core fact (e.g. sector ETFs like XLK) skip this
        # field entirely — the gate then treats body numbers for them
        # as non-core (action `warn`) rather than `unverified`.
        fact = core_fact_for_ticker(ticker)
        if fact is not None:
            raw_metadata[core_fact_metadata_key(fact)] = format_float(close)

        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=f"https://stooq.com/q/?s={quote(stooq_symbol, safe='')}",
                published_at=published_at,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None


def _parse_csv_row(body: str) -> dict[str, str] | None:
    """Parse the first data row from a Stooq CSV response.

    Stooq returns ``Symbol,Date,Time,Open,High,Low,Close,Volume`` as
    the header (with ``h=1``) followed by one data row for the
    requested daily snapshot. Returns the row as a dict keyed by
    header field, or ``None`` if the body is empty / header-only /
    malformed.
    """
    if not body or not body.strip():
        return None
    reader = csv.DictReader(io.StringIO(body))
    for row in reader:
        # First (and only expected) data row.
        return {key: (value or "").strip() for key, value in row.items() if key is not None}
    return None


def _is_not_available(row: dict[str, str]) -> bool:
    """Stooq's placeholder "unknown ticker" sentinel: every value == N/D."""
    return all(value == _NOT_AVAILABLE for key, value in row.items() if key != "Symbol")


def _parse_volume(raw: str) -> int:
    """Parse a Stooq volume cell to a non-negative int.

    Equity volume comes through as plain integers (``52692761``); crypto
    volume comes through as fractional floats (``14237.042997827913``);
    indices sometimes carry an empty cell. We coerce all three to an
    int by truncating fractions and treating empty / unparseable cells
    as 0 — the field is informational on the briefing card and a 0
    surface is preferable to dropping the whole row.
    """
    if not raw:
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _resolve_close_timestamp(date_str: str) -> datetime:
    """Resolve a Stooq ``YYYY-MM-DD`` date to that day's 16:00 ET as UTC.

    Stooq's ``Time`` field reports the *snapshot* moment in Stooq local
    (Warsaw); it is not the US market close. For consistency with the
    yfinance adapter (R11) we pin ``published_at`` to 16:00 America/
    New_York on the reported trading day and convert to UTC; the
    briefing thus reads "S&P 500 close" with the same wall-clock
    semantics regardless of which adapter sourced the row.
    """
    parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
    ny_close = datetime.combine(parsed, time(16, 0), tzinfo=_NY)
    return ny_close.astimezone(UTC)


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
