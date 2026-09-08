"""u151 context transport preserves the explicit minimal prompt projection."""

from __future__ import annotations

import json

import pytest
from hypothesis import given, note, seed, settings
from hypothesis import strategies as st

from investo.briefing._reader_enhance.context_render import _render_bundle_context_block
from investo.briefing.generation_contract import GenerationInput
from investo.briefing.watchlist import WatchlistConfig
from investo.models.bundle_context import BundleContext, SharedMacroKey
from investo.models.segments import MarketSegment
from tests._helpers.bundle_context_u151 import (
    KEY_SUBSETS,
    SEGMENTS,
    TARGET_DATE,
    build_bundle_context,
    bundle_contexts,
)


def test_u151_generation_input_keeps_exact_context_and_none() -> None:
    for context in (None, build_bundle_context()):
        request = GenerationInput(
            target_date=TARGET_DATE,
            items=(),
            watchlist_config=WatchlistConfig(),
            bundle_context=context,
        )
        assert request.bundle_context is context
    assert _render_bundle_context_block(None, segment=SEGMENTS[0]) == ""


@pytest.mark.parametrize("keys", KEY_SUBSETS)
def test_u151_self_pending_copy_and_noop_branches_retain_keys(
    keys: frozenset[SharedMacroKey],
) -> None:
    base = build_bundle_context(keys=keys)
    copied = base.with_self_pending(SEGMENTS[0])
    assert copied is not base
    assert copied.detected_macro_keys == keys
    assert copied.daily_thesis_decision == base.daily_thesis_decision
    assert copied.segments[SEGMENTS[0]].close_state == "pending"
    assert base.segments[SEGMENTS[0]].close_state == "close"
    assert copied.with_self_pending(SEGMENTS[0]) is copied
    assert base.with_self_pending("missing-segment") is base
    assert copied.model_dump(mode="json")["detected_macro_keys"] == sorted(keys)
    assert BundleContext.model_validate_json(copied.model_dump_json()) == copied


@seed(15120260908)
@settings(max_examples=60)
@given(base=bundle_contexts(), segment=st.sampled_from((*SEGMENTS, None)))
def test_u151_property_prompt_projection_preserves_only_existing_fields(
    base: BundleContext,
    segment: MarketSegment | None,
) -> None:
    note("u151 seed=15120260908")
    before = base.model_copy(deep=True)
    rendered = _render_bundle_context_block(base, segment=segment)
    payload = json.loads(rendered[rendered.index("{") :])
    assert set(payload) == {
        "bundle_id",
        "target_kst_date",
        "segments",
        "shared_macro_present",
        "cross_market_core_allowed",
    }
    assert payload["bundle_id"] == base.bundle_id
    assert payload["target_kst_date"] == base.target_kst_date.isoformat()
    assert payload["shared_macro_present"] is (base.shared_macro_block is not None)
    assert payload["cross_market_core_allowed"] == sorted(base.cross_market_core_allowed)
    for name, summary in base.segments.items():
        assert payload["segments"][name] == {
            "close_state": "pending" if name == segment else summary.close_state,
            "headline_native_fact": summary.headline_native_fact,
        }
    # No complete model dump, typed key transport, source payload or thesis data in prompt.
    assert "detected_macro_keys" not in rendered
    assert "daily_thesis" not in rendered
    assert base == before
