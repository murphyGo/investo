"""Reader-safe projection for internal quality diagnostics.

Internal quality labels are useful in logs, JSONL rows, and collapsed
diagnostics, but they should not leak into visible reader copy.
"""

from __future__ import annotations

import re
from typing import Final

PUBLIC_LOW_COVERAGE_TEXT: Final[str] = "이번 문서는 수집 근거가 제한적입니다."
PUBLIC_CORE_PRICE_MISSING_TEXT: Final[str] = (
    "핵심 가격 근거가 확인되지 않아 정확한 가격 서술은 줄였습니다."
)
PUBLIC_SOURCE_DETAIL_TEXT: Final[str] = "수집 상세는 진단 섹션에서 확인할 수 있습니다."
PUBLIC_WATCHPOINT_SOURCE_TEXT: Final[str] = "확인 가능한 출처가 있는 신호만 표시했습니다."
PUBLIC_WATCHPOINT_LIMITED_TEXT: Final[str] = (
    "오늘은 공개 근거가 충분한 관전 신호만 본문에 남겼습니다."
)
PUBLIC_SHARED_MACRO_LIMITED_TEXT: Final[str] = (
    "공통 거시 근거가 제한되어 확인 가능한 내용만 제공합니다."
)
PUBLIC_INDICATOR_LIMITED_TEXT: Final[str] = (
    "핵심 지표 근거가 제한되어 확인 가능한 내용만 제공합니다."
)
PUBLIC_CHANNEL_ANCHOR_LIMITED_TEXT: Final[str] = (
    "채널별 기준 근거가 제한되어 확인 가능한 내용만 제공합니다."
)
PUBLIC_DAILY_THESIS_LIMITED_TEXT: Final[str] = (
    "통합 관점의 근거가 제한되어 세그먼트별 확인 사항을 우선합니다."
)
PUBLIC_LOW_COVERAGE_INLINE_TEXT: Final[str] = "수집 근거가 제한적입니다"
PUBLIC_LOW_COVERAGE_LABEL: Final[str] = "근거 제한"

FORBIDDEN_PUBLIC_PHRASES: Final[tuple[str, ...]] = (
    "[데이터부족]",
    "데이터부족",
    "데이터 부족",
    "본문 사용 미집계",
    "확인 소스 미상",
    "source missing",
    "price missing",
    "fallback_ratio",
    "figures_presence",
)

FORBIDDEN_PUBLIC_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"본문 사용\s*(?:\d+|미집계)"),
    re.compile(r"실패\s*\d+"),
    re.compile(r"0건\s*\d+"),
    re.compile(r"fallback[_ ]?ratio", re.IGNORECASE),
    re.compile(r"figures[_ ]?presence", re.IGNORECASE),
)

_DATA_LIMITED_SENTENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:\[\s*데이터부족\s*\]|데이터\s*부족|데이터부족)(?:입니다|입니다\.|임|\.|。)?"
)
_DATA_LIMITED_NOUN_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:\[\s*데이터부족\s*\]|데이터\s*부족|데이터부족)(?=[은는이가을를으로도만과와])"
)
_BODY_USED_RE: Final[re.Pattern[str]] = re.compile(r"본문 사용\s*(?:\d+|미집계)")
_FAILED_COUNT_RE: Final[re.Pattern[str]] = re.compile(r"실패\s*\d+")
_ZERO_COUNT_RE: Final[re.Pattern[str]] = re.compile(r"0건\s*\d+")
_FALLBACK_RATIO_RE: Final[re.Pattern[str]] = re.compile(r"fallback[_ ]?ratio", re.IGNORECASE)
_FIGURES_PRESENCE_RE: Final[re.Pattern[str]] = re.compile(r"figures[_ ]?presence", re.IGNORECASE)


def project_public_quality_language(text: str) -> str:
    """Convert known diagnostic fragments to reader-facing Korean copy."""

    projected = _DATA_LIMITED_NOUN_RE.sub("수집 근거 제한", text)
    projected = _DATA_LIMITED_SENTENCE_RE.sub(PUBLIC_LOW_COVERAGE_INLINE_TEXT, projected)
    projected = projected.replace("본문 사용 미집계", PUBLIC_SOURCE_DETAIL_TEXT)
    projected = _BODY_USED_RE.sub(PUBLIC_SOURCE_DETAIL_TEXT, projected)
    projected = projected.replace("확인 소스 미상", PUBLIC_WATCHPOINT_SOURCE_TEXT)
    projected = projected.replace("source missing", PUBLIC_SOURCE_DETAIL_TEXT)
    projected = projected.replace("price missing", PUBLIC_CORE_PRICE_MISSING_TEXT)
    projected = _FAILED_COUNT_RE.sub(PUBLIC_SOURCE_DETAIL_TEXT, projected)
    projected = _ZERO_COUNT_RE.sub(PUBLIC_SOURCE_DETAIL_TEXT, projected)
    projected = _FALLBACK_RATIO_RE.sub("수집 제한 비율", projected)
    projected = _FIGURES_PRESENCE_RE.sub("수치 근거 표시율", projected)
    return " ".join(projected.split())


def first_forbidden_public_evidence(text: str) -> str | None:
    """Return the first raw diagnostic fragment visible in ``text``."""

    for phrase in FORBIDDEN_PUBLIC_PHRASES:
        if phrase in text:
            return phrase
    for pattern in FORBIDDEN_PUBLIC_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            return match.group(0)
    return None


__all__ = [
    "FORBIDDEN_PUBLIC_PATTERNS",
    "FORBIDDEN_PUBLIC_PHRASES",
    "PUBLIC_CHANNEL_ANCHOR_LIMITED_TEXT",
    "PUBLIC_CORE_PRICE_MISSING_TEXT",
    "PUBLIC_DAILY_THESIS_LIMITED_TEXT",
    "PUBLIC_INDICATOR_LIMITED_TEXT",
    "PUBLIC_LOW_COVERAGE_INLINE_TEXT",
    "PUBLIC_LOW_COVERAGE_LABEL",
    "PUBLIC_LOW_COVERAGE_TEXT",
    "PUBLIC_SHARED_MACRO_LIMITED_TEXT",
    "PUBLIC_SOURCE_DETAIL_TEXT",
    "PUBLIC_WATCHPOINT_LIMITED_TEXT",
    "PUBLIC_WATCHPOINT_SOURCE_TEXT",
    "first_forbidden_public_evidence",
    "project_public_quality_language",
]
