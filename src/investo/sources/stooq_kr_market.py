"""Stooq + Yonhap Korean-market price adapter — domestic index close + 원/달러 (u67).

Closes the domestic-channel depth gap identified in the 2026-05-24
reader-facing review:

* The official KRX feed (``fsc-krx-index-price``) frequently returns 0
  rows on the KST-morning cron (T+1 settlement timing), so the body has
  no deterministic KOSPI / KOSDAQ close to anchor §① on.
* ``usd_krw`` is mapped in :mod:`investo.sources._core_fact_map` but no
  registered source actually fetched it — yfinance ``KRW=X`` returns
  HTTP 429 from the GitHub Actions shared-runner IP space (verified
  2026-05-24, same failure mode the US ``yfinance`` adapter documents).

This adapter is the **free, no-key fallback** that fills both gaps. It
is registered alongside ``fsc-krx-index-price``; the orchestrator gets
the union of both adapters' items, so when KRX lands the body has the
official rows and when KRX is empty the body still carries a Stooq /
Yonhap-derived close.

Source precedence (confirmed at Step-1 reachability, 2026-05-24)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* **원/달러** — Stooq ``usdkrw`` (no-key, ``200`` with a usable close).
  yfinance ``KRW=X`` is *not* used: it returns ``429`` from GHA.
* **KOSPI close** — overall pipeline precedence is
  ``fsc-krx-index-price`` (official) → this adapter's Stooq ``^kospi``
  → this adapter's Yonhap numeric parse. Within this adapter the order
  is Stooq → Yonhap.
* **KOSDAQ close** — Stooq does **not** carry ``^kosdaq`` (returns the
  ``N/D`` placeholder for every symbol variant probed), so KOSDAQ has
  no Stooq tier: pipeline precedence is ``fsc-krx-index-price`` →
  Yonhap numeric parse only.

Design choices
~~~~~~~~~~~~~~
* **KST close timestamp** — unlike the US ``stooq-price`` adapter (which
  pins ``published_at`` to 16:00 America/New_York), KR instruments pin
  to 15:30 Asia/Seoul (KRX regular-session close). 원/달러 uses the same
  KST close so the §③ 수급 narrative reads a single wall-clock frame.
* **Provenance tag** — every item stamps ``raw_metadata["provenance"]``
  (``stooq`` / ``yonhap-rss``) so the trace footer shows which tier
  supplied the close (AC-1).
* **Core-fact stamp** — KOSPI / KOSDAQ / 원/달러 stamp the typed
  :class:`CoreFact` key via :func:`core_fact_for_ticker` so the
  numeric_verify gate can verify body numbers against the source value.

Pins
~~~~
* **R3** — uses the injected ``httpx.AsyncClient``; never builds its own.
* **R6** — per-symbol isolation via ``asyncio.gather`` semantics; a
  single symbol failure never drops siblings. Whole-adapter failure
  raises :class:`SourceFetchError` only when *every* tier yields
  nothing AND a source-side error occurred.
* **R8** — :class:`NormalizedItem` shape; ``raw_metadata`` is a flat
  ``dict[str, str]``.
* **R9** — idempotent; ``published_at`` is derived from the source date
  pinned to the KST close. No ``datetime.now``.
* **R11** (window-relaxation, parallel to ``stooq-price`` / ``yfinance``)
  — returns the most recent snapshot regardless of strict R7 membership;
  a slightly stale domestic close beats an empty §①.
* **R12** — ``INVESTO_STOOQ_KR_SYMBOLS`` env-var override.
* **R13** — Stooq + Yonhap have no auth surface; no secrets to redact.
* **AC-7.6** — Yonhap RSS parsed via ``defusedxml`` only (never the
  unsafe stdlib ElementTree parser).
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
import re
from datetime import UTC, date, datetime, time
from typing import Any, ClassVar, Final
from zoneinfo import ZoneInfo

import httpx
from defusedxml.ElementTree import ParseError, fromstring
from pydantic import ValidationError

from investo.models import Category, NormalizedItem
from investo.sources._config import SUMMARY_MAX_LEN, format_float, parse_symbol_list
from investo.sources._core_fact_map import core_fact_for_ticker, core_fact_metadata_key
from investo.sources._registry import register
from investo.sources._retry import retry_get
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")
# KRX regular session closes at 15:30 KST. 원/달러 onshore quote runs to
# ~15:30 too; pinning all KR instruments to one close keeps §③ 수급 on a
# single wall-clock frame.
_KR_CLOSE_KST = time(15, 30, tzinfo=_KST)

_ENV_SYMBOLS = "INVESTO_STOOQ_KR_SYMBOLS"
_ENV_CONCURRENCY = "INVESTO_STOOQ_KR_CONCURRENCY"
_DEFAULT_CONCURRENCY = 2
_USER_AGENT = "Investo/1.0 (https://murphygo.github.io/investo)"
_NOT_AVAILABLE = "N/D"

_STOOQ_URL: Final[str] = "https://stooq.com/q/l/"
_STOOQ_PAGE_URL: Final[str] = "https://stooq.com/q/?s="
_YONHAP_FEED_URL: Final[str] = "https://www.yna.co.kr/rss/market.xml"
_YONHAP_PAGE_URL: Final[str] = "https://www.yna.co.kr/market-plus/all"

# Korean display name per canonical ticker (yfinance vocabulary, matching
# ``_core_fact_map``). Used in the item title.
_KR_DISPLAY: Final[dict[str, str]] = {
    "^KOSPI": "코스피",
    "^KOSDAQ": "코스닥",
    "KRW=X": "원/달러 환율",
}

# Canonical ticker → Stooq symbol. ``^KOSDAQ`` is intentionally absent:
# Stooq returns ``N/D`` for it (verified 2026-05-24), so KOSDAQ has no
# Stooq tier and is sourced from the Yonhap numeric parse only.
_STOOQ_SYMBOL: Final[dict[str, str]] = {
    "^KOSPI": "^kospi",
    "KRW=X": "usdkrw",
}

# Yonhap headline numeric-parse patterns. The 마켓+ feed publishes a daily
# close headline shaped like "코스피, ... 2,650.50 마감" / "코스닥 ... 마감".
# We extract the first thousands-grouped decimal that follows the index
# name. Best-effort terminal fallback only — KRX + Stooq are preferred.
_NUM = r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)"
_YONHAP_INDEX_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "^KOSPI": re.compile(rf"코스피[^0-9]{{0,40}}{_NUM}"),
    "^KOSDAQ": re.compile(rf"코스닥[^0-9]{{0,40}}{_NUM}"),
}


@register
class StooqKrMarketAdapter:
    """Adapter for Stooq KR index / FX + a Yonhap numeric index fallback."""

    name: ClassVar[str] = "stooq-kr-market"
    category: ClassVar[Category] = "price"

    # Default basket: KOSPI + 원/달러 (Stooq tier) and KOSDAQ
    # (Yonhap-only tier). KOSPI also has a Yonhap fallback when Stooq is
    # unreachable. Operators can override via ``INVESTO_STOOQ_KR_SYMBOLS``.
    _DEFAULT_SYMBOLS: ClassVar[tuple[str, ...]] = ("^KOSPI", "^KOSDAQ", "KRW=X")

    async def fetch(
        self,
        client: httpx.AsyncClient,
        window: FetchWindow,  # window unused — R11 relaxation (see module docstring)
    ) -> list[NormalizedItem]:
        symbols = parse_symbol_list(_ENV_SYMBOLS, self._DEFAULT_SYMBOLS)
        concurrency = _parse_concurrency()
        semaphore = asyncio.Semaphore(concurrency)

        # First pass — Stooq tier (per-symbol concurrent, isolated).
        results = await asyncio.gather(
            *(self._fetch_stooq_limited(client, sym, semaphore) for sym in symbols),
            return_exceptions=True,
        )
        items: dict[str, NormalizedItem] = {}
        stooq_failed = False
        for sym, result in zip(symbols, results, strict=True):
            if isinstance(result, NormalizedItem):
                items[sym] = result
            elif isinstance(result, SourceFetchError):
                stooq_failed = True
                continue
            elif isinstance(result, BaseException):
                # Programmer error escapes — re-raise for the stage guard.
                raise result

        # Second pass — Yonhap numeric fallback for any symbol the Stooq
        # tier did not satisfy and that has a Yonhap parse pattern.
        missing = [sym for sym in symbols if sym not in items and sym in _YONHAP_INDEX_PATTERNS]
        if missing:
            try:
                fallbacks = await self._fetch_yonhap_indices(
                    client, missing, target_date=window.target_date
                )
            except SourceFetchError:
                # Yonhap unreachable / malformed — terminal for the
                # fallback tier only; Stooq items already collected stay.
                fallbacks = {}
            for sym, item in fallbacks.items():
                items[sym] = item

        if not items and stooq_failed:
            raise SourceFetchError(
                source_name=self.name,
                message="all KR symbols failed (Stooq + Yonhap tiers)",
                transient=True,
            )
        return [items[sym] for sym in symbols if sym in items]

    # ------------------------------------------------------------------
    # Stooq tier
    # ------------------------------------------------------------------
    async def _fetch_stooq_limited(
        self,
        client: httpx.AsyncClient,
        ticker: str,
        semaphore: asyncio.Semaphore,
    ) -> NormalizedItem | None:
        async with semaphore:
            return await self._fetch_stooq_one(client, ticker)

    async def _fetch_stooq_one(
        self,
        client: httpx.AsyncClient,
        ticker: str,
    ) -> NormalizedItem | None:
        stooq_symbol = _STOOQ_SYMBOL.get(ticker)
        if stooq_symbol is None:
            # No Stooq tier (e.g. ^KOSDAQ) — defer to the Yonhap pass.
            return None
        response = await retry_get(
            client,
            _STOOQ_URL,
            source_name=self.name,
            params={"s": stooq_symbol, "i": "d", "h": "1", "f": "sd2t2ohlcv"},
            headers={"User-Agent": _USER_AGENT},
        )
        row = _parse_csv_row(response.text)
        if row is None or _is_not_available(row):
            # Header-only / malformed / N/D placeholder — no Stooq data
            # for this symbol; the Yonhap pass may still cover it.
            return None
        try:
            close = float(row["Close"])
        except (KeyError, ValueError):
            return None
        try:
            source_date = datetime.strptime(row["Date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            return None

        open_ = _safe_float(row.get("Open"))
        high = _safe_float(row.get("High"))
        low = _safe_float(row.get("Low"))
        return self._build_item(
            ticker=ticker,
            close=close,
            open_=open_,
            high=high,
            low=low,
            source_date=source_date,
            provenance="stooq",
            url=f"{_STOOQ_PAGE_URL}{stooq_symbol}",
        )

    # ------------------------------------------------------------------
    # Yonhap numeric-parse fallback tier
    # ------------------------------------------------------------------
    async def _fetch_yonhap_indices(
        self,
        client: httpx.AsyncClient,
        tickers: list[str],
        *,
        target_date: date,
    ) -> dict[str, NormalizedItem]:
        response = await retry_get(
            client,
            _YONHAP_FEED_URL,
            source_name=self.name,
            headers={"User-Agent": _USER_AGENT},
        )
        try:
            root = fromstring(response.content)
        except ParseError as exc:
            raise SourceFetchError(
                source_name=self.name,
                message=f"malformed Yonhap XML: {exc}",
                transient=False,
                cause=exc,
            ) from exc

        # Collect candidate headline strings (title + description text).
        headlines: list[str] = []
        for entry in root.iter("item"):
            title = (entry.findtext("title") or "").strip()
            if title:
                headlines.append(title)
            desc = (entry.findtext("description") or "").strip()
            if desc:
                headlines.append(desc)

        out: dict[str, NormalizedItem] = {}
        for ticker in tickers:
            pattern = _YONHAP_INDEX_PATTERNS.get(ticker)
            if pattern is None:
                continue
            close = _first_numeric_match(pattern, headlines)
            if close is None:
                continue
            item = self._build_item(
                ticker=ticker,
                close=close,
                open_=None,
                high=None,
                low=None,
                source_date=target_date,
                provenance="yonhap-rss",
                url=_YONHAP_PAGE_URL,
            )
            if item is not None:
                out[ticker] = item
        return out

    # ------------------------------------------------------------------
    # Shared item builder
    # ------------------------------------------------------------------
    def _build_item(
        self,
        *,
        ticker: str,
        close: float,
        open_: float | None,
        high: float | None,
        low: float | None,
        source_date: date,
        provenance: str,
        url: str,
    ) -> NormalizedItem | None:
        published_at = datetime.combine(source_date, _KR_CLOSE_KST).astimezone(UTC)
        display = _KR_DISPLAY.get(ticker, ticker)
        is_fx = ticker == "KRW=X"
        title = f"{display} {close:,.2f}원" if is_fx else f"{display} {close:,.2f}"
        summary_parts: list[str] = []
        if open_ is not None and high is not None and low is not None:
            summary_parts.append(f"O:{open_:,.2f} H:{high:,.2f} L:{low:,.2f} C:{close:,.2f}")
        else:
            summary_parts.append(f"C:{close:,.2f}")
        summary_parts.append(f"출처:{provenance}")
        summary = "; ".join(summary_parts)
        if len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]

        raw_metadata: dict[str, str] = {
            "ticker": ticker,
            "display_name": display,
            "close": format_float(close),
            "provenance": provenance,
            "source_date": source_date.isoformat(),
        }
        if open_ is not None:
            raw_metadata["open"] = format_float(open_)
        if high is not None:
            raw_metadata["high"] = format_float(high)
        if low is not None:
            raw_metadata["low"] = format_float(low)

        fact = core_fact_for_ticker(ticker)
        if fact is not None:
            raw_metadata[core_fact_metadata_key(fact)] = format_float(close)

        try:
            return NormalizedItem(
                source_name=self.name,
                category=self.category,
                title=title,
                summary=summary,
                url=url,
                published_at=published_at,
                raw_metadata=raw_metadata,
            )
        except ValidationError:
            return None


def _parse_csv_row(body: str) -> dict[str, str] | None:
    if not body or not body.strip():
        return None
    reader = csv.DictReader(io.StringIO(body))
    for row in reader:
        return {key: (value or "").strip() for key, value in row.items() if key is not None}
    return None


def _is_not_available(row: dict[str, str]) -> bool:
    return all(value == _NOT_AVAILABLE for key, value in row.items() if key != "Symbol")


def _safe_float(raw: Any) -> float | None:
    text = str(raw or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _first_numeric_match(pattern: re.Pattern[str], headlines: list[str]) -> float | None:
    for line in headlines:
        match = pattern.search(line)
        if match is None:
            continue
        token = match.group(1).replace(",", "")
        try:
            value = float(token)
        except ValueError:
            continue
        # Index closes are well above 100; guard against picking up a
        # spurious small number (e.g. a percentage) right after the name.
        if value < 100.0:
            continue
        return value
    return None


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


__all__ = ["StooqKrMarketAdapter"]
