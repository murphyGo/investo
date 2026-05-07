"""Briefing-markdown anchor extraction (DEBT-060 chokepoint).

The first-viewport summary block emitted by
:func:`investo.briefing.pipeline._enhance_reader_experience` is parsed by
five distinct downstream surfaces:

1. ``investo.publisher.site_index`` — Home page hero block ("오늘의 결론"
   quote cards per segment),
2. ``investo.publisher.weekly_digest`` — Saturday retrospective rows
   pulling each archived day's conclusion line,
3. ``investo.visuals.og_card`` — OG image SVG body lines,
4. ``investo.visuals.assets`` — `MarketSnapshotCardInput` field
   extraction (conclusion / driver / caution),
5. ``investo.briefing.context`` — recent-briefings-context loader for
   the Stage 2 "today inside the weekly arc" prompt block.

DEBT-060 promoted from Medium → High when the fifth consumer (u34
context loader) landed. This module collapses the five near-identical
extraction routines into one chokepoint so a future change to any of
the prefix markers lands in one place. Each helper returns ``None`` on
miss, leaving the **fallback text** to the caller — site_index uses
"결론 인용을 추출하지 못했습니다.", weekly_digest uses "(결론 인용을
추출하지 못함)", og_card uses "결론 인용을 추출하지 못했습니다.",
assets falls back to the briefing's own ``market_summary`` /
``key_issues`` / ``today_watch`` fields, context returns ``""`` and
gates on (conclusion or drivers) being non-empty.

Project-rule preservation:

* No new dependency — pure stdlib.
* No module-boundary violation — imports only from the same
  ``investo.briefing.summary_quality`` peer for the prefix constants.
* No I/O, no clock — every helper is a pure function of its input
  ``rendered_markdown``.
* Idempotent — calling extract_* twice on the same input returns the
  same value.
"""

from __future__ import annotations

from investo.briefing.summary_quality import (
    CAUTION_PREFIX,
    CONCLUSION_PREFIX,
    DRIVER_PREFIX,
    WATERMARK_PREFIX,
)


def _extract_first(rendered_markdown: str, prefix: str) -> str | None:
    """Return the trimmed value following the first ``prefix``-anchored line.

    Iterates lines (preserving order — first match wins, matching the
    historic behavior of all five call sites). Returns ``None`` when no
    line starts with ``prefix`` OR when the matched value is empty
    after trimming. The "first match wins" rule is deliberate: a
    rendered briefing emits each prefix exactly once, but a defensive
    parse against a malformed archive should not silently swap to a
    later (possibly garbage) line.
    """
    for line in rendered_markdown.splitlines():
        if line.startswith(prefix):
            value = line.removeprefix(prefix).strip()
            if value:
                return value
            return None
    return None


def extract_conclusion(rendered_markdown: str) -> str | None:
    """Extract the ``> **오늘의 결론**:`` value, ``None`` on miss.

    The hero card on the Home page, the weekly retrospective rows, the
    OG image body, and the recent-context Stage 2 block all consume
    this anchor.
    """
    return _extract_first(rendered_markdown, CONCLUSION_PREFIX)


def extract_key_drivers(rendered_markdown: str) -> str | None:
    """Extract the ``> **핵심 동인**:`` value, ``None`` on miss.

    Consumed by the visual-card market-snapshot field and the
    recent-context Stage 2 block.
    """
    return _extract_first(rendered_markdown, DRIVER_PREFIX)


def extract_caution(rendered_markdown: str) -> str | None:
    """Extract the ``> **주의할 점**:`` value, ``None`` on miss.

    Consumed by the visual-card market-snapshot caution field.
    """
    return _extract_first(rendered_markdown, CAUTION_PREFIX)


def extract_watermark(rendered_markdown: str) -> str | None:
    """Extract the ``**기준 시각**:`` value, ``None`` on miss.

    Consumed by the recent-context Stage 2 block. The watermark line
    is *not* a blockquote (it sits above the summary block); the
    prefix already encodes the leading ``**`` so callers do not need
    to special-case the missing ``> `` blockquote leader.
    """
    return _extract_first(rendered_markdown, WATERMARK_PREFIX)


__all__ = [
    "extract_caution",
    "extract_conclusion",
    "extract_key_drivers",
    "extract_watermark",
]
