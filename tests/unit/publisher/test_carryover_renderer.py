"""u52 — publisher carryover block renderer + injector pins.

Three shape pins:

* :func:`render_carryover_block` emits a 4-column markdown table for a
  populated bundle; empty bundle returns an empty string.
* :func:`inject_carryover_block` inserts the block between §② and §③
  the first time; replaces an existing block on a re-run (idempotent).
* Empty block + stale prior block in the markdown → stale block
  stripped (the renderer's single-source-of-truth contract holds even
  when input carries leftover bytes).
"""

from __future__ import annotations

from datetime import date

from investo.models import BriefingCarryover, CarryoverItem
from investo.publisher.carryover import (
    CARRYOVER_BLOCK_HEADING,
    inject_carryover_block,
    render_carryover_block,
)


def _item(
    *,
    topic: str = "ARM 어닝",
    status: str = "unresolved",
    expected: date | None = date(2026, 5, 8),
) -> CarryoverItem:
    return CarryoverItem(
        event_type="earnings",
        ticker_or_topic=topic,
        originated_date=date(2026, 5, 6),
        expected_date=expected,
        status=status,  # type: ignore[arg-type]
        note=None,
    )


def _markdown_stub() -> str:
    """Mimic a Stage 2 segmented body with §② → §③ boundary."""
    return (
        "# 2026-05-08 미국 증시 시황\n"
        "\n"
        "## ① 요약\n\n요약 본문.\n\n"
        "---\n\n"
        "## ② 전일 핵심 이슈\n\n②본문.\n\n"
        "---\n\n"
        "## ③ 섹터/수급 동향\n\n섹터.\n\n"
        "---\n\n"
        "## ⑥ 오늘의 관전 포인트\n\n관전.\n"
    )


def test_render_empty_carryover_returns_empty_string() -> None:
    empty = BriefingCarryover(prior_resolved=(), prior_unresolved=(), lookback_days=0)
    assert render_carryover_block(empty) == ""


def test_render_populated_carryover_emits_table() -> None:
    bundle = BriefingCarryover(
        prior_resolved=(_item(topic="ARM 어닝", status="resolved"),),
        prior_unresolved=(
            _item(topic="LNG 어닝", status="unresolved", expected=date(2026, 5, 7)),
            _item(topic="FOMC 의사록", status="carried_over", expected=date(2026, 5, 20)),
        ),
        lookback_days=2,
    )
    block = render_carryover_block(bundle)
    assert block.startswith(CARRYOVER_BLOCK_HEADING)
    assert "| 이벤트 | 발원일 | 기대일 | 상태 |" in block
    # Korean labels present
    assert "확인됨" in block
    assert "미확인" in block
    assert "이월" in block
    # Order: resolved first, then unresolved+carried_over per parser split.
    arm_idx = block.find("ARM 어닝")
    lng_idx = block.find("LNG 어닝")
    fomc_idx = block.find("FOMC 의사록")
    assert -1 < arm_idx < lng_idx < fomc_idx


def test_inject_carryover_inserts_before_section_three() -> None:
    bundle = BriefingCarryover(
        prior_resolved=(_item(status="resolved"),),
        prior_unresolved=(),
        lookback_days=1,
    )
    block = render_carryover_block(bundle)
    markdown = _markdown_stub()
    out = inject_carryover_block(markdown, block)
    section_two_idx = out.find("## ② 전일 핵심 이슈")
    block_idx = out.find(CARRYOVER_BLOCK_HEADING)
    section_three_idx = out.find("## ③ 섹터/수급 동향")
    assert -1 < section_two_idx < block_idx < section_three_idx


def test_inject_carryover_is_idempotent() -> None:
    """Calling inject twice with the same block returns equal markdown."""
    bundle = BriefingCarryover(
        prior_resolved=(_item(status="resolved"),),
        prior_unresolved=(_item(topic="LNG", status="unresolved", expected=None),),
        lookback_days=1,
    )
    block = render_carryover_block(bundle)
    once = inject_carryover_block(_markdown_stub(), block)
    twice = inject_carryover_block(once, block)
    assert once == twice
    # Block appears exactly once.
    assert twice.count(CARRYOVER_BLOCK_HEADING) == 1


def test_inject_carryover_replaces_existing_block_on_rerun() -> None:
    """A same-day re-run with different rows replaces the existing block."""
    bundle_v1 = BriefingCarryover(
        prior_resolved=(_item(topic="ARM 어닝", status="resolved"),),
        prior_unresolved=(),
        lookback_days=1,
    )
    bundle_v2 = BriefingCarryover(
        prior_resolved=(),
        prior_unresolved=(_item(topic="DIFFERENT 토픽", status="unresolved"),),
        lookback_days=1,
    )
    md_v1 = inject_carryover_block(_markdown_stub(), render_carryover_block(bundle_v1))
    md_v2 = inject_carryover_block(md_v1, render_carryover_block(bundle_v2))
    assert md_v2.count(CARRYOVER_BLOCK_HEADING) == 1
    assert "DIFFERENT 토픽" in md_v2
    assert "ARM 어닝" not in md_v2


def test_inject_carryover_empty_block_strips_stale_block() -> None:
    """Empty block + pre-existing stale block in markdown → stale stripped."""
    bundle_v1 = BriefingCarryover(
        prior_resolved=(_item(topic="ARM 어닝", status="resolved"),),
        prior_unresolved=(),
        lookback_days=1,
    )
    md_v1 = inject_carryover_block(_markdown_stub(), render_carryover_block(bundle_v1))
    assert CARRYOVER_BLOCK_HEADING in md_v1

    md_v2 = inject_carryover_block(md_v1, "")  # empty render
    assert CARRYOVER_BLOCK_HEADING not in md_v2


def test_inject_carryover_empty_block_leaves_clean_markdown_alone() -> None:
    base = _markdown_stub()
    assert inject_carryover_block(base, "") == base


def test_inject_carryover_appends_when_no_section_three() -> None:
    """Defensive — body lacking §③ heading still gets the block (appended)."""
    minimal = "# Title\n\n## ① 요약\n\n요약.\n\n## ② 전일 핵심 이슈\n\n핵심.\n"
    bundle = BriefingCarryover(
        prior_resolved=(_item(status="resolved"),),
        prior_unresolved=(),
        lookback_days=1,
    )
    out = inject_carryover_block(minimal, render_carryover_block(bundle))
    assert CARRYOVER_BLOCK_HEADING in out


def test_inject_carryover_table_cell_escapes_pipe() -> None:
    """Pipe characters in ticker_or_topic must be escaped to keep the row intact."""
    bundle = BriefingCarryover(
        prior_resolved=(),
        prior_unresolved=(_item(topic="HE|RE", status="unresolved"),),
        lookback_days=1,
    )
    block = render_carryover_block(bundle)
    # The literal "|" inside the topic must be backslash-escaped so the
    # row stays 4 columns.
    assert "HE\\|RE" in block
