"""Reader-facing header enhancement + data-limited body.

``_enhance_reader_experience`` prepends the title / segment nav /
watermark / market-anchor / coverage badge / watchlist callout /
numeric-warning / glossary callout / 3-line summary header to the
synthesized body. ``_build_data_limited_body`` is the zero-input
shortcut body.

Moved verbatim from ``briefing/pipeline.py`` in the u83 decomposition;
behavior-preserving (move-only). ``_enhance_reader_experience`` /
``_render_timestamp_watermark`` keep their import path via re-export
from ``briefing/pipeline.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Final

from investo._internal.data_limited_segment import build_data_limited_body
from investo._internal.public_quality_language import PUBLIC_LOW_COVERAGE_TEXT
from investo._internal.public_watermark import (
    render_timestamp_watermark as _render_timestamp_watermark,
)
from investo.briefing import numeric_self_check
from investo.briefing._assembly.summary_extraction import _build_summary_header
from investo.briefing._reader_enhance.coverage_badge import _render_coverage_badge
from investo.briefing.action_tag import DATA_LIMITED_ACTION_TAG
from investo.briefing.glossary import (
    audit_glossary_compliance,
    collect_recently_glossed,
    render_glossary_callout,
)
from investo.briefing.market_anchor import MarketAnchor, render_market_anchor_line
from investo.briefing.segments import SEGMENT_LABELS, MarketSegment, SegmentCoverage
from investo.briefing.watchlist import WatchlistImpact, render_watchlist_impact
from investo.models import NormalizedItem

_SEGMENT_NAV_LABELS: Final[dict[MarketSegment, str]] = {
    "domestic-equity": "국내 증시",
    "us-equity": "미국 증시",
    "crypto": "크립토",
}
_CONCLUSION_TERMINATORS: Final[tuple[str, ...]] = (".", "!", "?", "…", "。")
_CONCLUSION_CLOSERS: Final[frozenset[str]] = frozenset(
    "\"')]}" + "\u201d\u2019\uff09\u3011\u300d\u300f"
)


def _build_data_limited_body(target_date: date, segment: MarketSegment) -> str:
    """Return a concise six-section body for a segment with zero routed items."""
    return build_data_limited_body(target_date, segment)


def _segment_nav(target_date: date, segment: MarketSegment) -> str:
    filename = f"{target_date.isoformat()}.md"
    links: list[str] = []
    for target_segment, label in _SEGMENT_NAV_LABELS.items():
        href = (
            filename
            if target_segment == segment
            else f"../../../{target_segment}/{target_date.year}/{target_date.month:02d}/{filename}"
        )
        links.append(f"[{label}]({href})")
    return " | ".join(links)


def _render_watchlist_callout(impact: WatchlistImpact) -> str:
    """Render the site-channel watchlist callout (u28).

    Always emits a callout for the public site, including the ``unconfigured``
    onboarding nudge and the ``coverage_hold`` branch. The Telegram surface
    is rendered separately via :func:`render_watchlist_impact` with
    ``channel='telegram'`` and is allowed to skip these branches.
    """
    return f"> **내 관심 자산 영향**: {render_watchlist_impact(impact, channel='site')}\n"


def _render_public_conclusion(conclusion: str) -> str:
    """Replace a terminal data-limited tag with its own reader sentence."""
    stripped = conclusion.strip()
    if not stripped.endswith(DATA_LIMITED_ACTION_TAG):
        return stripped

    preceding = stripped[: -len(DATA_LIMITED_ACTION_TAG)].rstrip()
    terminal_probe = preceding
    while terminal_probe and terminal_probe[-1] in _CONCLUSION_CLOSERS:
        terminal_probe = terminal_probe[:-1].rstrip()
    if preceding and not terminal_probe.endswith(_CONCLUSION_TERMINATORS):
        preceding = f"{preceding}."
    if not preceding:
        return PUBLIC_LOW_COVERAGE_TEXT
    return f"{preceding} {PUBLIC_LOW_COVERAGE_TEXT}"


def _enhance_reader_experience(
    body_markdown: str,
    *,
    target_date: date,
    segment: MarketSegment | None,
    sections: tuple[str, str, str, str, str, str],
    coverage: SegmentCoverage | None = None,
    watchlist_impact: WatchlistImpact | None = None,
    data_limited: bool = False,
    candidates: Sequence[NormalizedItem] | None = None,
    market_anchors: Sequence[MarketAnchor] = (),
    archive_root: Path | None = None,
) -> str:
    """Prepend the reader-facing title, segment nav, and 3-line brief."""
    if segment is None:
        return body_markdown

    label = SEGMENT_LABELS[segment]
    effective_data_limited = data_limited or (coverage is not None and coverage.status != "normal")
    summary_header = _build_summary_header(sections, data_limited=effective_data_limited)
    public_conclusion = _render_public_conclusion(summary_header.conclusion)
    watermark = _render_timestamp_watermark(target_date, segment)
    # u49 — deterministic market anchor line (ATH / 52w / MTD / YTD).
    # Empty when no anchors landed (history fetch failed or empty
    # input); the helper returns "" so the f-string collapses cleanly.
    anchor_line = render_market_anchor_line(market_anchors)
    # u32 Step 2 — Stage 3 numeric self-check. Compare flaggable numeric
    # tokens in the body against the Stage 1 candidate haystack and
    # render a single-line warning callout when mismatches are found.
    numeric_warning_line = ""
    if candidates is not None:
        unverified = numeric_self_check.find_unverified(body_markdown, candidates)
        numeric_warning_line = numeric_self_check.render_warning_line(unverified)
    # u68 — cross-day suppression. Terms already glossed in this
    # segment's recent archives are dropped so the "처음 등장한 용어"
    # callout stays truthful within the recent window. A missing
    # archive_root (fresh repo / data-limited) yields an empty set →
    # today-only behavior (no regression).
    already_glossed = (
        collect_recently_glossed(archive_root, segment, target_date)
        if archive_root is not None
        else set()
    )
    glossary_line = render_glossary_callout(
        audit_glossary_compliance(
            body_markdown,
            segment=segment,
            already_glossed=already_glossed,
        )
    )
    header = (
        f"# {target_date.isoformat()} {label} 시황\n\n"
        f"{watermark}\n\n"
        f"{anchor_line}"
        f"**세그먼트**: {_segment_nav(target_date, segment)}\n\n"
        f"{_render_coverage_badge(coverage) if coverage is not None else ''}"
        f"{_render_watchlist_callout(watchlist_impact) if watchlist_impact is not None else ''}"
        f"{numeric_warning_line}"
        f"{glossary_line}"
        f"> **오늘의 결론**: {public_conclusion}\n"
        f"> **핵심 동인**: {summary_header.driver}\n"
        f"> **주의할 점**: {summary_header.caution}\n\n"
    )
    return f"{header}{body_markdown}"


__all__ = [
    "_build_data_limited_body",
    "_enhance_reader_experience",
    "_render_public_conclusion",
    "_render_timestamp_watermark",
    "_render_watchlist_callout",
    "_segment_nav",
]
