"""Regression tests for shared segment market-clock metadata."""

from __future__ import annotations

from datetime import date

import pytest

from investo.briefing.pipeline import _render_timestamp_watermark
from investo.briefing.segments import MarketSegment
from investo.models.segments import SEGMENT_MARKET_TZ, SEGMENT_MARKET_TZ_LABEL
from investo.sources.aggregator import _window_for_adapter


@pytest.mark.parametrize(
    ("segment", "source_name"),
    [
        ("domestic-equity", "fsc-krx-index-price"),
        ("us-equity", "yfinance-price"),
        ("crypto", "coingecko-price"),
    ],
)
def test_briefing_watermark_matches_aggregator_window(
    segment: MarketSegment,
    source_name: str,
) -> None:
    target_date = date(2026, 5, 6)

    window = _window_for_adapter(target_date, source_name)
    watermark = _render_timestamp_watermark(target_date, segment)

    start = window.start_utc.strftime("%Y-%m-%dT%H:%MZ")
    end = window.end_utc.strftime("%Y-%m-%dT%H:%MZ")
    assert (
        watermark == f"**기준 시각**: 2026-05-06 {SEGMENT_MARKET_TZ_LABEL[segment]} · "
        f"[{start}, {end})"
    )


def test_segment_market_clock_catalog_is_complete() -> None:
    assert set(SEGMENT_MARKET_TZ) == {"domestic-equity", "us-equity", "crypto"}
    assert set(SEGMENT_MARKET_TZ_LABEL) == set(SEGMENT_MARKET_TZ)
