"""Shared segment identifiers and market-clock metadata."""

from __future__ import annotations

from typing import Final, Literal
from zoneinfo import ZoneInfo

MarketSegment = Literal["domestic-equity", "us-equity", "crypto"]

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

__all__ = [
    "SEGMENT_MARKET_TZ",
    "SEGMENT_MARKET_TZ_LABEL",
    "MarketSegment",
]
