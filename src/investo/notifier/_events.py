"""Deterministic imminent-event tagging for the Telegram summary (u35).

This module owns the *imminent-event policy* — what counts as
"imminent" (the 72-hour horizon), how the top candidate is selected
deterministically, the source-name → icon mapping, and the terse
per-source label. It is deliberately separate from both the briefing
*extraction* layer (:mod:`investo.notifier._summary_extract`) and the
Telegram *formatting* layer (:mod:`investo.notifier.summary`):

- Extraction answers "what does this briefing say?" (regex pulls from
  ``rendered_markdown`` / ``market_summary``).
- Formatting answers "how do we render Telegram-safe bytes?" (markdown
  cleanup, UTF-16 budget, price decoration, block assembly).
- Event detection answers "is there a calendar event close enough to
  flag, and how do we name it?" — a policy with its own reason to
  change (horizon length, icon registry, label rules). Folding it into
  either neighbour would tangle an unrelated change-axis, so it lives
  here (review 2026-05-28, u80 Step 1).

The produced tag (e.g. ``📅 FOMC D-2``) is *not* LLM-generated; it is
derived entirely from :attr:`NormalizedItem.scheduled_at`,
:attr:`NormalizedItem.source_name`, and an explicit ``now_utc`` — no
network, no clock read when ``now_utc`` is supplied (DEBT-067 M1).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Final

from investo.models import NormalizedItem

# u35 — imminent-event horizon for the deterministic Telegram tag.
# Events scheduled within 72 hours of the run instant qualify; the tag
# is computed by D-distance arithmetic, not by the LLM (no hallucination
# surface). Capped at top-1 by deterministic ordering (earliest first).
_IMMINENT_HORIZON: Final[timedelta] = timedelta(hours=72)
# Source-name → emoji mapping for the imminent tag prefix. New
# adapters that emit ``scheduled_at`` should register an entry here so
# the deterministic tag stays terse and source-attributable. Sources
# not in this map fall back to a generic 📅 calendar icon.
_IMMINENT_TAG_ICON: Final[dict[str, str]] = {
    "fomc-rss": "📅",
    "nasdaq-earnings-calendar": "📊",
    "fred-macro": "📈",
    "coingecko-events": "🪙",
}
_IMMINENT_TAG_FALLBACK_ICON: Final[str] = "📅"


def imminent_event_tag(
    lookahead_items: Sequence[NormalizedItem],
    *,
    now_utc: datetime | None,
) -> str:
    """Compute a deterministic imminent-event tag from forward items.

    Selects the earliest item whose ``scheduled_at`` falls within
    :data:`_IMMINENT_HORIZON` of ``now_utc`` and emits a tag of the
    shape ``"📅 <label> D-<n>"`` (where ``n`` is the number of full
    UTC days between ``now_utc`` and ``scheduled_at``, rounded down,
    minimum 0). When nothing qualifies, returns an empty string and
    the caller leaves the line unchanged.

    Determinism: the function consults ``scheduled_at`` and
    ``source_name`` only — no LLM call, no network, no clock read
    when ``now_utc`` is supplied. The orchestrator passes a single
    ``now_utc`` for all segments so a multi-segment publish emits a
    consistent set of tags.
    """
    if not lookahead_items or now_utc is None:
        return ""
    horizon_end = now_utc + _IMMINENT_HORIZON
    candidates = [
        item
        for item in lookahead_items
        if item.scheduled_at is not None and now_utc <= item.scheduled_at < horizon_end
    ]
    if not candidates:
        return ""
    # Earliest first; ties broken by source then title for determinism.
    best = min(
        candidates,
        key=lambda item: (
            item.scheduled_at,
            item.source_name,
            item.title,
        ),
    )
    assert best.scheduled_at is not None
    delta = best.scheduled_at - now_utc
    days_to_event = max(int(delta.total_seconds() // 86400), 0)
    icon = _IMMINENT_TAG_ICON.get(best.source_name, _IMMINENT_TAG_FALLBACK_ICON)
    label = _imminent_event_label(best)
    return f"{icon} {label} D-{days_to_event}"


def _imminent_event_label(item: NormalizedItem) -> str:
    """Resolve a terse Korean/English label for the imminent tag.

    For earnings calendar rows we surface the ticker symbol so the
    Telegram preview reads ``📊 NVDA 실적 D-1`` instead of repeating
    the long company-name title. For other sources we fall back to
    the first 24 characters of the title — short enough that the
    surrounding "상세보기" footer still fits inside the UTF-16 budget.
    """
    if item.source_name == "nasdaq-earnings-calendar":
        symbol = item.raw_metadata.get("symbol")
        if isinstance(symbol, str) and symbol:
            return f"{symbol} 실적"
    title = item.title.strip()
    return title if len(title) <= 24 else title[:23] + "…"


__all__ = ["imminent_event_tag"]
