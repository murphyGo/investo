"""Orchestrator pipeline — stage runners + ``run_pipeline`` composer.

This module is built up incrementally across plan Steps 5-9:

* **Step 5** (this commit) — :func:`_stage_collect`: wraps u1
  ``Aggregator.fetch_all``; raises :class:`EmptyCollectError` on a
  zero-item return so ``run_pipeline`` can route the failure through
  AC-003-2.
* Steps 6-8 will add ``_stage_generate``, ``_stage_publish``,
  ``_stage_notify_briefing`` (each thin async wrappers around the
  corresponding work unit's surface).
* Step 9 will add :func:`run_pipeline` — the Q9=B-routing composer.

Each stage runner takes its callable dependency as a keyword-only
parameter so unit tests can inject a fake without monkeypatching
``investo.sources`` etc. The defaults wire to the real units;
``run_pipeline`` (Step 9) propagates injected callables through.

Logging follows AC-005-5: each stage entry emits an INFO line; per-
source degradation surfaces as a WARNING from the underlying unit
(u1 already logs at WARNING — we don't double-log here).

Reference:
    aidlc-docs/construction/u5-orchestrator/nfr-requirements/
    aidlc-docs/construction/plans/u5-orchestrator-code-generation-plan.md
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import date

from investo.models import NormalizedItem
from investo.orchestrator.errors import EmptyCollectError
from investo.sources import fetch_all as _default_fetch_all

_logger = logging.getLogger("investo.orchestrator.pipeline")

# Type alias for the callable shape of u1's ``fetch_all``. Captures the
# surface ``run_pipeline`` and ``_stage_collect`` depend on without
# importing a class — u1's aggregator is module-level (not a class)
# per ``aidlc-docs/inception/application-design/component-methods.md``.
CollectCallable = Callable[[date], Awaitable[list[NormalizedItem]]]


async def _stage_collect(
    target_date: date,
    *,
    fetch: CollectCallable | None = None,
) -> list[NormalizedItem]:
    """Run u1's source aggregator and gate on a non-empty result.

    Parameters
    ----------
    target_date:
        Resolved by :func:`investo.orchestrator.date_resolution
        .resolve_target_date`. Passed through to the aggregator.
    fetch:
        Override hook for tests. When ``None`` (production), wires to
        :func:`investo.sources.fetch_all`. Tests inject a fake to avoid
        spinning the real httpx client.

    Returns
    -------
    list[NormalizedItem]
        Non-empty union of items from all successful sources. Per-
        source failures inside the aggregator are already swallowed
        with a WARNING — see ``aggregator.fetch_all`` docstring + FD
        L4 / NFR AC-3.5.

    Raises
    ------
    EmptyCollectError
        Every source returned zero items (or no adapters are
        registered). ``run_pipeline`` catches this and routes to
        ``OperatorAlerter.alert(stage="collect")`` per AC-003-2.
    """
    runner = fetch if fetch is not None else _default_fetch_all

    _logger.info("[collect] starting target_date=%s", target_date)
    items = await runner(target_date)
    _logger.info("[collect] returned %d items", len(items))

    if not items:
        # Empty result is a hard failure — the briefing has nothing
        # to summarize. The error_message is intentionally terse;
        # ``run_pipeline`` formats the operator-alert text including
        # ``target_date`` at the catch site.
        raise EmptyCollectError(f"aggregator returned 0 items for target_date={target_date}")

    return items
