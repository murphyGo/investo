"""Shared market-segment contracts and reader-facing coverage DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal
from zoneinfo import ZoneInfo

from investo.models.coverage import SourceOutcome
from investo.models.items import Category

MarketSegment = Literal["domestic-equity", "us-equity", "crypto"]
DOMESTIC_EQUITY: Final[MarketSegment] = "domestic-equity"
US_EQUITY: Final[MarketSegment] = "us-equity"
CRYPTO: Final[MarketSegment] = "crypto"

CoverageStatus = Literal["normal", "partial", "limited", "failed"]
CoverageReasonCode = Literal[
    "ZERO_ITEMS",
    "BELOW_THRESHOLD",
    "MISSING_NEWS",
    "MISSING_PRICE",
    "MISSING_MACRO",
    "MISSING_CALENDAR",
    "MISSING_EARNINGS",
    "SOURCE_FAILED",
    "SOURCE_ZERO",
    "DOMESTIC_DISCLOSURE_QUIET",
    "LOOKAHEAD_DATA_MISSING",
    "CORE_FAILED",
    "CORE_ZERO",
    "CORE_STALE",
    "ALL_FAILED",
    "MACRO_ACTUAL_MISSING",
    "MACRO_ACTUAL_ZERO",
    "MACRO_ACTUAL_FAILED",
    "MACRO_ACTUAL_STALE",
    "MACRO_REQUIRED_OMITTED",
    "MACRO_FORECAST_UNVERIFIED",
]

SEGMENT_LABELS: Final[dict[MarketSegment, str]] = {
    DOMESTIC_EQUITY: "국내 증시",
    US_EQUITY: "미국 증시",
    CRYPTO: "크립토",
}
COVERAGE_REASON_LABELS: Final[dict[CoverageReasonCode, str]] = {
    "ZERO_ITEMS": "수집 항목 0건",
    "BELOW_THRESHOLD": "최소 수집 기준 미달",
    "MISSING_NEWS": "뉴스 카테고리 누락",
    "MISSING_PRICE": "가격 카테고리 누락",
    "MISSING_MACRO": "거시 카테고리 누락",
    "MISSING_CALENDAR": "일정 카테고리 누락",
    "MISSING_EARNINGS": "실적 카테고리 누락",
    "SOURCE_FAILED": "일부 소스 수집 실패",
    "SOURCE_ZERO": "일부 소스 0건 반환",
    "DOMESTIC_DISCLOSURE_QUIET": "DART 주요 공시 0건",
    "LOOKAHEAD_DATA_MISSING": "예정 일정 데이터 미확보",
    "CORE_FAILED": "핵심 가격 소스 실패",
    "CORE_ZERO": "핵심 가격 소스 0건",
    "CORE_STALE": "핵심 가격 소스 데이터가 stale",
    "ALL_FAILED": "모든 소스 실패",
    "MACRO_ACTUAL_MISSING": "거시 실제치 미확보",
    "MACRO_ACTUAL_ZERO": "거시 실제치 소스 0건",
    "MACRO_ACTUAL_FAILED": "거시 실제치 소스 실패",
    "MACRO_ACTUAL_STALE": "거시 실제치 stale",
    "MACRO_REQUIRED_OMITTED": "필수 거시 지표 본문 누락",
    "MACRO_FORECAST_UNVERIFIED": "거시 예상치 미검증",
}
COVERAGE_STATUS_LABELS: Final[dict[CoverageStatus, str]] = {
    "normal": "정상",
    "partial": "부분",
    "limited": "제한",
    "failed": "실패",
}
SEVERITY_READER_EXPLANATIONS: Final[dict[CoverageStatus, str]] = {
    "normal": "정상 — 핵심 소스 수집 완료, 본문 결론 신뢰도 양호",
    "partial": "부분 — 일부 카테고리 미수집, 본문 일부 결론 보강 필요",
    "limited": "제한 — 핵심 가격 소스 0건/실패/stale, 본문 결론 신뢰도 낮음",
    "failed": "실패 — 핵심 소스 전부 실패 또는 수집 항목 0건",
}
CATEGORY_LABELS: Final[dict[Category, str]] = {
    "news": "뉴스",
    "price": "가격",
    "macro": "거시",
    "calendar": "일정",
    "earnings": "실적",
}

SEGMENT_MARKET_TZ: Final[dict[MarketSegment, ZoneInfo]] = {
    "domestic-equity": ZoneInfo("Asia/Seoul"),
    "us-equity": ZoneInfo("America/New_York"),
    "crypto": ZoneInfo("UTC"),
}
SEGMENT_MARKET_TZ_LABEL: Final[dict[MarketSegment, str]] = {
    "domestic-equity": "KST",
    "us-equity": "NY",
    "crypto": "UTC",
}


@dataclass(frozen=True, slots=True)
class SegmentCoverage:
    """Reader-facing coverage summary for a routed market segment."""

    segment: MarketSegment
    status: CoverageStatus
    item_count: int
    source_count: int
    categories: tuple[Category, ...]
    missing_categories: tuple[Category, ...]
    reason_codes: tuple[CoverageReasonCode, ...] = field(default_factory=tuple)
    source_outcomes: tuple[SourceOutcome, ...] = field(default_factory=tuple)
    targeted_count: int = 0
    succeeded_count: int = 0
    zero_count: int = 0
    failed_count: int = 0
    body_used_count: int = 0

    @property
    def status_label(self) -> str:
        return COVERAGE_STATUS_LABELS[self.status]

    @property
    def missing_category_label(self) -> str:
        if not self.missing_categories:
            return "없음"
        return ", ".join(CATEGORY_LABELS[category] for category in self.missing_categories)

    @property
    def reason_labels(self) -> tuple[str, ...]:
        """Human-readable Korean labels for each present reason code."""
        return tuple(COVERAGE_REASON_LABELS[code] for code in self.reason_codes)

    @property
    def failed_source_outcomes(self) -> tuple[SourceOutcome, ...]:
        return tuple(outcome for outcome in self.source_outcomes if outcome.status == "failed")

    @property
    def zero_source_outcomes(self) -> tuple[SourceOutcome, ...]:
        return tuple(outcome for outcome in self.source_outcomes if outcome.status == "zero")

    @property
    def ok_source_outcomes(self) -> tuple[SourceOutcome, ...]:
        return tuple(outcome for outcome in self.source_outcomes if outcome.status == "ok")

    @property
    def tier_mix_label(self) -> str:
        if not self.ok_source_outcomes:
            return ""
        counts: dict[str, int] = {label: 0 for label in ("S", "A", "B", "C")}
        for outcome in self.ok_source_outcomes:
            counts[outcome.tier] += 1
        parts = [f"{label}={count}" for label, count in counts.items() if count]
        return " / ".join(parts)


__all__ = [
    "CATEGORY_LABELS",
    "COVERAGE_REASON_LABELS",
    "COVERAGE_STATUS_LABELS",
    "CRYPTO",
    "DOMESTIC_EQUITY",
    "SEGMENT_LABELS",
    "SEGMENT_MARKET_TZ",
    "SEGMENT_MARKET_TZ_LABEL",
    "SEVERITY_READER_EXPLANATIONS",
    "US_EQUITY",
    "CoverageReasonCode",
    "CoverageStatus",
    "MarketSegment",
    "SegmentCoverage",
]
