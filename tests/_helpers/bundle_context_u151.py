"""Synthetic validated contexts shared by u151 transport tests."""

from __future__ import annotations

from datetime import date

from hypothesis import strategies as st

from investo._internal.daily_thesis_decision import decide_daily_thesis_for_segments
from investo.models.bundle_context import (
    BundleContext,
    CloseState,
    DailyThesisSignal,
    MarketStateSummary,
    SharedMacroKey,
)
from investo.models.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY, MarketSegment

TARGET_DATE = date(2026, 9, 5)
KEYS: tuple[SharedMacroKey, ...] = ("fomc", "oil", "ust_yield")
SEGMENTS: tuple[MarketSegment, ...] = (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)
KEY_SUBSETS: tuple[frozenset[SharedMacroKey], ...] = tuple(
    frozenset(key for index, key in enumerate(KEYS) if mask & (1 << index)) for mask in range(8)
)
ACTIVE_SUBSETS: tuple[tuple[MarketSegment, ...], ...] = tuple(
    tuple(segment for index, segment in enumerate(SEGMENTS) if mask & (1 << index))
    for mask in range(8)
)


def build_bundle_context(
    *,
    keys: frozenset[SharedMacroKey] = frozenset(KEYS),
    signal_keys: frozenset[SharedMacroKey] | None = None,
    block: str | None = "공통 관찰 자료 — 표시 문구",
    close_state: CloseState = "close",
) -> BundleContext:
    """Explicit evidence keys; never parse or derive keys from the block."""
    supported = keys if signal_keys is None else signal_keys
    signals = tuple(
        DailyThesisSignal(
            segment=segment,
            key=key,
            tier="core",
            evidence_label=key,
            source_ids=(f"synthetic-{key}",),
        )
        for key in sorted(supported)
        for segment in sorted(SEGMENTS)
    )
    return BundleContext(
        bundle_id="u151-transport",
        target_kst_date=TARGET_DATE,
        segments={
            segment: MarketStateSummary(
                segment=segment,
                target_date=TARGET_DATE,
                tz="UTC",
                close_state=close_state,
                headline_native_fact=f"{segment} 관찰",
            )
            for segment in SEGMENTS
        },
        shared_macro_block=block,
        detected_macro_keys=keys,
        daily_thesis_signals=signals,
        daily_thesis_decision=decide_daily_thesis_for_segments(
            SEGMENTS,
            shared_keys=sorted(keys),
            signals=signals,
        ),
    )


@st.composite
def bundle_contexts(draw: st.DrawFn) -> BundleContext:
    keys = draw(st.sampled_from(KEY_SUBSETS))
    supported = draw(st.frozensets(st.sampled_from(sorted(keys)))) if keys else frozenset()
    return build_bundle_context(
        keys=keys,
        signal_keys=supported,
        block=draw(st.sampled_from((None, "", "선택된 공통 관찰 자료"))),
        close_state=draw(st.sampled_from(("close", "pending"))),
    )
