"""Neutral pure owner for active-segment daily-thesis decisions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from investo.models.bundle_context import (
    CROSS_MARKET_CORE_ALLOWED,
    DAILY_THESIS_FALLBACK_LINE,
    BundleContext,
    DailyThesisDecision,
    DailyThesisSignal,
    SegmentDailyThesisInput,
)
from investo.models.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY, MarketSegment

_CANONICAL_SEGMENTS: Final[tuple[MarketSegment, ...]] = (
    DOMESTIC_EQUITY,
    US_EQUITY,
    CRYPTO,
)
_THESIS_CAUSE_TYPE_BY_KEY: Final[dict[str, str]] = {
    "oil": "geopolitical_oil_macro",
    "fomc": "fed_policy_event",
    "ust_yield": "fed_policy_event",
}
_THESIS_DRIVER_BY_CAUSE_TYPE: Final[dict[str, str]] = {
    "geopolitical_oil_macro": "유가와 지정학 변수",
    "fed_policy_event": "금리와 달러 변수",
    "global_systemic_risk": "공통 위험 요인",
}
_THESIS_IMPLICATION_BY_CAUSE_TYPE: Final[dict[str, str]] = {
    "geopolitical_oil_macro": "유동성 압력",
    "fed_policy_event": "금리·달러 민감도",
    "global_systemic_risk": "위험 선호의 방향",
}
_SEGMENT_THESIS_LABEL: Final[dict[str, str]] = {
    DOMESTIC_EQUITY: "국내",
    US_EQUITY: "미국",
    CRYPTO: "가상자산",
}
_SEGMENT_CONSEQUENCE_BY_CAUSE_TYPE: Final[dict[str, dict[str, str]]] = {
    "geopolitical_oil_macro": {
        DOMESTIC_EQUITY: "원/달러와 국내 수급",
        US_EQUITY: "섹터·실적 변동성",
        CRYPTO: "BTC·ETH 유동성",
    },
    "fed_policy_event": {
        DOMESTIC_EQUITY: "KOSPI·원/달러·외국인 수급",
        US_EQUITY: "Nasdaq·Dow 섹터 변동성",
        CRYPTO: "BTC·ETH 유동성",
    },
    "global_systemic_risk": {
        DOMESTIC_EQUITY: "KOSPI·KOSDAQ 국내 수급",
        US_EQUITY: "Dow·Nasdaq 변동성",
        CRYPTO: "BTC·ETH 정책·유동성",
    },
}
_SEGMENT_NATIVE_TERMS: Final[dict[str, tuple[str, ...]]] = {
    DOMESTIC_EQUITY: (
        "KOSPI",
        "KOSDAQ",
        "원/달러",
        "외국인",
        "기관",
        "반도체",
        "국내 수급",
    ),
    US_EQUITY: (
        "S&P 500",
        "Nasdaq",
        "Dow",
        "섹터",
        "실적",
        "CFTC",
        "변동성",
        "미국 금리",
    ),
    CRYPTO: ("BTC", "ETH", "도미넌스", "펀딩", "OI", "CFTC", "정책", "유동성"),
}


def _render_segment_daily_thesis_line(thesis_input: SegmentDailyThesisInput) -> str:
    if not thesis_input.evidence_labels:
        return DAILY_THESIS_FALLBACK_LINE
    native_terms = _SEGMENT_NATIVE_TERMS.get(thesis_input.segment, ())
    if not any(term in thesis_input.segment_consequence for term in native_terms):
        return DAILY_THESIS_FALLBACK_LINE
    return (
        f"> **오늘의 큰 그림:** {thesis_input.shared_driver}가 공통 변수지만, "
        f"{thesis_input.segment_consequence}를 먼저 확인해야 합니다."
    )


def _build_segment_daily_thesis_lines(
    *,
    cause_type: str,
    driver: str,
    supporting: Sequence[str],
    signals: Sequence[DailyThesisSignal],
    active_segments: Sequence[str],
) -> dict[str, str]:
    consequences = _SEGMENT_CONSEQUENCE_BY_CAUSE_TYPE.get(cause_type, {})
    evidence_by_segment: dict[str, list[str]] = {}
    supporting_set = set(supporting)
    for signal in signals:
        if signal.segment not in supporting_set:
            continue
        evidence_by_segment.setdefault(signal.segment, []).append(signal.evidence_label)
    lines: dict[str, str] = {}
    for segment in active_segments:
        thesis_input = SegmentDailyThesisInput(
            segment=segment,
            shared_driver=driver,
            segment_consequence=consequences.get(segment, ""),
            evidence_labels=tuple(dict.fromkeys(evidence_by_segment.get(segment, ()))),
        )
        lines[segment] = _render_segment_daily_thesis_line(thesis_input)
    return lines


def decide_daily_thesis_for_segments(
    active_segments: Sequence[MarketSegment | str],
    *,
    shared_keys: Sequence[str],
    signals: Sequence[DailyThesisSignal],
) -> DailyThesisDecision:
    """Return the deterministic thesis decision for the canonical active tuple."""

    active_set = set(active_segments)
    ordered_active = tuple(segment for segment in _CANONICAL_SEGMENTS if segment in active_set)
    if len(ordered_active) < 2:
        return DailyThesisDecision(mode="omit", reason="insufficient_successful_segments")

    segments_by_key: dict[str, set[str]] = {}
    for signal in signals:
        if signal.tier != "core" or signal.segment not in active_set:
            continue
        segments_by_key.setdefault(signal.key, set()).add(signal.segment)

    for key in shared_keys:
        cause_type = _THESIS_CAUSE_TYPE_BY_KEY.get(key)
        if cause_type is None or cause_type not in CROSS_MARKET_CORE_ALLOWED:
            continue
        supporting_set = segments_by_key.get(key, set())
        supporting = tuple(segment for segment in _CANONICAL_SEGMENTS if segment in supporting_set)
        if len(supporting) < 2:
            continue
        driver = _THESIS_DRIVER_BY_CAUSE_TYPE[cause_type]
        implication = _THESIS_IMPLICATION_BY_CAUSE_TYPE[cause_type]
        labels = "·".join(_SEGMENT_THESIS_LABEL.get(segment, segment) for segment in supporting)
        line = (
            f"> **오늘의 큰 그림:** {driver}가 {labels}에 동시에 걸리며, "
            f"오늘 독자는 {implication}을 먼저 확인해야 합니다."
        )
        return DailyThesisDecision(
            mode="strong",
            line=line,
            per_segment_lines=_build_segment_daily_thesis_lines(
                cause_type=cause_type,
                driver=driver,
                supporting=supporting,
                signals=signals,
                active_segments=ordered_active,
            ),
            macro_keys=(key,),
            supporting_segments=supporting,
            reason="shared_core_signal",
        )

    return DailyThesisDecision(
        mode="data_limited",
        line=(
            "> **오늘의 큰 그림:** 공통 핵심 신호가 제한적이어서, "
            "오늘은 세그먼트별 데이터 상태를 먼저 확인해야 합니다."
        ),
        per_segment_lines={segment: DAILY_THESIS_FALLBACK_LINE for segment in ordered_active},
        reason="no_shared_core_signal",
        supporting_segments=ordered_active,
    )


def redecide_daily_thesis_for_active_segments(
    context: BundleContext,
    active_segments: Sequence[MarketSegment | str],
) -> BundleContext:
    """Scope one immutable base context to the current survivor tuple."""

    active_set = set(active_segments)
    filtered_signals = tuple(
        signal for signal in context.daily_thesis_signals if signal.segment in active_set
    )
    shared_keys = tuple(dict.fromkeys(signal.key for signal in context.daily_thesis_signals))
    decision = decide_daily_thesis_for_segments(
        active_segments,
        shared_keys=shared_keys,
        signals=filtered_signals,
    )
    return context.model_copy(
        update={
            "daily_thesis_signals": filtered_signals,
            "daily_thesis_decision": decision,
        }
    )


__all__ = [
    "decide_daily_thesis_for_segments",
    "redecide_daily_thesis_for_active_segments",
]
