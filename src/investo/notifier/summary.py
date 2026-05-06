"""Telegram channel summary builder (FR-004).

``build_summary`` composes the public-channel preview text from a
:class:`Briefing` and a site URL pointing at the archived markdown.

Telegram's ``sendMessage`` text-field limit is **4096 UTF-16 code
units**, NOT 4096 characters. Non-BMP characters (emoji like 📈,
certain CJK ideographs) consume 2 code units per Python codepoint,
so ``len(s)`` would under-count and risk exceeding the limit.
The truncation here uses ``len(s.encode("utf-16-le")) // 2`` for
accurate counting — the same formula the
:class:`BriefingNotification` model validator enforces (defense in
depth: this function truncates; the model validator rejects any
overflow that survives).

Layout::

    📈 {target_date.isoformat()} 시황 요약

    {truncated market_summary}

    상세보기: {site_url}

The footer URL is always preserved (it's the whole point of the
summary). Body text is truncated with a trailing "…" when it
overflows the budget.

Reference:
    aidlc-docs/inception/application-design/component-methods.md (C4)
    aidlc-docs/construction/plans/u4-notifier-code-generation-plan.md
        (Step 3)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from investo.briefing.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    SEGMENT_LABELS,
    US_EQUITY,
    MarketSegment,
)
from investo.models import Briefing

# Telegram's hard cap. Mirrors the constant in
# ``investo.models.briefing`` (``TELEGRAM_MESSAGE_LIMIT``); kept local
# here so callers don't need to reach into models for a number they're
# already passing in.
DEFAULT_MAX_UNITS: Final[int] = 4096

# Truncation suffix. 1 UTF-16 unit (BMP character).
_TRUNCATION_SUFFIX: Final[str] = "…"


def _utf16_units(text: str) -> int:
    """Return the count of UTF-16 code units in ``text``.

    Equivalent to ``len(text.encode("utf-16-le")) // 2``. Non-BMP
    code points (emoji, certain CJK) count as 2 units.
    """
    return len(text.encode("utf-16-le")) // 2


def _utf16_truncate(text: str, max_units: int) -> str:
    """Truncate ``text`` to at most ``max_units`` UTF-16 code units.

    Surrogate-pair safe: a truncation that lands between the high
    and low halves of a non-BMP code point's UTF-16 encoding is
    rolled back by one unit so the result remains valid UTF-16.
    """
    encoded = text.encode("utf-16-le")
    if len(encoded) // 2 <= max_units:
        return text
    if max_units <= 0:
        return ""
    truncated_bytes = encoded[: max_units * 2]
    # If the final unit is a high surrogate (the first half of a
    # surrogate pair), drop it to avoid emitting half a code point.
    last_unit = int.from_bytes(truncated_bytes[-2:], "little")
    if 0xD800 <= last_unit <= 0xDBFF:
        truncated_bytes = truncated_bytes[:-2]
    return truncated_bytes.decode("utf-16-le", errors="ignore")


def build_summary(
    briefing: Briefing,
    *,
    site_url: str,
    max_units: int = DEFAULT_MAX_UNITS,
) -> str:
    """Build the public-channel summary text for ``briefing``.

    Returns a string fitting within ``max_units`` UTF-16 code units.
    The footer (``상세보기: {site_url}``) is always preserved; the
    body (``briefing.market_summary``) is truncated with a "…"
    suffix when it would overflow.
    """
    header = f"📈 {briefing.target_date.isoformat()} 시황 요약\n\n"
    footer = f"\n\n상세보기: {site_url}"

    fixed_units = _utf16_units(header) + _utf16_units(footer)
    body_budget = max_units - fixed_units

    body = briefing.market_summary

    if _utf16_units(body) <= body_budget:
        return header + body + footer

    # Need to truncate. Leave room for the 1-unit suffix.
    truncated = _utf16_truncate(body, body_budget - _utf16_units(_TRUNCATION_SUFFIX))
    return header + truncated + _TRUNCATION_SUFFIX + footer


def build_segmented_summary(
    briefings: Mapping[MarketSegment, Briefing],
    *,
    site_urls: Mapping[MarketSegment, str],
    max_units: int = DEFAULT_MAX_UNITS,
) -> str:
    """Build one Telegram message with all segment summaries and links.

    The three URLs are part of the fixed footer and are always
    preserved; segment summary lines are truncated first if needed.
    """
    target_date = briefings[DOMESTIC_EQUITY].target_date
    ordered_segments = (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)
    header = f"📈 {target_date.isoformat()} 시황 요약\n\n"
    footer = "\n\n상세보기:\n" + "\n".join(
        f"{SEGMENT_LABELS[segment]}: {site_urls[segment]}" for segment in ordered_segments
    )
    body = "\n".join(
        f"{SEGMENT_LABELS[segment]}: {_one_line_summary(briefings[segment])}"
        for segment in ordered_segments
    )

    fixed_units = _utf16_units(header) + _utf16_units(footer)
    body_budget = max_units - fixed_units
    if _utf16_units(body) <= body_budget:
        return header + body + footer

    truncated = _utf16_truncate(body, body_budget - _utf16_units(_TRUNCATION_SUFFIX))
    return header + truncated + _TRUNCATION_SUFFIX + footer


def _one_line_summary(briefing: Briefing) -> str:
    for line in briefing.market_summary.splitlines():
        line = line.strip()
        if line:
            return line
    return "데이터 부족"


__all__ = ["DEFAULT_MAX_UNITS", "build_segmented_summary", "build_summary"]
