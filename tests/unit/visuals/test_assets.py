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
from investo.visuals.external_image import ExternalImageAsset
from investo.visuals.policy import ExternalAssetManifest
from investo.visuals.provenance import (
    build_generated_svg_provenance,
    manifest_path_for,
    write_manifest,
)
from tests.unit.visuals._image_bytes import VALID_JPEG_BYTES, VALID_PNG_BYTES

_TARGET = date(2026, 5, 7)
_PNG_BYTES = VALID_PNG_BYTES
_JPEG_BYTES = VALID_JPEG_BYTES


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


def test_prepare_segment_visual_assets_prefers_external_image_before_ai(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    external_manifest = ExternalAssetManifest(
        kind="explicit-license",
        source_url="https://images.example.com/photo.jpg",  # type: ignore[arg-type]
        license="CC-BY-4.0",
        attribution="Example Photo",
        author="Jane Doe",
        fetched_on=_TARGET,
        allowed_use="editorial",
    )
    external_asset = ExternalImageAsset(
        content=_JPEG_BYTES,
        extension=".jpg",
        manifest=external_manifest,
        source_item_title="NVDA rallies after earnings",
    )
    monkeypatch.setattr(
        "investo.visuals.assets.fetch_contextual_external_image",
        lambda *_args, **_kwargs: external_asset,
    )
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

    assert prepared.asset_paths[0].name == "external-context-image.jpg"
    assert prepared.asset_paths[1].name == "ai-market-hero.png"
    assert "![실제 시황 이미지](2026-05-07.assets/external-context-image.jpg)" in (
        prepared.briefing.rendered_markdown
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


def _write_valid_svg_with_manifest(asset_path: Path, *, content: str) -> None:
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_text(content, encoding="utf-8")
    manifest = build_generated_svg_provenance(
        asset_relative_path=asset_path.name,
        card_kind="data-confidence",
        generated_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        width=1200,
        height=630,
    )
    write_manifest(manifest, asset_path)


def test_validate_visual_asset_rejects_corrupt_svg(tmp_path: Path) -> None:
    asset_path = tmp_path / "corrupt.svg"
    # Long enough to pass the size check but XML-broken.
    payload = "<svg width='1200' height='630'><text>" + ("x" * 600)
    _write_valid_svg_with_manifest(asset_path, content=payload)

    with pytest.raises(VisualAssetError, match=r"not a complete SVG|no readable dimensions"):
        validate_visual_asset(asset_path)


def test_validate_visual_asset_rejects_dimension_out_of_range(tmp_path: Path) -> None:
    asset_path = tmp_path / "huge.svg"
    payload = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="3000" height="3000">'
        '<text x="0" y="0">title</text>' + ("<!-- pad " + "x" * 600 + " -->") + "</svg>"
    )
    _write_valid_svg_with_manifest(asset_path, content=payload)

    with pytest.raises(VisualAssetError, match="outside"):
        validate_visual_asset(asset_path)


def test_validate_visual_asset_rejects_missing_manifest(tmp_path: Path) -> None:
    asset_path = tmp_path / "data-confidence.svg"
    asset_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630">'
        '<text x="0" y="0">title</text>' + ("<!-- pad " + "x" * 600 + " -->") + "</svg>",
        encoding="utf-8",
    )
    # Intentionally do NOT write a manifest sidecar.
    with pytest.raises(VisualAssetError, match="manifest"):
        validate_visual_asset(asset_path)


def test_prepare_segment_visual_assets_writes_manifest_per_asset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
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

    for path in prepared.asset_paths:
        sidecar = manifest_path_for(path)
        assert sidecar.exists(), f"manifest missing for {path}"
        # JSON is sorted; ensure expected fields are present and dims are 1200x630.
        import json as _json

        payload = _json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["source_type"] == "generated_svg"
        assert payload["generator"] == "investo"
        assert payload["dimensions"] == [1200, 630]


def test_prepare_segment_visual_assets_layout_repositions_secondary_cards(
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
    md = prepared.briefing.rendered_markdown

    # Hero (data-confidence) lives in the first viewport, before the
    # reader-status block.
    assert md.index("data-confidence.svg") < md.index("> **데이터 상태**")
    # Price snapshot is repositioned next to the notable-tickers section.
    assert md.index("## ⑤ 주요 종목") < md.index("price-snapshot.svg")
    # Watchlist is repositioned next to the watch-points section.
    assert md.index("## ⑥ 오늘의 관전 포인트") < md.index("watchlist-relevance.svg")
    # Each visual link is followed by a sanitized provenance caption.
    assert "*이미지: 데이터 신뢰도" in md


def test_prepare_segment_visual_assets_caption_is_secret_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-veryrealsecretvaluedefinitelyok")
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

    md = prepared.briefing.rendered_markdown
    assert "sk-veryrealsecretvaluedefinitelyok" not in md
    # Manifest sidecars also must not leak.
    for path in prepared.asset_paths:
        sidecar_text = manifest_path_for(path).read_text(encoding="utf-8")
        assert "sk-veryrealsecretvaluedefinitelyok" not in sidecar_text


def test_validate_visual_asset_rejects_dimension_invalid_png(tmp_path: Path) -> None:
    # Tiny truncated PNG (signature only). Should fail dimension parse.
    asset_path = tmp_path / "broken.png"
    asset_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 200)
    # Even if we wrote a manifest, the PNG dim parse would fail.
    manifest = build_generated_svg_provenance(
        asset_relative_path=asset_path.name,
        card_kind="ai-market-hero",
        generated_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        width=1024,
        height=1024,
    )
    write_manifest(manifest, asset_path)

    # Manifest shape is fine for SVG only — but the asset has .png suffix and
    # the validator runs PNG-specific checks first.
    with pytest.raises(VisualAssetError, match=r"dimensions|PNG"):
        validate_visual_asset(asset_path)
