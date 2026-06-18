"""Aggregator — concurrent fan-out across all registered Source Adapters.

Implements
``aidlc-docs/construction/u1-sources/functional-design/business-logic-model.md``
L1 (end-to-end flow), L4 (failure classification), L5 (logging
contract), and ``business-rules.md`` R6 (failure isolation). Pins NFR
ACs 1.1 (≤ 70 s wall-clock with one 60-s adapter) and 3.1-3.5
(graceful degradation).

:func:`fetch_all` is the public entry point of u1 — the orchestrator
(u5) calls it once per pipeline run.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

import httpx

from investo.models import NormalizedItem, SourceCollectionReport, SourceOutcome
from investo.models.segments import SEGMENT_MARKET_TZ
from investo.sources._registry import list_sources
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceAdapter, SourceFetchError
from investo.sources.tiers import adapter_tier

_logger = logging.getLogger(__name__)
_MAX_FUTURE_PUBLISHED_AT = timedelta(days=30)
_US_MARKET_SOURCES: Final[frozenset[str]] = frozenset(
    {
        "bea-macro-actuals",
        "bls-macro-actuals",
        "cnbc-top-news",
        "fed-board-leadership",
        "fed-speech-rss",
        "fomc-calendar",
        "fomc-rss",
        "fred-economic-calendar",
        "fred-macro",
        "nasdaq-earnings-calendar",
        "nasdaq-symbol-directory",
        "nasdaq-stocks-news",
        "sec-company-facts",
        "sec-edgar-8k",
        "sec-newsroom-rss",
        "stooq-price",
        "treasury-rates",
        "us-economic-calendar",
        "yahoo-finance-news",
        "yfinance-price",
    }
)
_CRYPTO_MARKET_SOURCES: Final[frozenset[str]] = frozenset(
    {
        "alternative-fng",
        "bybit-derivatives",
        "coingecko-price",
        "coingecko-global-market",
        "binance-crypto-market",
        "defillama-market-structure",
        "congress-gov-bill-actions",
        "house-financial-services-policy",
        "okx-derivatives",
        "senate-banking-policy",
        "theblock-crypto",
    }
)


@dataclass(frozen=True, slots=True)
class _TimedAdapterResult:
    result: list[NormalizedItem] | BaseException
    elapsed_s: float


async def fetch_all(target_date: date) -> list[NormalizedItem]:
    """Run every registered adapter concurrently and return the union of items.

    Per FD R6 / L4: any adapter raising :class:`SourceFetchError`
    contributes ``[]`` and is logged at WARNING. Any *other* exception
    (programmer error or system-level) is re-raised so the
    orchestrator's stage-level guard sees it.

    Returns a flat ``list[NormalizedItem]``. An empty list is a valid
    outcome — the orchestrator (not this unit) decides whether zero
    items means a pipeline failure (FD §E5 / NFR AC-3.5).

    This is a thin wrapper over :func:`collect_sources` that drops the
    per-adapter outcome report. Callers that need adapter-level success
    / zero / failure detail (u22 source-coverage transparency) should
    consume :func:`collect_sources` directly.
    """
    report = await collect_sources(target_date)
    return list(report.items)


async def collect_sources(target_date: date) -> SourceCollectionReport:
    """Run every registered adapter concurrently and return a full report.

    Same execution model as :func:`fetch_all` — concurrent fan-out, FD
    R6 failure isolation, programmer-error propagation. The difference
    is the return shape: callers get the union of items **plus** one
    :class:`SourceOutcome` per registered adapter so downstream layers
    (segment coverage, visual cards, public markdown) can reason about
    which sources succeeded, returned zero, or failed.

    Outcome ordering matches the registry order (deterministic) so the
    same set of adapters always produces the same outcome sequence.
    """

    adapters = list_sources()
    if not adapters:
        return SourceCollectionReport(items=(), outcomes=())

    windows = {adapter.name: _window_for_adapter(target_date, adapter.name) for adapter in adapters}

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(_fetch_adapter_timed(adapter, client, windows[adapter.name]) for adapter in adapters),
        )

    items: list[NormalizedItem] = []
    outcomes: list[SourceOutcome] = []
    for adapter, timed in zip(adapters, results, strict=True):
        result = timed.result
        elapsed_s = timed.elapsed_s
        if isinstance(result, SourceFetchError):
            # L5: one WARNING per failed adapter. We log the
            # *exception's* self-reported source_name (not the
            # registry's adapter.name): an adapter that violates
            # FD R8 by raising SourceFetchError("typo", ...) while
            # registered as "fomc-rss" will surface its lie in the
            # log, which is the desired debugging signal.
            _logger.warning(
                "source failed source_name=%s category=%s transient=%s elapsed_s=%.3f error=%s",
                result.source_name,
                adapter.category,
                result.transient,
                elapsed_s,
                str(result),
                extra={
                    "source_name": result.source_name,
                    "category": adapter.category,
                    "error": str(result),
                    "transient": result.transient,
                    "elapsed_s": elapsed_s,
                },
            )
            outcomes.append(
                SourceOutcome.from_failure(
                    adapter.name,
                    adapter.category,
                    message=str(result),
                    transient=result.transient,
                    tier=adapter_tier(adapter.name),
                    elapsed_s=elapsed_s,
                )
            )
            continue
        if isinstance(result, BaseException):
            # _fetch_adapter_timed captures every BaseException subclass
            # long enough to retain elapsed_s. Re-raising here preserves
            # the old contract: adapters never silence non-source errors.
            raise result
        window = windows[adapter.name]
        kept: list[NormalizedItem] = []
        for item in result:
            if item.published_at > window.end_utc + _MAX_FUTURE_PUBLISHED_AT:
                _logger.warning(
                    "source %s emitted future-dated item: published_at=%s target_date=%s",
                    item.source_name,
                    item.published_at.isoformat(),
                    target_date,
                )
                continue
            kept.append(item)
        _logger.info(
            "source returned source_name=%s category=%s item_count=%d "
            "window_start_utc=%s window_end_utc=%s elapsed_s=%.3f",
            adapter.name,
            adapter.category,
            len(result),
            window.start_utc.isoformat(),
            window.end_utc.isoformat(),
            elapsed_s,
            extra={
                "source_name": adapter.name,
                "category": adapter.category,
                "item_count": len(result),
                "window_start_utc": window.start_utc.isoformat(),
                "window_end_utc": window.end_utc.isoformat(),
                "elapsed_s": elapsed_s,
            },
        )
        items.extend(kept)
        tier = adapter_tier(adapter.name)
        if kept:
            # u54 — populate ``latest_item_at`` for the staleness override
            # in :func:`investo.briefing.segments.build_segment_coverage`.
            # Computed at the aggregator chokepoint so every adapter
            # (core or otherwise) gets the timestamp without per-adapter
            # boilerplate; non-core sources still emit it but the
            # staleness check ignores them.
            latest_item_at = max(item.published_at for item in kept)
            outcomes.append(
                SourceOutcome.ok(
                    adapter.name,
                    adapter.category,
                    len(kept),
                    tier=tier,
                    latest_item_at=latest_item_at,
                    elapsed_s=elapsed_s,
                )
            )
        else:
            outcomes.append(
                SourceOutcome.zero(
                    adapter.name,
                    adapter.category,
                    tier=tier,
                    elapsed_s=elapsed_s,
                )
            )
    return SourceCollectionReport(items=tuple(items), outcomes=tuple(outcomes))


async def _fetch_adapter_timed(
    adapter: SourceAdapter,
    client: httpx.AsyncClient,
    window: FetchWindow,
) -> _TimedAdapterResult:
    start = time.monotonic()
    try:
        result = await adapter.fetch(client, window)
    except BaseException as exc:
        return _TimedAdapterResult(result=exc, elapsed_s=time.monotonic() - start)
    return _TimedAdapterResult(result=result, elapsed_s=time.monotonic() - start)


def _window_for_adapter(target_date: date, source_name: str) -> FetchWindow:
    if source_name in _US_MARKET_SOURCES:
        return FetchWindow.from_local_date(target_date, SEGMENT_MARKET_TZ["us-equity"])
    if source_name in _CRYPTO_MARKET_SOURCES:
        return FetchWindow.from_local_date(target_date, SEGMENT_MARKET_TZ["crypto"])
    return FetchWindow.from_local_date(target_date, SEGMENT_MARKET_TZ["domestic-equity"])
