"""Tests for u19 visual asset preparation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.segments import build_segment_coverage
from investo.briefing.watchlist import WatchlistConfig, match_watchlist_items
from investo.models import Briefing, NormalizedItem
from investo.publisher.paths import archive_path
from investo.visuals.assets import (
    VisualAssetError,
    insert_visual_links,
    prepare_segment_visual_assets,
    validate_visual_asset,
)

_TARGET = date(2026, 5, 7)
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + (b"\0" * 128)


def _briefing() -> Briefing:
    rendered = (
        "# 2026-05-07 미국 증시 시황\n\n"
        "**세그먼트**: [국내](x) | [미국](y) | [크립토](z)\n\n"
        "> **데이터 상태**: 정상 — 수집 3건 / 소스 2개 / 누락: 없음\n"
        "> **오늘의 결론**: 미국 증시는 AI 주도주 중심으로 반등했습니다.\n"
        "> **핵심 동인**: NVDA 실적 기대가 위험 선호를 지지했습니다.\n"
        "> **주의할 점**: 금리 경로와 실적 발표를 함께 확인해야 합니다.\n\n"
        "## ① 요약\n미국 증시는 AI 주도주 중심으로 반등했습니다.\n\n"
        "## ② 전일 핵심 이슈\nNVDA 실적 기대가 위험 선호를 지지했습니다.\n\n"
        "## ③ 섹터/수급 동향\n섹터\n\n"
        "## ④ 지표·이벤트\n지표\n\n"
        "## ⑤ 주요 종목\n종목\n\n"
        "## ⑥ 오늘의 관전 포인트\n금리 경로와 실적 발표를 함께 확인해야 합니다.\n\n"
        f"{DISCLAIMER}"
    )
    return Briefing(
        target_date=_TARGET,
        market_summary="미국 증시는 AI 주도주 중심으로 반등했습니다.",
        key_issues="NVDA 실적 기대가 위험 선호를 지지했습니다.",
        sector_flow="섹터",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="금리 경로와 실적 발표를 함께 확인해야 합니다.",
        disclaimer=DISCLAIMER,
        rendered_markdown=rendered,
    )


def _item(
    source_name: str,
    category: str,
    title: str,
    *,
    raw_metadata: dict[str, str] | None = None,
) -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name,
        category=category,  # type: ignore[arg-type]
        title=title,
        url="https://example.com/item",
        published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        raw_metadata=raw_metadata or {},
    )


def test_insert_visual_links_places_images_before_reader_status_block() -> None:
    markdown_path = Path("archive/us-equity/2026/05/2026-05-07.md")
    asset_paths = (
        Path("archive/us-equity/2026/05/2026-05-07.assets/data-confidence.svg"),
        Path("archive/us-equity/2026/05/2026-05-07.assets/market-snapshot.svg"),
    )

    result = insert_visual_links(
        _briefing().rendered_markdown,
        markdown_path=markdown_path,
        asset_paths=asset_paths,
    )

    assert "![데이터 신뢰도](2026-05-07.assets/data-confidence.svg)" in result
    assert result.index("![데이터 신뢰도]") < result.index("> **데이터 상태**")
    assert (
        insert_visual_links(result, markdown_path=markdown_path, asset_paths=asset_paths) == result
    )


def test_prepare_segment_visual_assets_writes_assets_and_updates_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    items = (
        _item(
            "yfinance-price",
            "price",
            "NVDA 1,024.00 (+2.00%)",
            raw_metadata={
                "ticker": "NVDA",
                "close": "1024",
                "prev_close": "1000",
                "high": "1030",
                "low": "990",
                "volume": "30000000",
            },
        ),
        _item("yahoo-finance-news", "news", "NVDA rallies after earnings"),
    )
    coverage = build_segment_coverage("us-equity", items)
    impact = match_watchlist_items(items, WatchlistConfig(tickers=("NVDA",)))

    prepared = prepare_segment_visual_assets(
        _briefing(),
        target_date=_TARGET,
        segment="us-equity",
        items=items,
        coverage=coverage,
        watchlist_impact=impact,
    )

    assert len(prepared.asset_paths) == 4
    for path in prepared.asset_paths:
        assert path.exists()
        validate_visual_asset(path)
    assert "2026-05-07.assets/data-confidence.svg" in prepared.briefing.rendered_markdown
    assert "2026-05-07.assets/price-snapshot.svg" in prepared.briefing.rendered_markdown
    assert archive_path(_TARGET, segment="us-equity").parent == (
        tmp_path / "archive/us-equity/2026/05"
    )


def test_prepare_segment_visual_assets_can_prepend_openai_png(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    monkeypatch.setattr(
        "investo.visuals.assets.generate_openai_visual",
        lambda *_args, **_kwargs: _PNG_BYTES,
    )
    items = (_item("yahoo-finance-news", "news", "NVDA rallies after earnings"),)
    coverage = build_segment_coverage("us-equity", items)
    impact = match_watchlist_items(items, WatchlistConfig(tickers=("NVDA",)))

    prepared = prepare_segment_visual_assets(
        _briefing(),
        target_date=_TARGET,
        segment="us-equity",
        items=items,
        coverage=coverage,
        watchlist_impact=impact,
    )

    assert prepared.asset_paths[0].name == "ai-market-hero.png"
    assert prepared.asset_paths[0].read_bytes() == _PNG_BYTES
    assert "![AI 시황 이미지](2026-05-07.assets/ai-market-hero.png)" in (
        prepared.briefing.rendered_markdown
    )
    assert prepared.briefing.rendered_markdown.index("ai-market-hero.png") < (
        prepared.briefing.rendered_markdown.index("data-confidence.svg")
    )


def test_prepare_segment_visual_assets_falls_back_when_openai_png_is_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    monkeypatch.setattr(
        "investo.visuals.assets.generate_openai_visual",
        lambda *_args, **_kwargs: b"not-png",
    )
    items = (_item("yahoo-finance-news", "news", "NVDA rallies after earnings"),)
    coverage = build_segment_coverage("us-equity", items)
    impact = match_watchlist_items(items, WatchlistConfig(tickers=("NVDA",)))

    prepared = prepare_segment_visual_assets(
        _briefing(),
        target_date=_TARGET,
        segment="us-equity",
        items=items,
        coverage=coverage,
        watchlist_impact=impact,
    )

    assert all(path.suffix == ".svg" for path in prepared.asset_paths)
    assert "ai-market-hero.png" not in prepared.briefing.rendered_markdown


def test_validate_visual_asset_rejects_missing_or_blank_svg(tmp_path: Path) -> None:
    missing = tmp_path / "missing.svg"
    with pytest.raises(VisualAssetError, match="missing"):
        validate_visual_asset(missing)

    blank = tmp_path / "blank.svg"
    blank.write_text("<svg></svg>", encoding="utf-8")
    with pytest.raises(VisualAssetError, match="too small"):
        validate_visual_asset(blank)
