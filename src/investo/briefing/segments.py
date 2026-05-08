"""Market-segment routing for u7 segmented briefings."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final, Literal

from investo.models import Category, NormalizedItem, SourceOutcome

MarketSegment = Literal["domestic-equity", "us-equity", "crypto"]
CoverageStatus = Literal["normal", "partial", "insufficient"]
# u22 — closed set of reason codes describing *why* a segment landed in
# its current coverage status. Multiple codes can apply at once
# (e.g. price source failed AND news returned zero items).
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
]
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
}
_MISSING_CATEGORY_TO_REASON: Final[dict[Category, CoverageReasonCode]] = {
    "news": "MISSING_NEWS",
    "price": "MISSING_PRICE",
    "macro": "MISSING_MACRO",
    "calendar": "MISSING_CALENDAR",
    "earnings": "MISSING_EARNINGS",
}

DOMESTIC_EQUITY: Final[MarketSegment] = "domestic-equity"
US_EQUITY: Final[MarketSegment] = "us-equity"
CRYPTO: Final[MarketSegment] = "crypto"

SEGMENT_LABELS: Final[dict[MarketSegment, str]] = {
    DOMESTIC_EQUITY: "국내 증시",
    US_EQUITY: "미국 증시",
    CRYPTO: "크립토",
}

SEGMENT_THRESHOLDS: Final[dict[MarketSegment, int]] = {
    DOMESTIC_EQUITY: 3,
    US_EQUITY: 3,
    CRYPTO: 2,
}
SEGMENT_REQUIRED_CATEGORIES: Final[dict[MarketSegment, tuple[Category, ...]]] = {
    DOMESTIC_EQUITY: ("news", "price"),
    US_EQUITY: ("news", "price"),
    CRYPTO: ("news", "price"),
}
COVERAGE_STATUS_LABELS: Final[dict[CoverageStatus, str]] = {
    "normal": "정상",
    "partial": "부분",
    "insufficient": "부족",
}
CATEGORY_LABELS: Final[dict[Category, str]] = {
    "news": "뉴스",
    "price": "가격",
    "macro": "거시",
    "calendar": "일정",
    "earnings": "실적",
}

_DOMESTIC_SOURCES: Final[frozenset[str]] = frozenset({"fsc-krx-index-price", "yonhap-market"})
_US_SOURCES: Final[frozenset[str]] = frozenset(
    {
        "cnbc-top-news",
        "fomc-rss",
        "fred-macro",
        "nasdaq-earnings-calendar",
        "nasdaq-stocks-news",
        "sec-edgar-8k",
        "yahoo-finance-news",
        "yfinance-price",
    }
)
_CRYPTO_SOURCES: Final[frozenset[str]] = frozenset({"coingecko-price", "theblock-crypto"})
_SEGMENT_SOURCES: Final[dict[MarketSegment, frozenset[str]]] = {
    "domestic-equity": _DOMESTIC_SOURCES,
    "us-equity": _US_SOURCES,
    "crypto": _CRYPTO_SOURCES,
}

_KOREAN_EXCHANGE_TICKER = re.compile(r"\[(?:\d{6}|[A-Z]{3}\d{3})\]")
_US_TICKER = re.compile(r"\b(?:AAPL|AMZN|GOOGL|META|MSFT|NVDA|SPY|QQQ|TSLA|DIS|CPNG)\b")
_US_MARKET_TERMS: Final[tuple[str, ...]] = (
    "dow",
    "federal reserve",
    "fomc",
    "nasdaq",
    "nyse",
    "s&p 500",
    "sec ",
    "treasury",
    "vix",
)
_CRYPTO_TERMS: Final[tuple[str, ...]] = (
    "bitcoin",
    "btc",
    "crypto",
    "defi",
    "ethereum",
    "eth",
    "solana",
    "stablecoin",
    "token",
)
_CRYPTO_CROSS_MARKET_TERMS: Final[tuple[str, ...]] = (
    "liquidity",
    "rate",
    "risk asset",
    "treasury",
)


@dataclass(frozen=True, slots=True)
class SegmentedItems:
    """Items routed to each market segment."""

    domestic_equity: tuple[NormalizedItem, ...]
    us_equity: tuple[NormalizedItem, ...]
    crypto: tuple[NormalizedItem, ...]

    def for_segment(self, segment: MarketSegment) -> tuple[NormalizedItem, ...]:
        if segment == DOMESTIC_EQUITY:
            return self.domestic_equity
        if segment == US_EQUITY:
            return self.us_equity
        return self.crypto

    def is_data_limited(self, segment: MarketSegment) -> bool:
        """Return True when the routed segment is below the ``normal`` bar.

        Structural-only judgement — decided purely from the routed item
        count and missing required categories. Source-level outcomes
        (``SOURCE_FAILED`` / ``SOURCE_ZERO``) surface in
        :attr:`SegmentCoverage.reason_codes` for transparency but do
        **not** influence this routing decision; a segment with all
        required items can still carry a ``SOURCE_FAILED`` reason and
        will still report ``is_data_limited == False``.
        """
        return self.coverage_for_segment(segment).status != "normal"

    def coverage_for_segment(
        self,
        segment: MarketSegment,
        *,
        source_outcomes: Sequence[SourceOutcome] = (),
    ) -> SegmentCoverage:
        return build_segment_coverage(
            segment,
            self.for_segment(segment),
            source_outcomes=segment_source_outcomes(segment, source_outcomes),
        )


@dataclass(frozen=True, slots=True)
class SegmentCoverage:
    """Reader-facing coverage summary for a routed market segment.

    The u22 fields ``reason_codes`` and ``source_outcomes`` are populated
    when the orchestrator threads a :class:`investo.models.SourceCollectionReport`
    through to the briefing layer. When ``source_outcomes`` is empty
    (e.g. legacy unsegmented runs that still call
    :func:`build_segment_coverage` with items only) the coverage still
    reports the structural reasons (zero items, below threshold,
    missing categories) inferred from the routed item set.
    """

    segment: MarketSegment
    status: CoverageStatus
    item_count: int
    source_count: int
    categories: tuple[Category, ...]
    missing_categories: tuple[Category, ...]
    reason_codes: tuple[CoverageReasonCode, ...] = field(default_factory=tuple)
    source_outcomes: tuple[SourceOutcome, ...] = field(default_factory=tuple)

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


def segment_items(items: Sequence[NormalizedItem]) -> SegmentedItems:
    """Route source items into deterministic market segments."""
    domestic: list[NormalizedItem] = []
    us: list[NormalizedItem] = []
    crypto: list[NormalizedItem] = []

    for item in items:
        text = _item_text(item)
        if _is_domestic_equity(item, text):
            domestic.append(item)
        if _is_us_equity(item, text):
            us.append(item)
        if _is_crypto(item, text):
            crypto.append(item)

    return SegmentedItems(
        domestic_equity=tuple(domestic),
        us_equity=tuple(us),
        crypto=tuple(crypto),
    )


def build_segment_coverage(
    segment: MarketSegment,
    items: Sequence[NormalizedItem],
    *,
    source_outcomes: Sequence[SourceOutcome] = (),
) -> SegmentCoverage:
    """Build coverage for a routed segment.

    ``source_outcomes`` is the optional u22 hook: when supplied, it must
    already be filtered down to outcomes relevant to ``segment`` (use
    :func:`segment_source_outcomes` to derive the subset from a full
    :class:`investo.models.SourceCollectionReport`). Reason codes are
    derived from both the routed item set (structural deficiencies) and
    the per-source outcomes (operational deficiencies); the resulting
    ``reason_codes`` tuple is deterministic and order-stable.

    ``status`` vs ``reason_codes`` relationship:

    * ``status`` is a *hard* judgement based solely on the routed item
      set (``normal`` / ``partial`` / ``insufficient``): zero items →
      ``insufficient``; below threshold or missing required categories
      → ``partial``; otherwise → ``normal``.
    * ``reason_codes`` is an *additional transparency signal*. It can
      carry ``SOURCE_FAILED`` / ``SOURCE_ZERO`` even when the routed
      items are sufficient and ``status == "normal"``. In other words a
      ``normal`` segment may still display "일부 소스 실패" alongside —
      this is intended behaviour, not an inconsistency.
    """
    categories = tuple(sorted({item.category for item in items}))
    source_count = len({item.source_name for item in items})
    required_categories = SEGMENT_REQUIRED_CATEGORIES[segment]
    missing_categories = tuple(
        category for category in required_categories if category not in categories
    )
    if not items:
        status: CoverageStatus = "insufficient"
    elif len(items) < SEGMENT_THRESHOLDS[segment] or missing_categories:
        status = "partial"
    else:
        status = "normal"
    return SegmentCoverage(
        segment=segment,
        status=status,
        item_count=len(items),
        source_count=source_count,
        categories=categories,
        missing_categories=missing_categories,
        reason_codes=_derive_reason_codes(
            segment=segment,
            items=items,
            missing_categories=missing_categories,
            source_outcomes=source_outcomes,
        ),
        source_outcomes=tuple(source_outcomes),
    )


def segment_source_outcomes(
    segment: MarketSegment,
    outcomes: Sequence[SourceOutcome],
) -> tuple[SourceOutcome, ...]:
    """Filter aggregator outcomes to those mapped to ``segment``.

    The mapping mirrors the segment-routing source allow-lists already
    used by :func:`segment_items`. Adapters not assigned to any segment
    (none today) are intentionally dropped — the segment-level coverage
    surface only annotates sources whose verdicts are reader-relevant
    for *that* segment.
    """
    allow_list = _SEGMENT_SOURCES[segment]
    return tuple(outcome for outcome in outcomes if outcome.source_name in allow_list)


def _derive_reason_codes(
    *,
    segment: MarketSegment,
    items: Sequence[NormalizedItem],
    missing_categories: tuple[Category, ...],
    source_outcomes: Sequence[SourceOutcome],
) -> tuple[CoverageReasonCode, ...]:
    codes: list[CoverageReasonCode] = []
    if not items:
        codes.append("ZERO_ITEMS")
    elif len(items) < SEGMENT_THRESHOLDS[segment]:
        codes.append("BELOW_THRESHOLD")
    for category in missing_categories:
        codes.append(_MISSING_CATEGORY_TO_REASON[category])
    if any(outcome.status == "failed" for outcome in source_outcomes):
        codes.append("SOURCE_FAILED")
    if any(outcome.status == "zero" for outcome in source_outcomes):
        codes.append("SOURCE_ZERO")
    return tuple(codes)


def _item_text(item: NormalizedItem) -> str:
    return f"{item.source_name} {item.title} {item.summary or ''}".lower()


def _is_domestic_equity(item: NormalizedItem, text: str) -> bool:
    return item.source_name in _DOMESTIC_SOURCES or bool(
        _KOREAN_EXCHANGE_TICKER.search(f"{item.title} {item.summary or ''}")
    )


def _is_us_equity(item: NormalizedItem, text: str) -> bool:
    return (
        item.source_name in _US_SOURCES
        or bool(_US_TICKER.search(f"{item.title} {item.summary or ''}"))
        or any(term in text for term in _US_MARKET_TERMS)
    )


def _is_crypto(item: NormalizedItem, text: str) -> bool:
    if item.source_name in _CRYPTO_SOURCES:
        return True
    if any(term in text for term in _CRYPTO_TERMS):
        return True
    return any(term in text for term in _CRYPTO_CROSS_MARKET_TERMS) and (
        "fed" in text or "fomc" in text or "federal reserve" in text
    )


__all__ = [
    "CATEGORY_LABELS",
    "COVERAGE_REASON_LABELS",
    "COVERAGE_STATUS_LABELS",
    "CRYPTO",
    "DOMESTIC_EQUITY",
    "SEGMENT_LABELS",
    "SEGMENT_REQUIRED_CATEGORIES",
    "SEGMENT_THRESHOLDS",
    "US_EQUITY",
    "CoverageReasonCode",
    "CoverageStatus",
    "MarketSegment",
    "SegmentCoverage",
    "SegmentedItems",
    "build_segment_coverage",
    "segment_items",
    "segment_source_outcomes",
]
