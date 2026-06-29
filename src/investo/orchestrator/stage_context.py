"""Orchestrator stage-context loaders (u84 — relocated from pipeline.py).

These build the *inputs* the segmented generate stage consumes — the
per-segment market anchors + price history, the per-segment carryover
bundles, and the trailing recent-briefings context. They were previously
defined inline in ``orchestrator/pipeline.py``; u84 moves the context-
assembly responsibility into its own module so ``run_pipeline`` reads as a
sequencing + error-routing loop rather than a context-loading + routing
tangle.

Behaviour-preserving: this is a verbatim move. ``pipeline.py`` re-imports
each name so existing references / tests keep their import path. The
``ARCHIVE_ROOT`` lookups stay deferred to call time so the
``monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", …)`` test
seam keeps working.

This module is part of u5 (orchestrator) and is permitted the cross-unit
imports (sources / briefing / publisher) that CLAUDE.md #3 grants the
orchestrator.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final

from investo.briefing.carryover_parser import load_carryover, resolve_lookback_days
from investo.briefing.context import (
    RecentBriefingsContext,
    load_recent_briefings,
    resolve_recent_days,
)
from investo.briefing.market_anchor import (
    DEFAULT_HISTORY_WINDOW_DAYS,
    MarketAnchor,
    OHLCRow,
    compute_market_anchors,
)
from investo.briefing.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
)
from investo.models import BriefingCarryover, NormalizedItem
from investo.models.coverage import SourceOutcome
from investo.orchestrator.domestic_anchor_quarantine import domestic_anchor_verdicts

_logger = logging.getLogger("investo.orchestrator.stage_context")
_MARKET_ANCHOR_HISTORY_BUDGET_ENV = "INVESTO_MARKET_ANCHOR_HISTORY_BUDGET_S"
_DEFAULT_MARKET_ANCHOR_HISTORY_BUDGET_S = 8.0

SEGMENT_ORDER: tuple[MarketSegment, MarketSegment, MarketSegment] = (
    DOMESTIC_EQUITY,
    US_EQUITY,
    CRYPTO,
)

# u49 deterministic-market-anchor segment routing. Mirrors the price-
# adapter coverage: us-equity owns the S&P 500 / NASDAQ / DJIA indices
# plus the seven big-tech bellwethers; crypto owns BTC-USD / ETH-USD;
# domestic-equity has no Yahoo-coverable basket today (KOSPI / KOSDAQ
# are not part of the snapshot adapters' default basket and would
# need a separate fetcher — out of scope for u49 per the plan).
_ANCHOR_SEGMENT_ROUTING: dict[str, MarketSegment] = {
    "^GSPC": US_EQUITY,
    "^IXIC": US_EQUITY,
    "^DJI": US_EQUITY,
    "AAPL": US_EQUITY,
    "MSFT": US_EQUITY,
    "GOOGL": US_EQUITY,
    "AMZN": US_EQUITY,
    "NVDA": US_EQUITY,
    "META": US_EQUITY,
    "TSLA": US_EQUITY,
    "BTC-USD": CRYPTO,
    "ETH-USD": CRYPTO,
    # u67 — domestic index close + 원/달러 (from stooq-kr-market). These
    # are not Yahoo-history-backed (yfinance KRW=X / ^kospi are 429 on the
    # GHA IP); the anchors are synthesized close-only from the domestic
    # price snapshot items via ``_build_kr_anchors_from_items``.
    "^KOSPI": DOMESTIC_EQUITY,
    "^KOSDAQ": DOMESTIC_EQUITY,
    "KRW=X": DOMESTIC_EQUITY,
}


def _market_anchor_history_budget_from_env() -> float:
    raw = os.environ.get(_MARKET_ANCHOR_HISTORY_BUDGET_ENV)
    if raw is None:
        return _DEFAULT_MARKET_ANCHOR_HISTORY_BUDGET_S
    raw = raw.strip()
    try:
        value = float(raw)
    except ValueError:
        _logger.warning(
            "[market_anchor] invalid %s=%r; falling back to %.1fs",
            _MARKET_ANCHOR_HISTORY_BUDGET_ENV,
            raw,
            _DEFAULT_MARKET_ANCHOR_HISTORY_BUDGET_S,
        )
        return _DEFAULT_MARKET_ANCHOR_HISTORY_BUDGET_S
    if value > 0:
        return value
    _logger.warning(
        "[market_anchor] invalid %s=%r; expected positive seconds; falling back to %.1fs",
        _MARKET_ANCHOR_HISTORY_BUDGET_ENV,
        raw,
        _DEFAULT_MARKET_ANCHOR_HISTORY_BUDGET_S,
    )
    return _DEFAULT_MARKET_ANCHOR_HISTORY_BUDGET_S


# u67 / u109 — canonical domestic snapshot anchor tickers and display
# priority. KOSPI / KOSDAQ / 원/달러 are sourced from stooq-kr-market, while
# the large-cap rows are sourced from fsc-krx-stock-price. None uses Yahoo
# history, so they render as close-only anchor rows (note column "—").
_KR_ANCHOR_TICKERS: Final[tuple[str, ...]] = (
    "^KOSPI",
    "^KOSDAQ",
    "KRW=X",
    "005930.KS",
    "000660.KS",
)


def _snapshot_close_by_ticker(items: Sequence[NormalizedItem]) -> dict[str, Decimal]:
    """Build ``ticker -> Decimal(close)`` from price-snapshot items.

    Reads ``raw_metadata["ticker"]`` + ``raw_metadata["close"]`` off every
    ``category == "price"`` item. This is the exact close value the body
    prose and the trace footer surface (the snapshot adapters derive the
    item title and the ``core_fact:`` overlay from the same field), so an
    anchor overridden to this value agrees with both other surfaces.

    Last-writer-wins on duplicate tickers (matches the numeric_verify
    aggregation contract). Rows with a missing / unparseable close are
    skipped — the anchor then falls back to its history close.
    """
    out: dict[str, Decimal] = {}
    for item in items:
        if item.category != "price":
            continue
        ticker = str(item.raw_metadata.get("ticker", "")).strip()
        close_raw = str(item.raw_metadata.get("close", "")).strip()
        if not ticker or not close_raw:
            continue
        try:
            out[ticker] = Decimal(close_raw)
        except (InvalidOperation, ValueError):
            continue
    return out


def _build_kr_anchors_from_items(
    items: Sequence[NormalizedItem],
    *,
    target_date: date | None = None,
    source_outcomes: Sequence[SourceOutcome] = (),
) -> tuple[MarketAnchor, ...]:
    """Synthesize close-only domestic :class:`MarketAnchor` rows (u67).

    The Yahoo-history anchor path cannot supply domestic rows from the
    GitHub Actions IP space. Instead the domestic anchor table is built
    from deterministic trusted snapshot items: one anchor per KR ticker,
    close-only (derived range / period fields stay ``None`` → the table
    renders a "—" note). The body / trace cite the same ``close`` value,
    so all three surfaces agree.

    Empty / missing KR items ⇒ empty tuple (the domestic table omits the
    KR rows entirely, matching the existing graceful-degrade contract).
    """
    trusted_snapshot = {
        verdict.candidate.symbol: verdict.candidate.close
        for verdict in domestic_anchor_verdicts(
            items,
            target_date=target_date,
            source_outcomes=source_outcomes,
        )
        if verdict.trust == "trusted" and verdict.candidate.symbol in _KR_ANCHOR_TICKERS
    }
    anchors: list[MarketAnchor] = []
    for ticker in _KR_ANCHOR_TICKERS:
        close = trusted_snapshot.get(ticker)
        if close is None:
            continue
        anchors.append(MarketAnchor(ticker=ticker, close=close, is_ath=False))
    return tuple(anchors)


async def _load_market_anchors_for_run(
    target_date: date,
) -> tuple[
    dict[MarketSegment, tuple[MarketAnchor, ...]],
    dict[str, tuple[OHLCRow, ...]],
]:
    """Fetch trailing price history and compute per-segment market anchors (u49).

    Returns both:

    * ``anchors_by_segment`` — the per-segment :class:`MarketAnchor`
      tuples consumed by the briefing header line.
    * ``history_by_ticker`` — the raw ``OHLCRow`` history keyed by
      ticker; the publisher (u50) feeds this into Lightweight Charts
      placeholders so the same fetch underpins both surfaces.

    Best-effort: any failure (network, 429, malformed JSON) is logged
    and swallowed; the orchestrator continues with empty anchors AND
    empty history, the briefing header omits the
    ``> **시장 anchor**`` line, and the chart-block injection skips
    silently. The function is async because the underlying HTTP
    fetch is async; the post-fetch computation is pure synchronous.
    """
    import httpx

    from investo.sources.yfinance_history import fetch_price_history

    empty_anchors: dict[MarketSegment, tuple[MarketAnchor, ...]] = {
        segment: () for segment in SEGMENT_ORDER
    }
    budget_s = _market_anchor_history_budget_from_env()
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=min(20.0, budget_s)) as client:
            history = await asyncio.wait_for(fetch_price_history(client), timeout=budget_s)
    except TimeoutError:
        elapsed_s = time.monotonic() - start
        _logger.warning(
            "[market_anchor] history fetch timed out budget_s=%.1f elapsed_s=%.3f; "
            "briefing header anchor omitted",
            budget_s,
            elapsed_s,
            extra={
                "elapsed_s": elapsed_s,
                "budget_s": budget_s,
                "degraded_reason": "timeout",
            },
        )
        return empty_anchors, {}
    except Exception as exc:  # pragma: no cover - best-effort guard
        elapsed_s = time.monotonic() - start
        _logger.warning(
            "[market_anchor] history fetch failed elapsed_s=%.3f error=%s; "
            "briefing header anchor omitted",
            elapsed_s,
            exc,
            extra={
                "elapsed_s": elapsed_s,
                "budget_s": budget_s,
                "degraded_reason": type(exc).__name__,
            },
        )
        return empty_anchors, {}

    anchors = compute_market_anchors(
        history,
        today=target_date,
        history_window_days=DEFAULT_HISTORY_WINDOW_DAYS,
    )
    by_segment: dict[MarketSegment, list[MarketAnchor]] = {segment: [] for segment in SEGMENT_ORDER}
    for anchor in anchors:
        segment = _ANCHOR_SEGMENT_ROUTING.get(anchor.ticker)
        if segment is None:
            continue
        by_segment[segment].append(anchor)
    _logger.info(
        "[market_anchor] target_date=%s tickers=%d us=%d crypto=%d domestic=%d elapsed_s=%.3f",
        target_date,
        len(anchors),
        len(by_segment[US_EQUITY]),
        len(by_segment[CRYPTO]),
        len(by_segment[DOMESTIC_EQUITY]),
        time.monotonic() - start,
    )
    history_by_ticker = {ticker: tuple(rows) for ticker, rows in history.items()}
    return (
        {segment: tuple(values) for segment, values in by_segment.items()},
        history_by_ticker,
    )


def _load_carryover_for_run(
    target_date: date,
    candidates_by_segment: Mapping[MarketSegment, Sequence[NormalizedItem]],
) -> dict[MarketSegment, BriefingCarryover]:
    """Build a per-segment :class:`BriefingCarryover` map for u52.

    Walks each segment's prior ≤``INVESTO_CARRYOVER_LOOKBACK_DAYS``
    archive markdown files via :func:`load_carryover`. Per-segment
    isolation: a parser failure for one segment (file I/O error,
    malformed markdown) is swallowed and the segment receives an
    empty :class:`BriefingCarryover` — the orchestrator continues to
    publish the rest.

    The :data:`ARCHIVE_ROOT` lookup is deferred to call time (not at
    import) so unit tests that monkeypatch
    ``investo.publisher.paths.ARCHIVE_ROOT`` see the redirected path.
    """
    from investo.publisher.paths import ARCHIVE_ROOT

    lookback = resolve_lookback_days()
    result: dict[MarketSegment, BriefingCarryover] = {}
    for segment in SEGMENT_ORDER:
        candidates = candidates_by_segment.get(segment, ())
        try:
            result[segment] = load_carryover(
                ARCHIVE_ROOT,
                segment,
                target_date,
                candidates=candidates,
                lookback=lookback,
            )
        except Exception as exc:
            _logger.warning(
                "[carryover] segment=%s parser failed; using empty bundle err=%s",
                segment,
                exc,
            )
            result[segment] = BriefingCarryover(
                prior_resolved=(),
                prior_unresolved=(),
                lookback_days=0,
            )
    total = sum(len(b.prior_resolved) + len(b.prior_unresolved) for b in result.values())
    _logger.info(
        "[carryover] loaded target_date=%s lookback=%d total_items=%d",
        target_date,
        lookback,
        total,
    )
    return result


def _load_recent_context_for_run(target_date: date) -> RecentBriefingsContext | None:
    """Resolve the env-var window and load the trailing recent-briefings context.

    Returns ``None`` when the user explicitly disabled the feature
    (``INVESTO_RECENT_CONTEXT_DAYS=0``); the orchestrator threads
    ``None`` straight through and the briefing prompt omits the
    "최근 N일 컨텍스트" block entirely. Otherwise returns the loaded
    :class:`RecentBriefingsContext`, which itself may be empty (first
    publish path) — the prompt builder handles both cases.

    The :data:`ARCHIVE_ROOT` lookup is deferred to call time (not at
    import) so unit tests that monkeypatch
    ``investo.publisher.paths.ARCHIVE_ROOT`` see the redirected path.
    """
    days = resolve_recent_days()
    if days <= 0:
        _logger.info("[recent_context] disabled (days=0)")
        return None
    from investo.publisher.paths import ARCHIVE_ROOT

    context = load_recent_briefings(ARCHIVE_ROOT, target_date, days=days)
    total = sum(len(entries) for entries in context.entries_by_segment.values())
    _logger.info(
        "[recent_context] loaded target_date=%s days=%d entries=%d",
        target_date,
        days,
        total,
    )
    return context


__all__ = [
    "SEGMENT_ORDER",
    "_build_kr_anchors_from_items",
    "_load_carryover_for_run",
    "_load_market_anchors_for_run",
    "_load_recent_context_for_run",
    "_market_anchor_history_budget_from_env",
    "_snapshot_close_by_ticker",
]
