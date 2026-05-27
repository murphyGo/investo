"""Stage 2 context-block rendering (SINGLE home for context blocks).

The recent / carryover / bundle / lookahead context blocks and the
segment-scope instruction block are the LLM-input context surface. This
module is the single home for context-block rendering (per the u83 plan
correction 2026-05-28 — an earlier draft double-listed it under
``markdown_render`` too).

Moved verbatim from ``briefing/pipeline.py`` in the u83 decomposition;
behavior-preserving (move-only).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC

from investo.briefing.context import RecentBriefingEntry, RecentBriefingsContext
from investo.briefing.prompts import (
    CRYPTO_FORBIDDEN_TERMS_NOTE,
    CRYPTO_UTC_FRAME_NOTE,
    DEFAULT_SEGMENT_CONTEXT,
    DOMESTIC_DEPTH_NOTE,
    SEGMENT_CONTEXT_TEMPLATE,
    SEGMENT_DATA_LIMITED_NOTE,
    SEGMENT_DATA_READY_NOTE,
    format_bundle_context_section,
    format_carryover_section,
    format_lookahead_section,
    format_recent_context_section,
)
from investo.briefing.segments import (
    SEGMENT_LABELS,
    MarketSegment,
    filter_lookahead_items,
)
from investo.models import (
    BriefingCarryover,
    CarryoverItem,
    NormalizedItem,
    status_label_kr,
)
from investo.models.bundle_context import BundleContext


def _render_recent_context_block(
    segment: MarketSegment | None,
    recent_context: RecentBriefingsContext | None,
) -> str:
    """Render the u34 "최근 N일 컨텍스트" block for Stage 2.

    Returns the empty string for the unsegmented legacy path or when
    ``recent_context`` is ``None`` — the Stage 2 user template absorbs
    an empty placeholder cleanly because the surrounding template
    already provides whitespace structure.

    When ``recent_context.is_empty()`` (or the per-segment list is
    empty) the rendered block carries the "no recent context" note so
    the LLM still sees an explicit acknowledgement that the context is
    intentionally absent (vs. silently missing).

    Each entry collapses to a single line: the loader has already
    truncated the conclusion / drivers fields to the per-day budget;
    this renderer only stitches labels.
    """
    if segment is None or recent_context is None:
        return ""
    entries = recent_context.for_segment(segment)
    if not entries:
        return format_recent_context_section("")
    lines = [_render_recent_entry(entry) for entry in entries]
    return format_recent_context_section("\n".join(lines))


def _render_recent_entry(entry: RecentBriefingEntry) -> str:
    """Render one :class:`RecentBriefingEntry` as a single bullet line.

    Format::

        - YYYY-MM-DD: 결론="..." | 핵심 동인="..."

    The fields are already truncated + redacted by the loader (per the
    u34 trust contract); this function adds no additional sanitization.
    Empty fields collapse to ``(없음)`` so the LLM can see the gap
    rather than guess.
    """
    conclusion = entry.conclusion or "(없음)"
    drivers = entry.key_drivers or "(없음)"
    return f'- {entry.publish_date.isoformat()}: 결론="{conclusion}" | 핵심 동인="{drivers}"'


def _render_carryover_context_block(
    carryover: BriefingCarryover | None,
) -> str:
    """Render the u52 "## Watchlist Carryover (입력)" block for Stage 2.

    Returns the empty string when ``carryover`` is ``None`` (legacy /
    unsegmented path; the prompt template absorbs the placeholder
    cleanly). When ``carryover.is_empty`` the block carries the "no
    carryover" note so the LLM sees an explicit acknowledgement.

    Otherwise emits one deterministic row per item in the order:
    resolved first, then unresolved (carried_over rows are mixed into
    the unresolved list per the model's split rule). The renderer is
    *separate* from the publisher-side ``render_carryover_block``: the
    prompt block is plain text (LLM-readable rows); the publisher
    block is a Markdown table (reader-facing).
    """
    if carryover is None:
        return ""
    if carryover.is_empty:
        return format_carryover_section("")
    lines: list[str] = []
    for item in carryover.prior_resolved:
        lines.append(_render_carryover_prompt_row(item))
    for item in carryover.prior_unresolved:
        lines.append(_render_carryover_prompt_row(item))
    return format_carryover_section("\n".join(lines))


def _render_bundle_context_block(
    bundle_context: BundleContext | None,
    *,
    segment: MarketSegment | None,
) -> str:
    """Render the u57 BundleContext block for Stage 2.

    Returns the empty string when ``bundle_context`` is ``None`` (legacy
    / test paths). When the segment is non-null we force *its own* slot
    to ``pending`` so the LLM cannot self-assert a close-state — see
    :class:`BundleContext.with_self_pending` for the anti-regression
    rationale.

    The rendered JSON is intentionally minimal — only the fields the
    LLM needs to obey BC-1~BC-4 — to keep the prompt token cost ≤ 500.
    """
    if bundle_context is None:
        return ""
    ctx = bundle_context.with_self_pending(segment) if segment is not None else bundle_context
    payload = {
        "bundle_id": ctx.bundle_id,
        "target_kst_date": ctx.target_kst_date.isoformat(),
        "segments": {
            seg: {
                "close_state": summ.close_state,
                "headline_native_fact": summ.headline_native_fact,
            }
            for seg, summ in ctx.segments.items()
        },
        "shared_macro_present": ctx.shared_macro_block is not None,
        "cross_market_core_allowed": sorted(ctx.cross_market_core_allowed),
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return format_bundle_context_section(body)


def _render_carryover_prompt_row(item: CarryoverItem) -> str:
    """Render one :class:`CarryoverItem` as a deterministic bullet line.

    Format::

        - [event_type] ticker_or_topic | 발원=YYYY-MM-DD | 기대=YYYY-MM-DD | 상태=확인됨

    The Korean status label is sourced via
    :func:`investo.models.status_label_kr`. ``expected_date`` is
    rendered as ``미정`` when the carryover has no expected date.
    """
    expected = item.expected_date.isoformat() if item.expected_date is not None else "미정"
    status_label = status_label_kr(item.status)
    return (
        f"- [{item.event_type}] {item.ticker_or_topic} | "
        f"발원={item.originated_date.isoformat()} | "
        f"기대={expected} | 상태={status_label}"
    )


def _render_lookahead_context_block(items: Sequence[NormalizedItem]) -> str:
    """Render the u35 "주요 일정" block from forward-scheduled items.

    Walks ``items`` (already capped by :func:`_select_llm_candidate_items`)
    pulling out rows whose ``scheduled_at`` is set and emitting one
    bullet line per row. Empty input falls through to the
    "no lookahead" note so the LLM sees an explicit acknowledgement
    rather than silently dropping the rule.

    Each row is intentionally compact (date + source + title) — the
    block must stay under the ~300-char-per-segment budget the plan
    locks. The selection cap (:data:`_MAX_LLM_LOOKAHEAD_ITEMS` = 12)
    plus an inline character ceiling per line keeps the total bounded
    even when an upstream adapter floods.
    """
    lookahead = filter_lookahead_items(items)
    if not lookahead:
        return format_lookahead_section("")

    lines: list[str] = []
    for item in lookahead:
        scheduled_at = item.scheduled_at
        # Defensive — ``scheduled_at is not None`` was already checked
        # in the comprehension; this assert is for the type checker.
        assert scheduled_at is not None
        scheduled_date = scheduled_at.astimezone(UTC).date().isoformat()
        # Trim extra-long titles so a single row cannot blow the budget.
        title = item.title if len(item.title) <= 80 else item.title[:79] + "…"
        lines.append(f"- {scheduled_date}: [{item.source_name}] {title}")
    return format_lookahead_section("\n".join(lines))


def _render_segment_context(segment: MarketSegment | None, *, data_limited: bool) -> str:
    """Render prompt-side segment scope instructions for u7.

    ``segment=None`` keeps the original u2 unsegmented behavior. When a
    segment is supplied, both Stage 1 and Stage 2 see the same scope so
    classification and synthesis cannot silently drift apart.
    """
    if segment is None:
        return DEFAULT_SEGMENT_CONTEXT

    data_limited_note = SEGMENT_DATA_LIMITED_NOTE if data_limited else SEGMENT_DATA_READY_NOTE
    # u56 — append crypto-only forbidden-term clause so the Stage-2 LLM
    # sees the §10 retail-coded ban at the same surface as the segment
    # scope. The publisher gate enforces this same list regardless of
    # whether the LLM honored the prompt.
    # u56 crypto ban / u67 domestic depth — at most one applies per segment.
    if segment == "crypto":
        segment_extra_note = f"{CRYPTO_FORBIDDEN_TERMS_NOTE}\n{CRYPTO_UTC_FRAME_NOTE}\n"
    elif segment == "domestic-equity":
        segment_extra_note = f"{DOMESTIC_DEPTH_NOTE}\n"
    else:
        segment_extra_note = ""
    return SEGMENT_CONTEXT_TEMPLATE.format(
        segment_label=SEGMENT_LABELS[segment],
        segment_slug=segment,
        data_limited_note=data_limited_note,
        segment_extra_note=segment_extra_note,
    )


__all__ = [
    "_render_bundle_context_block",
    "_render_carryover_context_block",
    "_render_carryover_prompt_row",
    "_render_lookahead_context_block",
    "_render_recent_context_block",
    "_render_recent_entry",
    "_render_segment_context",
]
