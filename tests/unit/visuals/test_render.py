"""Tests for u19 SVG visual card rendering."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import get_args

import pytest

from investo.visuals.cards import (
    DataConfidenceCardInput,
    DataConfidenceSourceRow,
    MarketSnapshotCardInput,
    PriceSnapshotCardInput,
    PriceSnapshotRow,
    WatchlistRelevanceCardInput,
    WatchlistRelevanceRow,
)
from investo.visuals.render import (
    _CARD_PALETTE,
    SVG_HEIGHT,
    SVG_WIDTH,
    CardStyleVariant,
    _RenderableCard,
    build_card_style,
    render_card_svg,
    wrap_visual_text,
)

_STYLE_BASELINE = (
    (Path(__file__).parents[2] / "fixtures" / "u143_card_style_auto.txt")
    .read_text(encoding="utf-8")
    .removesuffix("\n")
)


def _sample_renderable_card(card_type: type[object]) -> _RenderableCard:
    if card_type is DataConfidenceCardInput:
        return DataConfidenceCardInput(
            target_date=date(2026, 5, 7),
            segment="domestic-equity",
            coverage_status="partial",
            item_count=3,
            source_count=2,
        )
    if card_type is MarketSnapshotCardInput:
        return MarketSnapshotCardInput(
            target_date=date(2026, 5, 7),
            segment="us-equity",
            coverage_status="normal",
            conclusion="결론",
            main_driver="동인",
            caution="주의",
        )
    if card_type is PriceSnapshotCardInput:
        return PriceSnapshotCardInput(
            target_date=date(2026, 5, 7),
            segment="crypto",
            rows=(
                PriceSnapshotRow(
                    symbol="BTC",
                    price="$76,105.00",
                    percent_change="+0.33%",
                    source_name="coingecko-price",
                ),
            ),
        )
    if card_type is WatchlistRelevanceCardInput:
        return WatchlistRelevanceCardInput(
            target_date=date(2026, 5, 7),
            segment="us-equity",
            configured=True,
            total_matches=0,
        )
    raise AssertionError(f"missing sample for renderable card type: {card_type}")


def test_build_card_style_auto_is_byte_identical_to_pre_u143_fixture() -> None:
    assert build_card_style("auto") == _STYLE_BASELINE


@pytest.mark.parametrize("variant", ("light", "dark", "auto", "site-scoped"))
def test_build_card_style_variant_matrix(variant: CardStyleVariant) -> None:
    style = build_card_style(variant)

    expected_definitions = 2 if variant in ("auto", "site-scoped") else 1
    for css_class, light_declarations, dark_declarations in _CARD_PALETTE:
        assert style.count(f".{css_class}{{") == expected_definitions
        if variant != "dark":
            assert style.count(f".{css_class}{{{light_declarations}}}") == 1
        if variant != "light":
            assert style.count(f".{css_class}{{{dark_declarations}}}") == 1

    if variant == "auto":
        assert "@media (prefers-color-scheme: dark)" in style
    else:
        assert "@media" not in style
    if variant == "site-scoped":
        assert '[data-md-color-scheme="slate"]' in style


@pytest.mark.parametrize("card_type", get_args(_RenderableCard))
def test_every_renderable_card_type_inherits_light_and_dark_variants(
    card_type: type[object],
) -> None:
    card = _sample_renderable_card(card_type)

    light = render_card_svg(card, variant="light")
    dark = render_card_svg(card, variant="dark")

    assert light != dark
    assert "@media" not in light
    assert "@media" not in dark
    assert "#f7f5ef" in light
    assert "#0f1417" in dark


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


def test_render_data_confidence_card_includes_reasons_and_source_rows() -> None:
    card = DataConfidenceCardInput(
        target_date=date(2026, 5, 7),
        segment="us-equity",
        coverage_status="partial",
        item_count=2,
        source_count=2,
        missing_categories=("뉴스",),
        reason_labels=("뉴스 카테고리 누락", "일부 소스 수집 실패"),
        source_rows=(
            DataConfidenceSourceRow(
                source_name="fred-macro",
                status="failed",
                detail="connection reset",
            ),
            DataConfidenceSourceRow(
                source_name="nasdaq-earnings-calendar",
                status="zero",
                detail="0건 반환",
            ),
            DataConfidenceSourceRow(
                source_name="정상 2개",
                status="ok",
                detail="yfinance-price, yahoo-finance-news",
            ),
        ),
    )

    svg = render_card_svg(card)

    assert "사유" in svg
    assert "뉴스 카테고리 누락" in svg
    assert "소스별 상태" in svg
    assert "fred-macro" in svg
    assert "connection reset" in svg
    assert "nasdaq-earnings-calendar" in svg
    assert "정상 2개" in svg


def test_render_data_confidence_card_truncates_to_four_source_rows() -> None:
    rows = tuple(
        DataConfidenceSourceRow(
            source_name=f"src-{i}",
            status="failed",
            detail=f"reason-{i}",
        )
        for i in range(6)
    )
    card = DataConfidenceCardInput(
        target_date=date(2026, 5, 7),
        segment="us-equity",
        coverage_status="partial",
        item_count=0,
        source_count=0,
        missing_categories=(),
        reason_labels=(),
        source_rows=rows[:6],
    )

    svg = render_card_svg(card)

    # First four labels render; fifth onwards do not.
    assert "src-0" in svg
    assert "src-3" in svg
    assert "src-4" not in svg
    assert "src-5" not in svg


def test_render_data_confidence_card_escapes_failure_reason() -> None:
    """Defense-in-depth — even though sanitize_source_error_message
    runs upstream, the renderer still HTML-escapes the detail field
    so a future regression that lets a ``<`` through cannot break the
    SVG document. Note: ``>`` (and other markdown tokens) are stripped
    by ``_clean_visual_text`` before escaping, so we only assert ``<``
    is escaped — that alone defeats element injection.
    """
    card = DataConfidenceCardInput(
        target_date=date(2026, 5, 7),
        segment="crypto",
        coverage_status="failed",
        item_count=0,
        source_count=0,
        missing_categories=(),
        reason_labels=(),
        source_rows=(
            DataConfidenceSourceRow(
                source_name="<script",
                status="failed",
                detail="boom <bad",
            ),
        ),
    )

    svg = render_card_svg(card)

    assert "<script" not in svg.replace("</text>", "").replace("</svg>", "")
    assert "&lt;script" in svg
    assert "<bad" not in svg.replace("</text>", "").replace("</svg>", "")
    assert "&lt;bad" in svg


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


def test_render_market_snapshot_card_projects_quality_language() -> None:
    card = MarketSnapshotCardInput(
        target_date=date(2026, 5, 7),
        segment="us-equity",
        coverage_status="partial",
        conclusion="데이터 부족입니다.",
        main_driver="본문 사용 미집계",
        caution="확인 소스 미상",
    )

    svg = render_card_svg(card)

    assert "데이터 부족" not in svg
    assert "본문 사용 미집계" not in svg
    assert "확인 소스 미상" not in svg
    assert "수집 근거가 제한적입니다" in svg
    assert "수집 상세는 진단 섹션에서 확인할 수 있습니다." in svg
    assert "확인 가능한 출처가 있는 신호만 표시했습니다." in svg


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
    # u66 — crypto card caption uses UTC 24h framing, not equity close.
    assert "UTC 24h 스냅샷" in svg
    assert "종가" not in svg


def test_u66_us_equity_price_card_keeps_plain_date_subtitle() -> None:
    card = PriceSnapshotCardInput(
        target_date=date(2026, 5, 7),
        segment="us-equity",
        rows=(
            PriceSnapshotRow(
                symbol="AAPL",
                price="$292.68",
                percent_change="-0.22%",
                source_name="yfinance-price",
            ),
        ),
    )
    svg = render_card_svg(card)
    assert "UTC 24h" not in svg


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


def test_render_watchlist_card_shows_default_bundle_badge() -> None:
    card = WatchlistRelevanceCardInput(
        target_date=date(2026, 5, 7),
        segment="us-equity",
        configured=True,
        is_default_bundle=True,
        total_matches=1,
        rows=(
            WatchlistRelevanceRow(
                term="NVDA",
                kind="ticker",
                source_name="yahoo-finance-news",
                title="NVIDIA rallies after earnings",
            ),
        ),
    )

    svg = render_card_svg(card)

    assert "기본 바스켓" in svg


def test_wrap_visual_text_truncates_long_words_deterministically() -> None:
    lines = wrap_visual_text(
        "SuperLongTickerNameThatWouldOverflowAVisualCardWithoutTruncation 한국어 설명",
        max_chars=16,
        max_lines=2,
    )

    assert len(lines) == 2
    assert all(len(line) <= 16 for line in lines)
    assert lines[0].endswith("…")


def test_render_card_uses_noto_sans_kr_font_with_arial_fallback() -> None:
    """u26 — every ``<text>`` declares Noto Sans KR with Arial fallback.

    Pins persona #2: the public site uses Noto Sans KR but the SVG
    cards previously hard-coded Arial only, breaking the visual
    rhythm. The font stack is escaped (``&quot;``) inside the
    attribute value so the SVG remains XML-well-formed.
    """
    card = MarketSnapshotCardInput(
        target_date=date(2026, 5, 7),
        segment="us-equity",
        coverage_status="normal",
        conclusion="결론",
        main_driver="동인",
        caution="주의",
    )

    svg = render_card_svg(card)

    assert "&quot;Noto Sans KR&quot;, Arial, sans-serif" in svg
    # Arial-only text declarations must not survive the migration.
    assert 'font-family="Arial, sans-serif"' not in svg


def test_render_card_defaults_to_forced_light_style() -> None:
    """u143 Step 1 — primary card output is a forced-light variant."""
    card = DataConfidenceCardInput(
        target_date=date(2026, 5, 7),
        segment="domestic-equity",
        coverage_status="partial",
        item_count=3,
        source_count=2,
        missing_categories=("뉴스",),
    )

    svg = render_card_svg(card)

    assert "<style>" in svg
    assert "@media" not in svg
    assert ".card-bg{fill:#f7f5ef;}" in svg
    assert "#0f1417" not in svg
    # Class hooks present on the actual elements (not just the style).
    assert 'class="card-bg"' in svg
    assert 'class="card-frame"' in svg
    assert 'class="card-text"' in svg
    assert 'class="card-disclaimer"' in svg
