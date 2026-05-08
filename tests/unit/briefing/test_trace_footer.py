"""Tests for u32 Step 3 — traceability footer + hashed signatures."""

from __future__ import annotations

from datetime import UTC, datetime

from investo.briefing.trace_footer import (
    compute_input_hash,
    compute_stage1_hash,
    compute_stage2_hash,
    render_traceability_footer,
)
from investo.models import NormalizedItem


def _item(idx: int) -> NormalizedItem:
    return NormalizedItem(
        source_name=f"src-{idx}",
        category="news",
        title=f"item {idx}",
        published_at=datetime(2026, 5, 9, tzinfo=UTC),
        raw_metadata={"k": str(idx)},
    )


def test_compute_input_hash_is_deterministic_and_12_chars() -> None:
    items = [_item(0), _item(1)]
    h = compute_input_hash(items)
    assert len(h) == 12
    assert all(ch in "0123456789abcdef" for ch in h)
    # Same input → identical hash.
    assert compute_input_hash(items) == h


def test_compute_input_hash_differs_for_different_items() -> None:
    a = compute_input_hash([_item(0)])
    b = compute_input_hash([_item(1)])
    assert a != b


def test_compute_stage1_hash_stable_under_key_order() -> None:
    h1 = compute_stage1_hash({"assignments": {1: 2, 0: 3}, "unassigned": []})
    h2 = compute_stage1_hash({"unassigned": [], "assignments": {0: 3, 1: 2}})
    # Sorted keys at JSON-encode time → identical hash.
    assert h1 == h2


def test_compute_stage2_hash_changes_when_text_changes() -> None:
    h1 = compute_stage2_hash("body markdown v1")
    h2 = compute_stage2_hash("body markdown v2")
    assert h1 != h2


def test_render_footer_carries_three_hash_lines() -> None:
    items = [_item(0), _item(1)]
    classification = {"assignments": {0: 2, 1: 3}, "unassigned": []}
    out = render_traceability_footer(items, classification, "## ① 요약\n...")
    assert "<details>" in out
    assert "</details>" in out
    assert "📑 트레이스 + 서명" in out
    assert "input_hash" in out
    assert "stage1_hash" in out
    assert "stage2_hash" in out


def test_render_footer_lists_every_item_with_section_assignment() -> None:
    items = [_item(0), _item(1)]
    classification = {"assignments": {0: 2, 1: 5}, "unassigned": []}
    out = render_traceability_footer(items, classification, "body")
    assert "| 0 | src-0 | news | 2 |" in out
    assert "| 1 | src-1 | news | 5 |" in out


def test_render_footer_handles_unassigned_items() -> None:
    items = [_item(0)]
    classification = {"assignments": {}, "unassigned": [0]}
    out = render_traceability_footer(items, classification, "body")
    assert "| 0 | src-0 | news | — |" in out


def test_render_footer_truncates_long_titles() -> None:
    long_item = NormalizedItem(
        source_name="src",
        category="news",
        title="x" * 200,
        published_at=datetime(2026, 5, 9, tzinfo=UTC),
        raw_metadata={},
    )
    out = render_traceability_footer([long_item], {"assignments": {0: 2}}, "body")
    assert "…" in out
    # Long title doesn't appear in full.
    assert "x" * 200 not in out
