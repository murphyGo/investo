"""Tests for u19 SVG visual card rendering."""

from __future__ import annotations

from datetime import date

from investo.visuals.cards import (
    DataConfidenceCardInput,
    MarketSnapshotCardInput,
    PriceSnapshotCardInput,
    PriceSnapshotRow,
    WatchlistRelevanceCardInput,
    WatchlistRelevanceRow,
)
from investo.visuals.render import SVG_HEIGHT, SVG_WIDTH, render_card_svg, wrap_visual_text


def test_render_data_confidence_card_svg_has_fixed_dimensions_and_content() -> None:
    card = DataConfidenceCardInput(
        target_date=date(2026, 5, 7),
        segment="domestic-equity",
        coverage_status="partial",
        item_count=7,
        source_count=1,
        missing_categories=("가격",),
    )

    svg = render_card_svg(card)

    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert f'width="{SVG_WIDTH}"' in svg
    assert f'height="{SVG_HEIGHT}"' in svg
    assert "국내 증시 데이터 신뢰도" in svg
    assert "정보 제공용 시황 카드" in svg


def test_render_market_snapshot_card_cleans_markdown_and_wraps_long_text() -> None:
    card = MarketSnapshotCardInput(
        target_date=date(2026, 5, 7),
        segment="us-equity",
        coverage_status="normal",
        conclusion="**미국 증시는** [AI 주도주](https://example.com) 중심으로 반등했습니다.",
        main_driver="- NVDA와 MSFT 실적 기대가 위험 선호를 지지했습니다.",
        caution="1. 금리 경로와 장 마감 후 실적 발표를 함께 확인해야 합니다.",
    )

    svg = render_card_svg(card)

    assert "**" not in svg
    assert "https://example.com" not in svg
    assert "AI 주도주" in svg
    assert "미국 증시 시장 스냅샷" in svg


def test_render_price_snapshot_card_escapes_text() -> None:
    card = PriceSnapshotCardInput(
        target_date=date(2026, 5, 7),
        segment="crypto",
        rows=(
            PriceSnapshotRow(
                symbol="BTC",
                price="$76,105.00",
                percent_change="+0.33%",
                volume="$42.00B",
                high="$76,529.00",
                low="$75,103.00",
                source_name="coingecko-price",
            ),
            PriceSnapshotRow(
                symbol="ETH",
                price="$2,253.73",
                percent_change="-0.90%",
                source_name="coingecko-price",
            ),
        ),
    )

    svg = render_card_svg(card)

    assert "크립토 가격 스냅샷" in svg
    assert "BTC" in svg
    assert "$76,105.00" in svg


def test_render_watchlist_card_handles_no_match_and_rows() -> None:
    no_match = WatchlistRelevanceCardInput(
        target_date=date(2026, 5, 7),
        segment="us-equity",
        configured=True,
        total_matches=0,
    )
    matched = WatchlistRelevanceCardInput(
        target_date=date(2026, 5, 7),
        segment="us-equity",
        configured=True,
        total_matches=1,
        rows=(
            WatchlistRelevanceRow(
                term="NVDA",
                kind="ticker",
                source_name="yahoo-finance-news",
                title="NVDA rallies after earnings",
            ),
        ),
    )

    assert "직접 연결된 수집 항목 없음" in render_card_svg(no_match)
    assert "NVDA rallies after earnings" in render_card_svg(matched)


def test_wrap_visual_text_truncates_long_words_deterministically() -> None:
    lines = wrap_visual_text(
        "SuperLongTickerNameThatWouldOverflowAVisualCardWithoutTruncation 한국어 설명",
        max_chars=16,
        max_lines=2,
    )

    assert len(lines) == 2
    assert all(len(line) <= 16 for line in lines)
    assert lines[0].endswith("…")
