"""Prepare and validate generated briefing visual assets."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final, Literal

from defusedxml.ElementTree import ParseError, fromstring

from investo.briefing.extract import (
    extract_caution,
    extract_conclusion,
    extract_key_drivers,
)
from investo.briefing.segments import MarketSegment, SegmentCoverage
from investo.briefing.summary_quality import CONCLUSION_PREFIX
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
from investo.visuals.external_image import fetch_contextual_external_image
from investo.visuals.openai_image import (
    generate_openai_visual,
    load_openai_visual_config,
)
from investo.visuals.paths import visual_asset_path, visual_asset_relative_path
from investo.visuals.provenance import (
    VisualProvenanceManifest,
    build_ai_generated_provenance,
    build_external_provenance,
    build_generated_svg_provenance,
    manifest_path_for,
    provenance_caption,
    read_manifest,
    write_manifest,
)
from investo.visuals.render import SVG_HEIGHT, SVG_WIDTH, render_card_svg

_MIN_SVG_BYTES: Final[int] = 500
_MIN_PNG_BYTES: Final[int] = 100
_PNG_SIGNATURE: Final[bytes] = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE: Final[bytes] = b"\xff\xd8\xff"
_MIN_DIMENSION: Final[int] = 100
_MAX_DIMENSION: Final[int] = 2000
_PNG_IHDR_OFFSET: Final[int] = 8
_PNG_IHDR_LENGTH: Final[int] = 25
_DIMENSION_NUMBER_RE: Final[re.Pattern[str]] = re.compile(r"\d+")
_CARD_LABELS: Final[dict[str, str]] = {
    "ai-market-hero": "AI 시황 이미지",
    "data-confidence": "데이터 신뢰도",
    "external-context-image": "실제 시황 이미지",
    "market-snapshot": "시장 스냅샷",
    "price-snapshot": "가격 스냅샷",
    "watchlist-relevance": "관심 자산 관련성",
}
_HERO_CARD_KINDS: Final[frozenset[str]] = frozenset(
    {"ai-market-hero", "external-context-image", "data-confidence"}
)
# Layout policy (u24): only one hero visual lands above the fold; every
# other card moves down to the H2 section that names it. The hero
# preference order is external-context > ai-market-hero > data-confidence;
# whichever is present first wins. ``data-confidence`` is the guaranteed
# fallback because every segment renders it.
_HERO_PRIORITY: Final[tuple[str, ...]] = (
    "external-context-image",
    "ai-market-hero",
    "data-confidence",
)
_SECTION_ANCHORS: Final[dict[str, tuple[str, ...]]] = {
    # Market-snapshot card belongs near the segment summary section.
    "market-snapshot": ("## ① 요약",),
    # Price-snapshot belongs near the notable-tickers section.
    "price-snapshot": ("## ⑤ 주요 종목",),
    # Watchlist relevance belongs near the watch-points section.
    "watchlist-relevance": ("## ⑥ 오늘의 관전 포인트",),
    # If the hero is data-confidence and no PNG/external is available,
    # data-confidence is the hero. When data-confidence is *not* the hero
    # (e.g. AI hero present), it is repositioned next to the summary.
    "data-confidence": ("## ① 요약",),
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
    """Generate SVG cards, write provenance manifests, and lay out markdown."""
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
    external_asset_path = _prepare_external_context_image(
        target_date=target_date,
        segment=segment,
        items=items,
    )
    if external_asset_path is not None:
        asset_paths.append(external_asset_path)

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
        _write_generated_svg_manifest(path, card_kind=card.kind)
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
    """Lay out one hero visual above the fold and reposition the rest (u24).

    The previous implementation grouped every visual card directly
    under the H1, which produced a crowded first viewport. u24 picks
    one hero card (priority: external context > AI hero >
    data-confidence) and inserts it before the reader-status block;
    every other card is inserted just below the H2 section it relates
    to (``## ① 요약`` for market-snapshot, ``## ⑤ 주요 종목`` for
    price-snapshot, ``## ⑥ 오늘의 관전 포인트`` for watchlist).
    Each visual is followed by a sanitized provenance caption so
    readers can see attribution without a click. Idempotent: a
    second pass that already finds every link in place returns the
    input unchanged.
    """
    if not asset_paths:
        return markdown
    blocks = tuple(_visual_block(path, markdown_path=markdown_path) for path in asset_paths)
    # Idempotency: if every block is already present, do nothing.
    if all(block in markdown for block in blocks):
        return markdown

    hero_index = _select_hero_index(asset_paths)
    lines = markdown.splitlines()
    # Track inserts in source-line coordinates (we mutate as we go).
    # Insert non-hero cards *first* (later positions first), so the
    # earlier hero insert does not shift their resolved positions.
    non_hero_inserts: list[tuple[int, str]] = []
    for index, path in enumerate(asset_paths):
        if index == hero_index:
            continue
        block = blocks[index]
        if block in markdown:
            continue
        anchor_line = _find_section_anchor(lines, path.stem)
        if anchor_line is None:
            # No matching H2 — fall back to immediately after the H1.
            anchor_line = 0
        non_hero_inserts.append((anchor_line, block))
    # Apply non-hero inserts in descending order so earlier indices stay valid.
    for anchor_line, block in sorted(non_hero_inserts, key=lambda item: item[0], reverse=True):
        # Insert *after* the section H2 line.
        insert_at = anchor_line + 1
        lines[insert_at:insert_at] = ["", block, ""]

    # Now insert the hero block before the reader-status / summary block.
    hero_block = blocks[hero_index]
    if hero_block not in "\n".join(lines):
        hero_anchor = next(
            (
                index
                for index, line in enumerate(lines)
                if line.startswith("> **데이터 상태**")
                or line.startswith("> **내 관심 자산 영향**")
                or line.startswith(CONCLUSION_PREFIX)
            ),
            1 if lines and lines[0].startswith("# ") else 0,
        )
        lines[hero_anchor:hero_anchor] = ["", hero_block, ""]

    suffix = "\n" if markdown.endswith("\n") else ""
    return "\n".join(lines) + suffix


def validate_visual_asset(path: Path) -> None:
    """Validate a generated visual: existence, integrity, dimensions, manifest."""
    if not path.exists():
        raise VisualAssetError(f"visual asset missing: {path}")
    if path.suffix == ".png":
        _validate_png_asset(path)
    elif path.suffix in {".jpg", ".jpeg"}:
        _validate_jpeg_asset(path)
    elif path.suffix == ".svg":
        _validate_svg_asset(path)
    else:
        raise VisualAssetError(f"unsupported visual asset type: {path}")
    _assert_manifest_exists(path)


def _select_hero_index(asset_paths: tuple[Path, ...]) -> int:
    """Pick the single hero card index by priority, with a deterministic fallback."""
    by_kind: dict[str, int] = {}
    for index, path in enumerate(asset_paths):
        kind = path.stem
        if kind in _HERO_CARD_KINDS and kind not in by_kind:
            by_kind[kind] = index
    for kind in _HERO_PRIORITY:
        if kind in by_kind:
            return by_kind[kind]
    # Fall back to the first asset (should never trigger because
    # ``data-confidence`` is always rendered).
    return 0


def _visual_block(path: Path, *, markdown_path: Path) -> str:
    """Compose ``![label](rel)\\n*caption*`` for one asset."""
    label = _CARD_LABELS[path.stem]
    rel = visual_asset_relative_path(path, markdown_path)
    image_line = f"![{label}]({rel})"
    caption = _provenance_caption_for(path)
    if caption is None:
        return image_line
    return f"{image_line}\n{caption}"


def _provenance_caption_for(path: Path) -> str | None:
    try:
        manifest = read_manifest(path)
    except (FileNotFoundError, ValueError):
        return None
    return provenance_caption(manifest)


def _find_section_anchor(lines: list[str], card_kind: str) -> int | None:
    anchors = _SECTION_ANCHORS.get(card_kind, ())
    for anchor in anchors:
        for index, line in enumerate(lines):
            if line.startswith(anchor):
                return index
    return None


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
    """Pull conclusion / driver / caution anchors via the DEBT-060 chokepoint.

    Returns a dict whose missing entries collapse to ``""`` so the
    caller (:func:`_build_market_snapshot_card`) can fall back to the
    briefing's own ``market_summary`` / ``key_issues`` / ``today_watch``
    fields without distinguishing "absent" from "blank".
    """
    return {
        "conclusion": extract_conclusion(markdown) or "",
        "driver": extract_key_drivers(markdown) or "",
        "caution": extract_caution(markdown) or "",
    }


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
    config = load_openai_visual_config()
    image_bytes = generate_openai_visual(
        _build_openai_market_prompt(
            market_card=market_card,
            price_card=price_card,
            coverage=coverage,
        ),
        config=config,
    )
    if image_bytes is None:
        return None
    if not _is_png_bytes(image_bytes):
        return None
    path = visual_asset_path(target_date, segment, "ai-market-hero", extension=".png")
    _write_png(path, image_bytes)
    width, height = _read_png_dimensions(image_bytes) or (1536, 1024)
    manifest = build_ai_generated_provenance(
        asset_relative_path=path.name,
        card_kind="ai-market-hero",
        generated_at=datetime.now(tz=UTC),
        width=width,
        height=height,
        model_name=config.image_model,
    )
    write_manifest(manifest, path)
    validate_visual_asset(path)
    return path


def _prepare_external_context_image(
    *,
    target_date: date,
    segment: MarketSegment,
    items: tuple[NormalizedItem, ...],
) -> Path | None:
    external_image = fetch_contextual_external_image(items, target_date=target_date)
    if external_image is None:
        return None
    path = visual_asset_path(
        target_date,
        segment,
        "external-context-image",
        extension=external_image.extension,
    )
    _write_binary(path, external_image.content)
    # Build provenance manifest for external image (mandatory attribution).
    width, height = _read_image_dimensions(path) or (1024, 1024)
    content_type: Literal["image/png", "image/jpeg"] = (
        "image/png" if external_image.extension == ".png" else "image/jpeg"
    )
    manifest = build_external_provenance(
        asset_relative_path=path.name,
        card_kind="external-context-image",
        generated_at=datetime.now(tz=UTC),
        width=width,
        height=height,
        content_type=content_type,
        license_name=external_image.manifest.license,
        attribution=external_image.manifest.attribution,
        author=external_image.manifest.author,
        allowed_use=external_image.manifest.allowed_use,
        fetched_from_host=str(external_image.manifest.source_url.host or ""),
    )
    write_manifest(manifest, path)
    validate_visual_asset(path)
    return path


def _write_generated_svg_manifest(path: Path, *, card_kind: str) -> None:
    """Write the JSON sidecar for a freshly rendered SVG card."""
    manifest = build_generated_svg_provenance(
        asset_relative_path=path.name,
        card_kind=card_kind,
        generated_at=datetime.now(tz=UTC),
        width=SVG_WIDTH,
        height=SVG_HEIGHT,
    )
    write_manifest(manifest, path)


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
    reasons = "없음"
    if coverage.reason_codes:
        reasons = ", ".join(coverage.reason_codes)
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
        f"missing categories: {missing}; coverage reasons: {reasons}\n"
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
    dims = _read_png_dimensions(content)
    if dims is None:
        raise VisualAssetError(f"visual asset PNG has no readable dimensions: {path}")
    _assert_dimensions_in_range(dims, path)


def _validate_jpeg_asset(path: Path) -> None:
    content = path.read_bytes()
    if not _is_jpeg_bytes(content):
        raise VisualAssetError(f"visual asset is not a JPEG: {path}")
    dims = _read_jpeg_dimensions(content)
    if dims is None:
        raise VisualAssetError(f"visual asset JPEG has no readable dimensions: {path}")
    _assert_dimensions_in_range(dims, path)


def _validate_svg_asset(path: Path) -> None:
    content = path.read_text(encoding="utf-8")
    if len(content.encode("utf-8")) < _MIN_SVG_BYTES:
        raise VisualAssetError(f"visual asset too small: {path}")
    if "<svg" not in content or "</svg>" not in content:
        raise VisualAssetError(f"visual asset is not a complete SVG: {path}")
    if "<text" not in content:
        raise VisualAssetError(f"visual asset has no text content: {path}")
    dims = _read_svg_dimensions(content)
    if dims is None:
        raise VisualAssetError(f"visual asset SVG has no readable dimensions: {path}")
    _assert_dimensions_in_range(dims, path)


def _assert_manifest_exists(path: Path) -> None:
    sidecar = manifest_path_for(path)
    if not sidecar.exists():
        raise VisualAssetError(f"visual asset manifest missing: {sidecar}")
    try:
        manifest = read_manifest(path)
    except (OSError, ValueError) as exc:
        raise VisualAssetError(f"visual asset manifest invalid: {sidecar}") from exc
    _assert_manifest_dimensions_in_range(manifest, path)


def _assert_dimensions_in_range(dimensions: tuple[int, int], path: Path) -> None:
    width, height = dimensions
    if not (_MIN_DIMENSION <= width <= _MAX_DIMENSION):
        raise VisualAssetError(
            f"visual asset width {width} outside [{_MIN_DIMENSION}, {_MAX_DIMENSION}]: {path}"
        )
    if not (_MIN_DIMENSION <= height <= _MAX_DIMENSION):
        raise VisualAssetError(
            f"visual asset height {height} outside [{_MIN_DIMENSION}, {_MAX_DIMENSION}]: {path}"
        )


def _assert_manifest_dimensions_in_range(manifest: VisualProvenanceManifest, path: Path) -> None:
    _assert_dimensions_in_range(manifest.dimensions, path)


def _read_svg_dimensions(content: str) -> tuple[int, int] | None:
    try:
        root = fromstring(content)
    except ParseError:
        return None
    width_attr = root.attrib.get("width")
    height_attr = root.attrib.get("height")
    width = _parse_svg_dimension(width_attr)
    height = _parse_svg_dimension(height_attr)
    if width is None or height is None:
        view_box = root.attrib.get("viewBox")
        if view_box is not None:
            parts = view_box.split()
            if len(parts) == 4:
                try:
                    width = width or int(float(parts[2]))
                    height = height or int(float(parts[3]))
                except ValueError:
                    return None
    if width is None or height is None:
        return None
    return width, height


def _parse_svg_dimension(value: str | None) -> int | None:
    if value is None:
        return None
    match = _DIMENSION_NUMBER_RE.match(value.strip())
    if match is None:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _read_image_dimensions(path: Path) -> tuple[int, int] | None:
    if path.suffix == ".png":
        return _read_png_dimensions(path.read_bytes())
    if path.suffix in {".jpg", ".jpeg"}:
        return _read_jpeg_dimensions(path.read_bytes())
    if path.suffix == ".svg":
        return _read_svg_dimensions(path.read_text(encoding="utf-8"))
    return None


def _read_png_dimensions(content: bytes) -> tuple[int, int] | None:
    if len(content) < _PNG_IHDR_OFFSET + _PNG_IHDR_LENGTH:
        return None
    if not content.startswith(_PNG_SIGNATURE):
        return None
    # IHDR is 13 bytes starting after the 8-byte signature + 4-byte length
    # + 4-byte chunk type. Width/height are big-endian uint32 at offsets
    # 16 and 20.
    try:
        width = int.from_bytes(content[16:20], "big")
        height = int.from_bytes(content[20:24], "big")
    except (IndexError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def _read_jpeg_dimensions(content: bytes) -> tuple[int, int] | None:
    if not content.startswith(_JPEG_SIGNATURE):
        return None
    # Walk JPEG markers until an SOFn (0xFFC0..0xFFCF except 0xFFC4/0xFFC8/0xFFCC).
    index = 2
    length = len(content)
    while index + 9 < length:
        if content[index] != 0xFF:
            index += 1
            continue
        marker = content[index + 1]
        if marker in {0xD8, 0xD9}:
            index += 2
            continue
        # Standalone markers (RSTn, etc.) have no payload.
        if 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        if index + 4 > length:
            return None
        segment_length = int.from_bytes(content[index + 2 : index + 4], "big")
        if segment_length < 2:
            return None
        if 0xC0 <= marker <= 0xCF and marker not in {0xC4, 0xC8, 0xCC}:
            if index + 9 > length:
                return None
            height = int.from_bytes(content[index + 5 : index + 7], "big")
            width = int.from_bytes(content[index + 7 : index + 9], "big")
            if width <= 0 or height <= 0:
                return None
            return width, height
        index += 2 + segment_length
    return None


def _is_png_bytes(content: bytes) -> bool:
    if len(content) < _MIN_PNG_BYTES:
        return False
    return content.startswith(_PNG_SIGNATURE)


def _is_jpeg_bytes(content: bytes) -> bool:
    if len(content) < _MIN_PNG_BYTES:
        return False
    return content.startswith(_JPEG_SIGNATURE)


def _write_svg(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
    except OSError as exc:
        raise VisualAssetError(f"failed to write visual asset: {path}") from exc


def _write_png(path: Path, content: bytes) -> None:
    _write_binary(path, content)


def _write_binary(path: Path, content: bytes) -> None:
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
