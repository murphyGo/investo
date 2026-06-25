"""Pre-Stage-2 :class:`BundleContext` computation (u57).

Called by the orchestrator immediately after routing — *before* any
segment's Stage-2 prompt is built. Walks each segment's routed
:class:`NormalizedItem`\\s, derives a deterministic close-state via
:func:`investo.briefing.time_state.detect_time_state`, and detects
shared-macro candidates whose source title shape appears in two or
more segments simultaneously (the canonical trigger from u57 plan
Step 1.5).

Purity contract
---------------

The function is pure: ``(routed, now_kst) → BundleContext`` is fully
deterministic for a given input. Only side effect is structured
logging via :data:`_logger`. ``now_kst`` is passed in (never read from
:func:`datetime.now`) so replay tests remain reproducible.

References
----------

* u57 plan Step 1.5 — pre-computation algorithm.
* u57 DoD — "BundleContext is computed before Stage 2 and injected as
  the same object into all three prompts".
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha1
from typing import Final

from investo._internal.redaction import RedactionPolicy, redact_text
from investo.briefing.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
)
from investo.briefing.time_state import TimeState, detect_time_state
from investo.models import Category, NormalizedItem
from investo.models.bundle_context import (
    CROSS_MARKET_CORE_ALLOWED,
    DAILY_THESIS_FALLBACK_LINE,
    BundleContext,
    CloseState,
    DailyThesisDecision,
    DailyThesisSignal,
    MarketStateSummary,
    SegmentDailyThesisInput,
)

_logger = logging.getLogger(__name__)


_SEGMENT_TZ: Final[dict[MarketSegment, str]] = {
    DOMESTIC_EQUITY: "Asia/Seoul",
    US_EQUITY: "America/New_York",
    CRYPTO: "UTC",
}


_CANONICAL_UST_SOURCES: Final[frozenset[str]] = frozenset({"treasury-rates", "fred-macro"})
_CANONICAL_FOMC_SOURCES: Final[frozenset[str]] = frozenset(
    {"fomc-calendar", "fomc-rss", "fred-economic-calendar"}
)
_SOURCE_RANKS: Final[dict[str, dict[str, int]]] = {
    "ust_yield": {"treasury-rates": 0, "fred-macro": 1},
    "fomc": {"fomc-calendar": 0, "fomc-rss": 1, "fred-economic-calendar": 2},
}
_CATEGORY_RANKS: Final[dict[Category, int]] = {"macro": 0, "calendar": 1, "news": 2}

_DGS_RATE_RE: Final[re.Pattern[str]] = re.compile(r"\bDGS(?:10|2|30|3MO)\b", re.IGNORECASE)
_UST_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"(?<![A-Za-z])UST(?![A-Za-z])", re.IGNORECASE)
_UST_CONTEXT_RE: Final[re.Pattern[str]] = re.compile(
    r"(\b(?:yield|curve|rate|10Y|2Y|30Y|3M|2Y10Y|3M10Y)\b|Treasur(?:y|ies)|금리|수익률)",
    re.IGNORECASE,
)
_US_TREASURY_KR_RE: Final[re.Pattern[str]] = re.compile(r"(미\s*국채|미국\s*국채|미국채)")
_BARE_TREASURY_KR_RE: Final[re.Pattern[str]] = re.compile(r"국채")
_TREASURY_WORD_RE: Final[re.Pattern[str]] = re.compile(r"\bTreasur(?:y|ies)\b", re.IGNORECASE)
_OIL_RE: Final[re.Pattern[str]] = re.compile(
    r"(\bWTI\b|\bBrent\b|브렌트|국제\s?유가|원유)", re.IGNORECASE
)
_FOMC_RE: Final[re.Pattern[str]] = re.compile(r"\bFOMC\b|연준|기준금리", re.IGNORECASE)
_FED_WORD_RE: Final[re.Pattern[str]] = re.compile(r"(\bFed\b|Federal Reserve)", re.IGNORECASE)
_FED_CONTEXT_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(meeting|rate|decision|minutes|statement)\b|기준금리",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class _SharedMacroCandidate:
    key: str
    segment: MarketSegment
    title: str
    source_name: str
    category: Category
    source_rank: int
    category_rank: int
    title_rank: int

    def sort_key(self) -> tuple[int, int, int, str, str, MarketSegment]:
        return (
            self.source_rank,
            self.category_rank,
            self.title_rank,
            self.source_name,
            self.title,
            self.segment,
        )


def _title_hash(title: str) -> str:
    return sha1(title.encode("utf-8")).hexdigest()[:12]


def _safe_title_preview(title: str) -> str:
    preview = title if len(title) <= 120 else title[:117] + "..."
    return redact_text(preview, policy=RedactionPolicy.STRICT)


def _log_candidate(
    event: str,
    *,
    key: str,
    segment: MarketSegment,
    item: NormalizedItem,
    reason: str,
) -> None:
    _logger.info(
        event,
        extra={
            "key": key,
            "segment": segment,
            "source_name": item.source_name,
            "category": item.category,
            "reason": reason,
            "title_preview": _safe_title_preview(item.title),
            "title_hash": _title_hash(item.title),
        },
    )


def _has_near(
    text: str,
    anchor_re: re.Pattern[str],
    context_re: re.Pattern[str],
    *,
    max_gap: int = 40,
) -> bool:
    anchors = tuple(anchor_re.finditer(text))
    contexts = tuple(context_re.finditer(text))
    for anchor in anchors:
        for context in contexts:
            if anchor.end() <= context.start():
                gap = context.start() - anchor.end()
            elif context.end() <= anchor.start():
                gap = anchor.start() - context.end()
            else:
                gap = 0
            if gap <= max_gap:
                return True
    return False


def _matches_ust_yield(item: NormalizedItem) -> bool:
    title = item.title
    if _DGS_RATE_RE.search(title):
        return True
    if _has_near(title, _US_TREASURY_KR_RE, _UST_CONTEXT_RE):
        return True
    if item.source_name in _CANONICAL_UST_SOURCES and _has_near(
        title, _BARE_TREASURY_KR_RE, _UST_CONTEXT_RE
    ):
        return True
    if _has_near(title, _UST_TOKEN_RE, _UST_CONTEXT_RE):
        return True
    return _has_near(title, _TREASURY_WORD_RE, _UST_CONTEXT_RE)


def _matches_oil(item: NormalizedItem) -> bool:
    return _OIL_RE.search(item.title) is not None


def _matches_fomc(item: NormalizedItem) -> bool:
    title = item.title
    return _FOMC_RE.search(title) is not None or _has_near(title, _FED_WORD_RE, _FED_CONTEXT_RE)


_SHARED_MACRO_MATCHERS: Final[dict[str, Callable[[NormalizedItem], bool]]] = {
    "ust_yield": _matches_ust_yield,
    "oil": _matches_oil,
    "fomc": _matches_fomc,
}

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
    DOMESTIC_EQUITY: ("KOSPI", "KOSDAQ", "원/달러", "외국인", "기관", "반도체", "국내 수급"),
    US_EQUITY: ("S&P 500", "Nasdaq", "Dow", "섹터", "실적", "CFTC", "변동성", "미국 금리"),
    CRYPTO: ("BTC", "ETH", "도미넌스", "펀딩", "OI", "CFTC", "정책", "유동성"),
}


def _source_rank(key: str, source_name: str) -> int:
    return _SOURCE_RANKS.get(key, {}).get(source_name, 9)


def _category_rank(category: Category) -> int:
    return _CATEGORY_RANKS.get(category, 9)


def _title_rank(key: str, title: str) -> int:
    if key == "ust_yield":
        if _DGS_RATE_RE.search(title):
            return 0
        if re.search(r"\b(?:10Y|2Y|30Y|2Y10Y|3M10Y)\b|수익률|금리", title, re.IGNORECASE):
            return 1
        if _UST_TOKEN_RE.search(title):
            return 2
        return 3
    if key == "fomc":
        if re.search(r"\bFOMC\b", title, re.IGNORECASE):
            return 0
        if _has_near(title, _FED_WORD_RE, _FED_CONTEXT_RE):
            return 1
        return 2
    if key == "oil":
        if re.search(r"\bWTI\b|\bBrent\b|브렌트", title, re.IGNORECASE):
            return 0
        return 1
    return 9


def _rejection_reason(key: str, item: NormalizedItem) -> str | None:
    title = item.title
    if key == "ust_yield":
        lowered = title.lower()
        if any(term in lowered for term in ("ust", "treasury", "treasuries")) or "국채" in title:
            return "missing_ust_rate_context"
    if key == "oil" and re.search(r"WTI|Brent", title, re.IGNORECASE):
        return "missing_oil_boundary_or_context"
    if key == "fomc" and re.search(r"FOMC|Federal Reserve|\bFed\b|연준", title, re.IGNORECASE):
        return "missing_fomc_boundary_or_context"
    return None


def _candidate_for(
    key: str,
    segment: MarketSegment,
    item: NormalizedItem,
) -> _SharedMacroCandidate:
    return _SharedMacroCandidate(
        key=key,
        segment=segment,
        title=item.title,
        source_name=item.source_name,
        category=item.category,
        source_rank=_source_rank(key, item.source_name),
        category_rank=_category_rank(item.category),
        title_rank=_title_rank(key, item.title),
    )


def _select_close_state_for_segment(
    items: Sequence[NormalizedItem],
) -> tuple[CloseState, str | None]:
    """Pick a segment's representative close-state.

    Algorithm:
    1. For each item with a published_at, detect_time_state on title.
    2. Take the *latest* (by published_at) item whose detect succeeded.
    3. That item supplies the close_state + a one-line headline fact
       (the title itself, truncated to ~120 chars).

    Returns ``("pending", None)`` when no item produces a label.
    """
    best: tuple[datetime, TimeState, str] | None = None
    for item in items:
        state = detect_time_state(item.title)
        if state is None:
            continue
        if best is None or item.published_at > best[0]:
            best = (item.published_at, state, item.title)
    if best is None:
        return "pending", None
    _, state, title = best
    headline = title if len(title) <= 120 else title[:117] + "..."
    return state, headline


def _detect_shared_macros(
    routed: Mapping[MarketSegment, Sequence[NormalizedItem]],
) -> list[tuple[str, str]]:
    """Return list of (macro_key, evidence_title) for keys hit by ≥ 2 segments."""
    candidates_by_key: dict[str, list[_SharedMacroCandidate]] = {}
    for segment, items in routed.items():
        for item in items:
            for key, matcher in _SHARED_MACRO_MATCHERS.items():
                if matcher(item):
                    candidate = _candidate_for(key, segment, item)
                    candidates_by_key.setdefault(key, []).append(candidate)
                    _log_candidate(
                        "shared_macro.candidate_accepted",
                        key=key,
                        segment=segment,
                        item=item,
                        reason="matched",
                    )
                    continue
                reason = _rejection_reason(key, item)
                if reason is not None:
                    _log_candidate(
                        "shared_macro.candidate_rejected",
                        key=key,
                        segment=segment,
                        item=item,
                        reason=reason,
                    )
    shared: list[tuple[str, str]] = []
    for key, candidates in candidates_by_key.items():
        segments = {candidate.segment for candidate in candidates}
        if len(segments) < 2:
            continue
        if key == "ust_yield" and not any(
            candidate.source_name in _CANONICAL_UST_SOURCES for candidate in candidates
        ):
            representative = min(candidates, key=lambda candidate: candidate.sort_key())
            _logger.info(
                "shared_macro.key_suppressed",
                extra={
                    "key": key,
                    "segment": representative.segment,
                    "source_name": representative.source_name,
                    "category": representative.category,
                    "reason": "missing_canonical_ust_source",
                    "title_preview": _safe_title_preview(representative.title),
                    "title_hash": _title_hash(representative.title),
                },
            )
            continue
        representative = min(candidates, key=lambda candidate: candidate.sort_key())
        _logger.info(
            "shared_macro.representative_selected",
            extra={
                "key": key,
                "segment": representative.segment,
                "source_name": representative.source_name,
                "category": representative.category,
                "reason": "selected",
                "title_preview": _safe_title_preview(representative.title),
                "title_hash": _title_hash(representative.title),
            },
        )
        shared.append((key, representative.title))
    # Sort by macro key for deterministic ordering.
    shared.sort(key=lambda pair: pair[0])
    return shared


_MACRO_KEY_LABELS: Final[dict[str, str]] = {
    "ust_yield": "미 국채 수익률",
    "oil": "국제 유가",
    "fomc": "FOMC 일정",
}


def _render_shared_macro_block(shared: Sequence[tuple[str, str]]) -> str | None:
    """Render the ``## ⓪ 오늘의 매크로`` body.

    Returns ``None`` when no macro hits ≥ 2 segments — caller skips H2
    injection in that case.
    """
    if not shared:
        return None
    lines = [f"- **{_MACRO_KEY_LABELS.get(key, key)}** — {evidence}" for key, evidence in shared]
    return "\n".join(lines)


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
    successful_segments: Sequence[str],
) -> dict[str, str]:
    consequences = _SEGMENT_CONSEQUENCE_BY_CAUSE_TYPE.get(cause_type, {})
    evidence_by_segment: dict[str, list[str]] = {}
    supporting_set = set(supporting)
    for signal in signals:
        if signal.segment not in supporting_set:
            continue
        evidence_by_segment.setdefault(signal.segment, []).append(signal.evidence_label)
    lines: dict[str, str] = {}
    for segment in successful_segments:
        thesis_input = SegmentDailyThesisInput(
            segment=segment,
            shared_driver=driver,
            segment_consequence=consequences.get(segment, ""),
            evidence_labels=tuple(dict.fromkeys(evidence_by_segment.get(segment, ()))),
        )
        lines[segment] = _render_segment_daily_thesis_line(thesis_input)
    return lines


def _daily_thesis_signals(
    routed: Mapping[MarketSegment, Sequence[NormalizedItem]],
    *,
    shared: Sequence[tuple[str, str]],
) -> tuple[DailyThesisSignal, ...]:
    shared_keys = {key for key, _title in shared}
    signals: list[DailyThesisSignal] = []
    for segment, items in routed.items():
        for item in items:
            for key in shared_keys:
                matcher = _SHARED_MACRO_MATCHERS.get(key)
                if matcher is None or not matcher(item):
                    continue
                signals.append(
                    DailyThesisSignal(
                        segment=segment,
                        key=key,
                        tier="core",
                        evidence_label=_MACRO_KEY_LABELS.get(key, key),
                        source_ids=(item.source_name,),
                    )
                )
                break
    return tuple(
        sorted(
            signals,
            key=lambda signal: (
                signal.key,
                signal.segment,
                signal.evidence_label,
                signal.source_ids,
            ),
        )
    )


def _decide_daily_thesis(
    routed: Mapping[MarketSegment, Sequence[NormalizedItem]],
    *,
    shared: Sequence[tuple[str, str]],
    signals: Sequence[DailyThesisSignal],
) -> DailyThesisDecision:
    successful_segments = tuple(segment for segment, items in routed.items() if items)
    return _decide_daily_thesis_for_segments(
        successful_segments,
        shared_keys=tuple(key for key, _title in shared),
        signals=signals,
    )


def _decide_daily_thesis_for_segments(
    successful_segments: Sequence[MarketSegment | str],
    *,
    shared_keys: Sequence[str],
    signals: Sequence[DailyThesisSignal],
) -> DailyThesisDecision:
    successful_set = set(successful_segments)
    ordered_successful = tuple(
        segment for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO) if segment in successful_set
    )
    if len(ordered_successful) < 2:
        return DailyThesisDecision(mode="omit", reason="insufficient_successful_segments")

    segments_by_key: dict[str, set[str]] = {}
    for signal in signals:
        if signal.tier != "core" or signal.segment not in successful_set:
            continue
        segments_by_key.setdefault(signal.key, set()).add(signal.segment)

    for key in shared_keys:
        cause_type = _THESIS_CAUSE_TYPE_BY_KEY.get(key)
        if cause_type is None or cause_type not in CROSS_MARKET_CORE_ALLOWED:
            continue
        supporting_set = segments_by_key.get(key, set())
        supporting = tuple(
            segment for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO) if segment in supporting_set
        )
        if len(supporting) < 2:
            continue
        driver = _THESIS_DRIVER_BY_CAUSE_TYPE[cause_type]
        implication = _THESIS_IMPLICATION_BY_CAUSE_TYPE[cause_type]
        labels = "·".join(_SEGMENT_THESIS_LABEL.get(segment, segment) for segment in supporting)
        line = (
            f"> **오늘의 큰 그림:** {driver}가 {labels}에 동시에 걸리며, "
            f"오늘 독자는 {implication}을 먼저 확인해야 합니다."
        )
        per_segment_lines = _build_segment_daily_thesis_lines(
            cause_type=cause_type,
            driver=driver,
            supporting=supporting,
            signals=signals,
            successful_segments=ordered_successful,
        )
        return DailyThesisDecision(
            mode="strong",
            line=line,
            per_segment_lines=per_segment_lines,
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
        per_segment_lines={segment: DAILY_THESIS_FALLBACK_LINE for segment in ordered_successful},
        reason="no_shared_core_signal",
        supporting_segments=ordered_successful,
    )


def redecide_daily_thesis_for_successful_segments(
    context: BundleContext,
    successful_segments: Sequence[MarketSegment | str],
) -> BundleContext:
    """Return ``context`` with u99 thesis scoped to generated segments only."""

    successful_set = set(successful_segments)
    filtered_signals = tuple(
        signal for signal in context.daily_thesis_signals if signal.segment in successful_set
    )
    shared_keys = tuple(dict.fromkeys(signal.key for signal in context.daily_thesis_signals))
    decision = _decide_daily_thesis_for_segments(
        successful_segments,
        shared_keys=shared_keys,
        signals=filtered_signals,
    )
    return context.model_copy(
        update={
            "daily_thesis_signals": filtered_signals,
            "daily_thesis_decision": decision,
        }
    )


def compute_bundle_context(
    routed: Mapping[MarketSegment, Sequence[NormalizedItem]],
    *,
    now_kst: datetime,
    bundle_id: str | None = None,
) -> BundleContext:
    """Compute the same-run :class:`BundleContext` from routed items.

    ``routed`` is the segment → items mapping produced by u45's
    router. ``now_kst`` is the orchestrator's reference time (passed
    explicitly so replay tests are deterministic). ``bundle_id``
    defaults to ``"<YYYY-MM-DD>-bundle"`` when omitted.

    The returned context has every known segment populated; segments
    not present in ``routed`` get a ``pending`` summary so downstream
    consumers can rely on the three slots existing unconditionally.
    """
    target_date: date = now_kst.date()
    bundle_id = bundle_id or f"{target_date.isoformat()}-bundle"

    summaries: dict[str, MarketStateSummary] = {}
    for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO):
        items = routed.get(segment, ())
        close_state, headline = _select_close_state_for_segment(items)
        summaries[segment] = MarketStateSummary(
            segment=segment,
            target_date=target_date,
            tz=_SEGMENT_TZ[segment],
            close_state=close_state,
            headline_native_fact=headline,
        )

    shared = _detect_shared_macros(routed)
    shared_block = _render_shared_macro_block(shared)
    daily_thesis_signals = _daily_thesis_signals(routed, shared=shared)
    daily_thesis_decision = _decide_daily_thesis(
        routed,
        shared=shared,
        signals=daily_thesis_signals,
    )

    ctx = BundleContext(
        bundle_id=bundle_id,
        target_kst_date=target_date,
        segments=summaries,
        shared_macro_block=shared_block,
        cross_market_core_allowed=CROSS_MARKET_CORE_ALLOWED,
        daily_thesis_signals=daily_thesis_signals,
        daily_thesis_decision=daily_thesis_decision,
    )

    _logger.info(
        "bundle_context.computed",
        extra={
            "bundle_id": bundle_id,
            "target_date": target_date.isoformat(),
            "close_states": {seg: summ.close_state for seg, summ in summaries.items()},
            "shared_macro_count": len(shared),
        },
    )
    return ctx


__all__ = ["compute_bundle_context", "redecide_daily_thesis_for_successful_segments"]
