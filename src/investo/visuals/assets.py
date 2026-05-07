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
    WatchlistRelevanceCardInput,
    build_data_confidence_card,
    build_price_snapshot_card,
    build_watchlist_relevance_card,
)
from investo.visuals.paths import visual_asset_path, visual_asset_relative_path
from investo.visuals.render import render_card_svg

_MIN_SVG_BYTES: Final[int] = 500
_SUMMARY_PREFIXES: Final[dict[str, str]] = {
    "conclusion": "> **오늘의 결론**:",
    "driver": "> **핵심 동인**:",
    "caution": "> **주의할 점**:",
}
_CARD_LABELS: Final[dict[str, str]] = {
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
    """Validate that a generated SVG asset exists and is not blank."""
    if not path.exists():
        raise VisualAssetError(f"visual asset missing: {path}")
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


def _write_svg(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(content, encoding="utf-8")
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
