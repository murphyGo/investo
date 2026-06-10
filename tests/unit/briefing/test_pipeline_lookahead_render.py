"""Branch tests for the u35 lookahead renderer in the pipeline.

Pins :func:`investo.briefing.pipeline._render_lookahead_context_block`
and the per-segment lookahead sub-cap inside
:func:`_select_llm_candidate_items` so future template tweaks cannot
silently change the bytes the LLM sees.

Branches covered:

1. No items with ``scheduled_at`` set → returns ``""`` so Stage 2
   prompt bytes are not spent on an empty optional block.
2. Items with ``scheduled_at`` set → emits the standard header +
   intro + one bullet per item.
3. Mixed bag (backward + forward items) → only the forward subset is
   rendered.
4. Lookahead sub-cap (12 / segment) → high-volume forward feeds do
   not starve the backward evidence path.
"""

from __future__ import annotations

from datetime import UTC, datetime

from investo.briefing.pipeline import (
    _render_lookahead_context_block,
    _select_llm_candidate_items,
)
from investo.briefing.prompts import LOOKAHEAD_HEADER
from investo.models import NormalizedItem


def _backward(idx: int, source: str = "yfinance-price") -> NormalizedItem:
    return NormalizedItem(
        source_name=source,
        category="price",
        title=f"backward-{idx}",
        published_at=datetime(2026, 5, 7, tzinfo=UTC),
    )


def _lookahead(idx: int, source: str = "nasdaq-earnings-calendar") -> NormalizedItem:
    return NormalizedItem(
        source_name=source,
        category="earnings",
        title=f"forward-{idx}",
        published_at=datetime(2026, 5, 7, tzinfo=UTC),
        scheduled_at=datetime(2026, 5, 10, tzinfo=UTC),
    )


def test_lookahead_block_empty_when_no_scheduled_items() -> None:
    """Pure backward bucket → optional block omitted."""
    items = (_backward(1), _backward(2), _backward(3))
    rendered = _render_lookahead_context_block(items)

    assert rendered == ""


def test_lookahead_block_renders_only_scheduled_items() -> None:
    """Mixed bucket → only ``scheduled_at is not None`` rows are rendered."""
    items = (_backward(1), _lookahead(1), _backward(2), _lookahead(2))
    rendered = _render_lookahead_context_block(items)

    assert LOOKAHEAD_HEADER in rendered
    assert "forward-1" in rendered
    assert "forward-2" in rendered
    # Backward items must not leak into the lookahead block.
    assert "backward-" not in rendered


def test_lookahead_block_carries_scheduled_date_per_row() -> None:
    """Each forward row prefixes its bullet with the scheduled date."""
    rendered = _render_lookahead_context_block((_lookahead(1),))
    assert "2026-05-10" in rendered
    assert "[nasdaq-earnings-calendar]" in rendered
    assert "forward-1" in rendered


def test_select_llm_candidate_items_caps_lookahead_at_twelve() -> None:
    """Sub-cap ``_MAX_LLM_LOOKAHEAD_ITEMS`` keeps a busy calendar from starving."""
    # 30 forward items from one source — the per-source cap is 24, the
    # lookahead sub-cap is 12, so 12 wins.
    forward_flood = tuple(_lookahead(i) for i in range(30))
    backward_signal = tuple(_backward(i, source=f"src-{i}") for i in range(5))
    selected = _select_llm_candidate_items(forward_flood + backward_signal)

    forward_selected = [item for item in selected if item.scheduled_at is not None]
    backward_selected = [item for item in selected if item.scheduled_at is None]
    assert len(forward_selected) == 12
    assert len(backward_selected) == 5


def test_select_llm_candidate_items_default_excludes_lookahead_when_absent() -> None:
    """No regression: pure backward input rounds-trips through the cap."""
    backward = tuple(_backward(i) for i in range(10))
    selected = _select_llm_candidate_items(backward)
    assert all(item.scheduled_at is None for item in selected)
