"""Market-segment routing for u7 segmented briefings."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from investo.models import Category, NormalizedItem

MarketSegment = Literal["domestic-equity", "us-equity", "crypto"]
CoverageStatus = Literal["normal", "partial", "insufficient"]

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

_DOMESTIC_SOURCES: Final[frozenset[str]] = frozenset({"yonhap-market"})
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
        return self.coverage_for_segment(segment).status != "normal"

    def coverage_for_segment(self, segment: MarketSegment) -> SegmentCoverage:
        return build_segment_coverage(segment, self.for_segment(segment))


@dataclass(frozen=True, slots=True)
class SegmentCoverage:
    """Reader-facing coverage summary for a routed market segment."""

    segment: MarketSegment
    status: CoverageStatus
    item_count: int
    source_count: int
    categories: tuple[Category, ...]
    missing_categories: tuple[Category, ...]

    @property
    def status_label(self) -> str:
        return COVERAGE_STATUS_LABELS[self.status]

    @property
    def missing_category_label(self) -> str:
        if not self.missing_categories:
            return "없음"
        return ", ".join(CATEGORY_LABELS[category] for category in self.missing_categories)


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
) -> SegmentCoverage:
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
    )


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
    "COVERAGE_STATUS_LABELS",
    "CRYPTO",
    "DOMESTIC_EQUITY",
    "SEGMENT_LABELS",
    "SEGMENT_REQUIRED_CATEGORIES",
    "SEGMENT_THRESHOLDS",
    "US_EQUITY",
    "CoverageStatus",
    "MarketSegment",
    "SegmentCoverage",
    "SegmentedItems",
    "build_segment_coverage",
    "segment_items",
]
