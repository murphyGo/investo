"""Branch tests for the u34 recent-context renderer in the pipeline.

Pins the four observable branches of
:func:`investo.briefing.pipeline._render_recent_context_block` and the
single-line shape of :func:`investo.briefing.pipeline._render_recent_entry`
so future template tweaks cannot silently change the bytes the LLM sees:

1. ``segment is None`` — unsegmented legacy path returns ``""``.
2. ``recent_context is None`` — segment supplied but loader skipped
   returns ``""``.
3. ``entries`` empty for the requested segment — returns ``""`` so
   Stage 2 prompt bytes are not spent on an empty optional block.
4. ``entries`` present — emits the standard header + intro + each
   entry rendered via :func:`_render_recent_entry`.

The integration test in ``tests/unit/briefing/test_recent_context.py``
already covers the loader contract; this file covers the prompt-render
seam so renderer regressions are caught without spinning up the full
two-stage pipeline.
"""

from __future__ import annotations

from datetime import date

from investo.briefing.context import RecentBriefingEntry, RecentBriefingsContext
from investo.briefing.pipeline import (
    _render_recent_context_block,
    _render_recent_entry,
)
from investo.briefing.prompts import (
    RECENT_CONTEXT_HEADER,
    RECENT_CONTEXT_INTRO,
)
from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY


def _entry(
    *,
    publish_date: date = date(2026, 5, 7),
    conclusion: str = "상승 마감, 거래대금 확대",
    drivers: str = "반도체 강세, 외국인 순매수",
    watermark: str = "2026-05-07 18:00 KST",
) -> RecentBriefingEntry:
    return RecentBriefingEntry(
        publish_date=publish_date,
        segment=US_EQUITY,
        conclusion=conclusion,
        key_drivers=drivers,
        watermark=watermark,
    )


def _context(entries: tuple[RecentBriefingEntry, ...]) -> RecentBriefingsContext:
    return RecentBriefingsContext(
        target_date=date(2026, 5, 8),
        days=5,
        entries_by_segment={
            DOMESTIC_EQUITY: (),
            US_EQUITY: entries,
            CRYPTO: (),
        },
    )


# ---------------------------------------------------------------------------
# _render_recent_context_block — 4 branches
# ---------------------------------------------------------------------------


def test_render_recent_context_block_segment_none_returns_empty_string() -> None:
    """Branch 1 — legacy unsegmented call yields ``""``."""
    rendered = _render_recent_context_block(
        segment=None,
        recent_context=_context((_entry(),)),
    )
    assert rendered == ""


def test_render_recent_context_block_context_none_returns_empty_string() -> None:
    """Branch 2 — loader skipped (``recent_context is None``) yields ``""``."""
    rendered = _render_recent_context_block(
        segment=US_EQUITY,
        recent_context=None,
    )
    assert rendered == ""


def test_render_recent_context_block_empty_entries_returns_empty_string() -> None:
    """Branch 3 — requested segment has no entries yields ``""``."""
    rendered = _render_recent_context_block(
        segment=US_EQUITY,
        recent_context=_context(()),
    )
    assert rendered == ""


def test_render_recent_context_block_with_entries_pins_full_shape() -> None:
    """Branch 4 — entries render header + intro + per-entry bullet lines."""
    entries = (
        _entry(
            publish_date=date(2026, 5, 7),
            conclusion="상승 마감",
            drivers="반도체 강세",
        ),
        _entry(
            publish_date=date(2026, 5, 6),
            conclusion="혼조 마감",
            drivers="금리 경계",
        ),
    )
    rendered = _render_recent_context_block(
        segment=US_EQUITY,
        recent_context=_context(entries),
    )
    expected_body = (
        '- 2026-05-07: 결론="상승 마감" | 핵심 동인="반도체 강세"\n'
        '- 2026-05-06: 결론="혼조 마감" | 핵심 동인="금리 경계"'
    )
    expected = f"\n{RECENT_CONTEXT_HEADER}\n\n{RECENT_CONTEXT_INTRO}\n\n{expected_body}\n"
    assert rendered == expected


# ---------------------------------------------------------------------------
# _render_recent_entry — single-line shape pin
# ---------------------------------------------------------------------------


def test_render_recent_entry_shape_pins_single_line_format() -> None:
    line = _render_recent_entry(
        _entry(
            publish_date=date(2026, 5, 7),
            conclusion="상승 마감",
            drivers="반도체 강세",
        )
    )
    assert line == '- 2026-05-07: 결론="상승 마감" | 핵심 동인="반도체 강세"'
    # Single line — no embedded newlines.
    assert "\n" not in line


def test_render_recent_entry_empty_fields_render_placeholder() -> None:
    """Empty conclusion / drivers collapse to the ``(없음)`` sentinel."""
    line = _render_recent_entry(
        _entry(
            publish_date=date(2026, 5, 7),
            conclusion="",
            drivers="",
        )
    )
    assert line == '- 2026-05-07: 결론="(없음)" | 핵심 동인="(없음)"'
