"""Pre-Stage-2 :class:`BundleContext` computation (u57).

Called by the orchestrator immediately after routing — *before* any
segment's Stage-2 prompt is built. Walks each segment's routed
:class:`NormalizedItem`\\s, derives a deterministic close-state via
:func:`investo.briefing.time_state.detect_time_state`, and detects
shared-macro candidates whose source title shape appears in two or
more segments simultaneously (the canonical trigger from u57 plan
Step 1.5).

Purity contract
---------------

The function is pure: ``(routed, now_kst) → BundleContext`` is fully
deterministic for a given input. Only side effect is structured
logging via :data:`_logger`. ``now_kst`` is passed in (never read from
:func:`datetime.now`) so replay tests remain reproducible.

References
----------

* u57 plan Step 1.5 — pre-computation algorithm.
* u57 DoD — "BundleContext is computed before Stage 2 and injected as
  the same object into all three prompts".
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Final

from investo.briefing.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
)
from investo.briefing.time_state import TimeState, detect_time_state
from investo.models import NormalizedItem
from investo.models.bundle_context import (
    CROSS_MARKET_CORE_ALLOWED,
    BundleContext,
    CloseState,
    MarketStateSummary,
)

_logger = logging.getLogger(__name__)


_SEGMENT_TZ: Final[dict[MarketSegment, str]] = {
    DOMESTIC_EQUITY: "Asia/Seoul",
    US_EQUITY: "America/New_York",
    CRYPTO: "UTC",
}


# Shared-macro detector patterns. When ≥ 2 segments have a routed item
# whose title matches the same key, we surface it as a candidate for
# the ``## ⓪`` block. Patterns are intentionally narrow to minimise
# false positives.
_SHARED_MACRO_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "ust_yield": re.compile(
        r"(미\s?국채|UST|10\s?-?\s?년물?\s?수익률|treasury\s+yield)",
        re.IGNORECASE,
    ),
    "oil": re.compile(r"(WTI|Brent|브렌트|국제\s?유가|원유)", re.IGNORECASE),
    "fomc": re.compile(r"(FOMC|연준|Fed\s+meeting|기준금리)", re.IGNORECASE),
}


def _select_close_state_for_segment(
    items: Sequence[NormalizedItem],
) -> tuple[CloseState, str | None]:
    """Pick a segment's representative close-state.

    Algorithm:
    1. For each item with a published_at, detect_time_state on title.
    2. Take the *latest* (by published_at) item whose detect succeeded.
    3. That item supplies the close_state + a one-line headline fact
       (the title itself, truncated to ~120 chars).

    Returns ``("pending", None)`` when no item produces a label.
    """
    best: tuple[datetime, TimeState, str] | None = None
    for item in items:
        state = detect_time_state(item.title)
        if state is None:
            continue
        if best is None or item.published_at > best[0]:
            best = (item.published_at, state, item.title)
    if best is None:
        return "pending", None
    _, state, title = best
    headline = title if len(title) <= 120 else title[:117] + "..."
    return state, headline


def _detect_shared_macros(
    routed: Mapping[MarketSegment, Sequence[NormalizedItem]],
) -> list[tuple[str, str]]:
    """Return list of (macro_key, evidence_title) for keys hit by ≥ 2 segments."""
    hits_by_key: dict[str, dict[MarketSegment, str]] = {}
    for segment, items in routed.items():
        for item in items:
            for key, pattern in _SHARED_MACRO_PATTERNS.items():
                if pattern.search(item.title):
                    hits_by_key.setdefault(key, {})
                    hits_by_key[key].setdefault(segment, item.title)
    shared: list[tuple[str, str]] = []
    for key, by_segment in hits_by_key.items():
        if len(by_segment) >= 2:
            # Use the alphabetically-first segment's evidence title as
            # representative — deterministic across runs.
            first_segment = sorted(by_segment.keys())[0]
            shared.append((key, by_segment[first_segment]))
    # Sort by macro key for deterministic ordering.
    shared.sort(key=lambda pair: pair[0])
    return shared


_MACRO_KEY_LABELS: Final[dict[str, str]] = {
    "ust_yield": "미 국채 수익률",
    "oil": "국제 유가",
    "fomc": "FOMC 일정",
}


def _render_shared_macro_block(shared: Sequence[tuple[str, str]]) -> str | None:
    """Render the ``## ⓪ 오늘의 매크로`` body.

    Returns ``None`` when no macro hits ≥ 2 segments — caller skips H2
    injection in that case.
    """
    if not shared:
        return None
    lines = [f"- **{_MACRO_KEY_LABELS.get(key, key)}** — {evidence}" for key, evidence in shared]
    return "\n".join(lines)


def compute_bundle_context(
    routed: Mapping[MarketSegment, Sequence[NormalizedItem]],
    *,
    now_kst: datetime,
    bundle_id: str | None = None,
) -> BundleContext:
    """Compute the same-run :class:`BundleContext` from routed items.

    ``routed`` is the segment → items mapping produced by u45's
    router. ``now_kst`` is the orchestrator's reference time (passed
    explicitly so replay tests are deterministic). ``bundle_id``
    defaults to ``"<YYYY-MM-DD>-bundle"`` when omitted.

    The returned context has every known segment populated; segments
    not present in ``routed`` get a ``pending`` summary so downstream
    consumers can rely on the three slots existing unconditionally.
    """
    target_date: date = now_kst.date()
    bundle_id = bundle_id or f"{target_date.isoformat()}-bundle"

    summaries: dict[str, MarketStateSummary] = {}
    for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO):
        items = routed.get(segment, ())
        close_state, headline = _select_close_state_for_segment(items)
        summaries[segment] = MarketStateSummary(
            segment=segment,
            target_date=target_date,
            tz=_SEGMENT_TZ[segment],
            close_state=close_state,
            headline_native_fact=headline,
        )

    shared = _detect_shared_macros(routed)
    shared_block = _render_shared_macro_block(shared)

    ctx = BundleContext(
        bundle_id=bundle_id,
        target_kst_date=target_date,
        segments=summaries,
        shared_macro_block=shared_block,
        cross_market_core_allowed=CROSS_MARKET_CORE_ALLOWED,
    )

    _logger.info(
        "bundle_context.computed",
        extra={
            "bundle_id": bundle_id,
            "target_date": target_date.isoformat(),
            "close_states": {seg: summ.close_state for seg, summ in summaries.items()},
            "shared_macro_count": len(shared),
        },
    )
    return ctx


__all__ = ["compute_bundle_context"]
