"""Shared per-item fan-out / error-isolation helper for source adapters.

Several adapters fetch N sub-resources concurrently (one ticker / coin /
series each) and then sort the results: keep the produced
:class:`NormalizedItem`\\ s, isolate per-item ``SourceFetchError``\\ s, and
let any *other* exception (a programmer error) escape to the
orchestrator's stage guard. This is the ``asyncio.gather(...,
return_exceptions=True)`` + classify loop that was copy-pasted across
adapters (Wave 14 u77 extraction).

Internal to ``investo.sources`` — sibling units must not import it.

Design choice (u77): this helper does NOT live in ``_retry.py`` (kept
HTTP/backoff-focused) nor ``_parse.py`` (payload parsing). It is its own
concern — concurrent fan-out — so it gets its own module.

Two escalation modes seen in the wild are both preserved:

* ``raise_if_all_failed=False`` (default) — pure per-item isolation:
  reproduces ``fred`` / ``yfinance``.
* ``raise_if_all_failed=True`` — re-raise the first ``SourceFetchError``
  only when zero items were produced AND at least one fetch failed:
  reproduces ``binance`` / ``fsc_krx_stock_price``.

"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Iterable

from investo.models import NormalizedItem
from investo.sources.protocol import SourceFetchError


async def gather_with_error_isolation(
    coros: Iterable[Awaitable[NormalizedItem | None]],
    *,
    source_name: str,
    raise_if_all_failed: bool = False,
) -> list[NormalizedItem]:
    """Gather ``coros`` concurrently and classify their results.

    Returns the produced :class:`NormalizedItem`\\ s in ``coros`` order
    isolating per-item :class:`SourceFetchError`\\ s. Any other
    :class:`BaseException` (programmer error) is re-raised immediately.

    With ``raise_if_all_failed`` the first isolated ``SourceFetchError``
    is re-raised when no items were produced and at least one fetch
    failed (the binance / fsc_krx escalation contract).

    ``source_name`` is accepted for call-site symmetry with the other
    shared helpers and future diagnostics; it is currently unused because
    the helper only re-raises pre-existing exceptions verbatim.
    """

    _ = source_name
    results = await asyncio.gather(*coros, return_exceptions=True)
    items: list[NormalizedItem] = []
    failures: list[SourceFetchError] = []
    for result in results:
        if isinstance(result, NormalizedItem):
            items.append(result)
        elif isinstance(result, SourceFetchError):
            failures.append(result)
        elif isinstance(result, BaseException):
            raise result
    if raise_if_all_failed and not items and failures:
        raise failures[0]
    return items
