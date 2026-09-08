"""u151 Step 4 copy boundaries; no new finalizer/CFTC acceptance suite."""

from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType

import pytest
from hypothesis import given, note, seed, settings
from hypothesis import strategies as st

from investo.models.bundle_context import BundleContext, SharedMacroKey
from investo.models.facts import VerifiedFactBundle
from investo.models.segments import MarketSegment, SegmentCoverage
from investo.publisher import public_document
from investo.publisher.cross_market_cause_map import evaluate_cause_map
from tests._helpers.bundle_context_u151 import (
    ACTIVE_SUBSETS,
    KEY_SUBSETS,
    KEYS,
    SEGMENTS,
    TARGET_DATE,
    build_bundle_context,
    bundle_contexts,
)


def _public_context(bundle: BundleContext | None) -> public_document.PublicDocumentContext:
    return public_document.PublicDocumentContext(
        target_date=TARGET_DATE,
        expected_segments=SEGMENTS,
        input_absences={},
        anchors_by_segment={},
        items_by_segment={},
        coverage_by_segment={
            segment: SegmentCoverage(
                segment=segment,
                status="normal",
                item_count=0,
                source_count=0,
                categories=(),
                missing_categories=(),
            )
            for segment in SEGMENTS
        },
        source_outcomes=(),
        bundle_context=bundle,
        fact_bundle=VerifiedFactBundle(target_date=TARGET_DATE),
        entity_observed_at_utc=datetime(2026, 9, 5, tzinfo=UTC),
    )


@pytest.mark.parametrize("keys", KEY_SUBSETS)
@pytest.mark.parametrize("active", ACTIVE_SUBSETS)
def test_u151_snapshot_and_survivor_copies_preserve_selected_keys(
    keys: frozenset[SharedMacroKey],
    active: tuple[MarketSegment, ...],
) -> None:
    base = build_bundle_context(keys=keys)
    before = base.model_copy(deep=True)
    context = _public_context(base)
    copied = public_document._context_for_active_segments(context, active)
    snapshot = context.bundle_context
    survivor = copied.bundle_context
    assert snapshot is not None and survivor is not None
    assert snapshot is not base
    assert isinstance(snapshot.segments, MappingProxyType)
    assert isinstance(snapshot.daily_thesis_decision.per_segment_lines, MappingProxyType)
    assert snapshot.detected_macro_keys == survivor.detected_macro_keys == keys
    assert snapshot.shared_macro_block == survivor.shared_macro_block == base.shared_macro_block
    assert survivor.daily_thesis_signals == tuple(
        signal for signal in base.daily_thesis_signals if signal.segment in active
    )
    assert survivor.segments == base.segments  # Survivor selection does not re-route states.
    expected_mode = "omit" if len(active) < 2 else ("strong" if keys else "data_limited")
    assert survivor.daily_thesis_decision.mode == expected_mode
    assert base == before


def test_u151_snapshot_isolates_mutable_containers_without_losing_keys() -> None:
    base = build_bundle_context()
    context = _public_context(base)
    snapshot = context.bundle_context
    assert snapshot is not None
    original_lines = dict(snapshot.daily_thesis_decision.per_segment_lines)
    base.segments.clear()
    base.daily_thesis_decision.per_segment_lines.clear()
    assert set(snapshot.segments) == set(SEGMENTS)
    assert snapshot.daily_thesis_decision.per_segment_lines == original_lines
    assert snapshot.detected_macro_keys == frozenset(KEYS)
    with pytest.raises(TypeError):
        snapshot.segments[SEGMENTS[0]] = snapshot.segments[SEGMENTS[1]]
    with pytest.raises(TypeError):
        snapshot.daily_thesis_decision.per_segment_lines[SEGMENTS[0]] = "mutated"


def test_u151_survivor_does_not_reselect_broader_keys_from_narrow_signals() -> None:
    base = build_bundle_context(signal_keys=frozenset({"oil"}))
    for active in (SEGMENTS[:2], SEGMENTS[:1]):
        survivor = public_document._context_for_active_segments(_public_context(base), active)
        assert survivor.bundle_context is not None
        assert survivor.bundle_context.detected_macro_keys == frozenset(KEYS)
        assert {signal.key for signal in survivor.bundle_context.daily_thesis_signals} == {"oil"}
        assert survivor.bundle_context.daily_thesis_decision.macro_keys == (
            ("oil",) if len(active) == 2 else ()
        )
        # Cause evidence stays the base selection, independent of survivor thesis support.
        assert evaluate_cause_map(survivor.bundle_context) == evaluate_cause_map(base)


def test_u151_none_and_minimal_numeric_context_never_reconstruct_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_redecision(*args: object, **kwargs: object) -> BundleContext:
        pytest.fail("absent semantic context must not invoke redecision")

    monkeypatch.setattr(
        public_document, "redecide_daily_thesis_for_active_segments", forbidden_redecision
    )
    assert public_document._snapshot_bundle_context(None) is None
    absent = public_document._context_for_active_segments(_public_context(None), SEGMENTS[:2])
    assert absent.bundle_context is None
    base = _public_context(build_bundle_context())
    minimal = public_document._context_for_minimal_segment(base, SEGMENTS[0])
    assert minimal.bundle_context is None
    assert (
        public_document._context_for_active_segments(minimal, SEGMENTS[:1]).bundle_context is None
    )
    assert base.bundle_context is not None
    assert base.bundle_context.detected_macro_keys == frozenset(KEYS)


@seed(15120260908)
@settings(max_examples=60)
@given(base=bundle_contexts(), active=st.sampled_from(ACTIVE_SUBSETS))
def test_u151_property_transport_retains_keys_and_filters_only_original_signals(
    base: BundleContext,
    active: tuple[MarketSegment, ...],
) -> None:
    note("u151 seed=15120260908")
    before = base.model_copy(deep=True)
    # JSON round-trip applies to the ordinary model before internal snapshot wrappers.
    restored = BundleContext.model_validate_json(base.model_dump_json())
    assert restored == base
    context = _public_context(restored)
    copied = public_document._context_for_active_segments(context, active)
    assert copied.bundle_context is not None
    transported = copied.bundle_context
    assert transported.detected_macro_keys == base.detected_macro_keys
    assert transported.shared_macro_block == base.shared_macro_block
    assert transported.cross_market_core_allowed == base.cross_market_core_allowed
    assert transported.daily_thesis_signals == tuple(
        signal for signal in base.daily_thesis_signals if signal.segment in active
    )
    assert evaluate_cause_map(transported) == evaluate_cause_map(base)
    assert base == before
