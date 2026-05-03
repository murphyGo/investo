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
from datetime import date, timedelta

import httpx

from investo.models import NormalizedItem
from investo.sources._registry import list_sources
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError

_logger = logging.getLogger(__name__)
_MAX_FUTURE_PUBLISHED_AT = timedelta(days=30)


async def fetch_all(target_date: date) -> list[NormalizedItem]:
    """Run every registered adapter concurrently and return the union of items.

    Per FD R6 / L4: any adapter raising :class:`SourceFetchError`
    contributes ``[]`` and is logged at WARNING. Any *other* exception
    (programmer error or system-level) is re-raised so the
    orchestrator's stage-level guard sees it.

    Returns a flat ``list[NormalizedItem]``. An empty list is a valid
    outcome — the orchestrator (not this unit) decides whether zero
    items means a pipeline failure (FD §E5 / NFR AC-3.5).
    """

    adapters = list_sources()
    if not adapters:
        return []

    window = FetchWindow.from_kst_date(target_date)

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(adapter.fetch(client, window) for adapter in adapters),
            return_exceptions=True,
        )

    items: list[NormalizedItem] = []
    for adapter, result in zip(adapters, results, strict=True):
        if isinstance(result, SourceFetchError):
            # L5: one WARNING per failed adapter. We log the
            # *exception's* self-reported source_name (not the
            # registry's adapter.name): an adapter that violates
            # FD R8 by raising SourceFetchError("typo", ...) while
            # registered as "fomc-rss" will surface its lie in the
            # log, which is the desired debugging signal.
            _logger.warning(
                "source failed",
                extra={
                    "source_name": result.source_name,
                    "category": adapter.category,
                    "error": str(result),
                    "transient": result.transient,
                },
            )
            continue
        if isinstance(result, BaseException):
            # gather(return_exceptions=True) catches every BaseException
            # subclass including CancelledError / KeyboardInterrupt /
            # SystemExit. Re-raising here propagates them up to the
            # orchestrator's stage-level guard, which is the right
            # behavior — adapters never silence non-source errors.
            raise result
        for item in result:
            if item.published_at > window.end_utc + _MAX_FUTURE_PUBLISHED_AT:
                _logger.warning(
                    "source %s emitted future-dated item: published_at=%s target_date=%s",
                    item.source_name,
                    item.published_at.isoformat(),
                    target_date,
                )
                continue
            items.append(item)
    return items
