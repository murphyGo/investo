"""Prepare and validate generated briefing visual assets."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

from investo.briefing.segments import MarketSegment, SegmentCoverage
from investo.briefing.watchlist import WatchlistImpact
from investo.models import Briefing, NormalizedItem
from investo.publisher.paths import archive_path
from investo.visuals.cards import (
    DataConfidenceCardInput,
    MarketSnapshotCardInput,
    PriceSnapshotCardInput,
    PriceSnapshotRow,
    WatchlistRelevanceCardInput,
    build_data_confidence_card,
    build_price_snapshot_card,
    build_watchlist_relevance_card,
)
from investo.visuals.openai_image import generate_openai_visual, load_openai_visual_config
from investo.visuals.paths import visual_asset_path, visual_asset_relative_path
from investo.visuals.render import render_card_svg

_MIN_SVG_BYTES: Final[int] = 500
_MIN_PNG_BYTES: Final[int] = 100
_PNG_SIGNATURE: Final[bytes] = b"\x89PNG\r\n\x1a\n"
_SUMMARY_PREFIXES: Final[dict[str, str]] = {
    "conclusion": "> **오늘의 결론**:",
    "driver": "> **핵심 동인**:",
    "caution": "> **주의할 점**:",
}
_CARD_LABELS: Final[dict[str, str]] = {
    "ai-market-hero": "AI 시황 이미지",
    "data-confidence": "데이터 신뢰도",
    "market-snapshot": "시장 스냅샷",
    "price-snapshot": "가격 스냅샷",
    "watchlist-relevance": "관심 자산 관련성",
}
_RenderableCard = (
    DataConfidenceCardInput
    | MarketSnapshotCardInput
    | PriceSnapshotCardInput
    | WatchlistRelevanceCardInput
)


class VisualAssetError(ValueError):
    """Raised when visual assets cannot be prepared safely."""


@dataclass(frozen=True, slots=True)
class PreparedVisualAssets:
    """A briefing with visual links plus the generated asset paths."""

    briefing: Briefing
    asset_paths: tuple[Path, ...]


def prepare_segment_visual_assets(
    briefing: Briefing,
    *,
    target_date: date,
    segment: MarketSegment,
    items: tuple[NormalizedItem, ...],
    coverage: SegmentCoverage,
    watchlist_impact: WatchlistImpact,
) -> PreparedVisualAssets:
    """Generate SVG cards and insert relative image links into segment markdown."""
    markdown_path = archive_path(target_date, segment=segment)
    cards: list[_RenderableCard] = [
        build_data_confidence_card(target_date, coverage),
        _build_market_snapshot_card(
            briefing,
            target_date=target_date,
            segment=segment,
            coverage=coverage,
        ),
        build_watchlist_relevance_card(target_date, segment, watchlist_impact),
    ]
    price_card = build_price_snapshot_card(target_date, segment, items)
    if price_card is not None:
        cards.insert(2, price_card)

    asset_paths: list[Path] = []
    ai_asset_path = _prepare_openai_market_image(
        target_date=target_date,
        segment=segment,
        market_card=cards[1],
        price_card=price_card,
        coverage=coverage,
    )
    if ai_asset_path is not None:
        asset_paths.append(ai_asset_path)

    for card in cards:
        path = visual_asset_path(target_date, segment, card.kind)
        _write_svg(path, render_card_svg(card))
        validate_visual_asset(path)
        asset_paths.append(path)

    rendered_markdown = insert_visual_links(
        briefing.rendered_markdown,
        markdown_path=markdown_path,
        asset_paths=tuple(asset_paths),
    )
    return PreparedVisualAssets(
        briefing=briefing.model_copy(update={"rendered_markdown": rendered_markdown}),
        asset_paths=tuple(asset_paths),
    )


def insert_visual_links(
    markdown: str,
    *,
    markdown_path: Path,
    asset_paths: tuple[Path, ...],
) -> str:
    """Insert markdown image links before the first reader-status blockquote."""
    if not asset_paths:
        return markdown
    visual_block = "\n".join(
        f"![{_CARD_LABELS[path.stem]}]({visual_asset_relative_path(path, markdown_path)})"
        for path in asset_paths
    )
    if visual_block in markdown:
        return markdown

    lines = markdown.splitlines()
    insert_at = next(
        (
            index
            for index, line in enumerate(lines)
            if line.startswith("> **데이터 상태**")
            or line.startswith("> **내 관심 자산 영향**")
            or line.startswith("> **오늘의 결론**")
        ),
        1 if lines and lines[0].startswith("# ") else 0,
    )
    lines[insert_at:insert_at] = ["", visual_block, ""]
    return "\n".join(lines) + ("\n" if markdown.endswith("\n") else "")


def validate_visual_asset(path: Path) -> None:
    """Validate that a generated visual asset exists and is not blank."""
    if not path.exists():
        raise VisualAssetError(f"visual asset missing: {path}")
    if path.suffix == ".png":
        _validate_png_asset(path)
        return
    if path.suffix != ".svg":
        raise VisualAssetError(f"unsupported visual asset type: {path}")
    content = path.read_text(encoding="utf-8")
    if len(content.encode("utf-8")) < _MIN_SVG_BYTES:
        raise VisualAssetError(f"visual asset too small: {path}")
    if "<svg" not in content or "</svg>" not in content:
        raise VisualAssetError(f"visual asset is not a complete SVG: {path}")
    if "<text" not in content:
        raise VisualAssetError(f"visual asset has no text content: {path}")


def _build_market_snapshot_card(
    briefing: Briefing,
    *,
    target_date: date,
    segment: MarketSegment,
    coverage: SegmentCoverage,
) -> MarketSnapshotCardInput:
    extracted = _extract_summary_lines(briefing.rendered_markdown)
    return MarketSnapshotCardInput(
        target_date=target_date,
        segment=segment,
        conclusion=extracted["conclusion"] or briefing.market_summary,
        main_driver=extracted["driver"] or briefing.key_issues,
        caution=extracted["caution"] or briefing.today_watch,
        coverage_status=coverage.status,
    )


def _extract_summary_lines(markdown: str) -> dict[str, str]:
    result = {"conclusion": "", "driver": "", "caution": ""}
    for line in markdown.splitlines():
        for key, prefix in _SUMMARY_PREFIXES.items():
            if line.startswith(prefix):
                result[key] = line.removeprefix(prefix).strip()
    return result


def _prepare_openai_market_image(
    *,
    target_date: date,
    segment: MarketSegment,
    market_card: _RenderableCard,
    price_card: PriceSnapshotCardInput | None,
    coverage: SegmentCoverage,
) -> Path | None:
    if not isinstance(market_card, MarketSnapshotCardInput):
        return None
    image_bytes = generate_openai_visual(
        _build_openai_market_prompt(
            market_card=market_card,
            price_card=price_card,
            coverage=coverage,
        ),
        config=load_openai_visual_config(),
    )
    if image_bytes is None:
        return None
    if not _is_png_bytes(image_bytes):
        return None
    path = visual_asset_path(target_date, segment, "ai-market-hero", extension=".png")
    _write_png(path, image_bytes)
    validate_visual_asset(path)
    return path


def _build_openai_market_prompt(
    *,
    market_card: MarketSnapshotCardInput,
    price_card: PriceSnapshotCardInput | None,
    coverage: SegmentCoverage,
) -> str:
    price_lines = _format_price_rows(price_card.rows) if price_card is not None else "없음"
    missing = "없음"
    if coverage.missing_categories:
        missing = ", ".join(str(category) for category in coverage.missing_categories)
    return (
        "Create a polished Korean market briefing hero image as a clean editorial "
        "financial visual, suitable for a public archive page. Use abstract charts, "
        "ticker-table motifs, and market color accents. Do not use real company logos, "
        "news photographs, copyrighted article imagery, photorealistic people, or "
        "investment-advice wording. Keep any text short and derived only from the "
        "provided facts.\n\n"
        f"Date: {market_card.target_date.isoformat()}\n"
        f"Segment: {market_card.segment}\n"
        f"Conclusion: {market_card.conclusion}\n"
        f"Main driver: {market_card.main_driver}\n"
        f"Caution: {market_card.caution}\n"
        f"Coverage status: {market_card.coverage_status}\n"
        f"Items: {coverage.item_count}; sources: {coverage.source_count}; "
        f"missing categories: {missing}\n"
        f"Price rows: {price_lines}"
    )


def _format_price_rows(rows: tuple[PriceSnapshotRow, ...]) -> str:
    return "; ".join(
        f"{row.symbol} {row.price} {row.percent_change} from {row.source_name}" for row in rows[:6]
    )


def _validate_png_asset(path: Path) -> None:
    content = path.read_bytes()
    if not _is_png_bytes(content):
        raise VisualAssetError(f"visual asset is not a PNG: {path}")


def _is_png_bytes(content: bytes) -> bool:
    if len(content) < _MIN_PNG_BYTES:
        return False
    return content.startswith(_PNG_SIGNATURE)


def _write_svg(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
    except OSError as exc:
        raise VisualAssetError(f"failed to write visual asset: {path}") from exc


def _write_png(path: Path, content: bytes) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(content)
        os.replace(tmp_path, path)
    except OSError as exc:
        raise VisualAssetError(f"failed to write visual asset: {path}") from exc


__all__ = [
    "PreparedVisualAssets",
    "VisualAssetError",
    "insert_visual_links",
    "prepare_segment_visual_assets",
    "validate_visual_asset",
]
