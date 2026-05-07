"""Deterministic visual asset contracts for briefing cards."""

from investo.visuals.assets import (
    PreparedVisualAssets,
    VisualAssetError,
    insert_visual_links,
    prepare_segment_visual_assets,
    validate_visual_asset,
)
from investo.visuals.cards import (
    CardKind,
    DataConfidenceCardInput,
    MarketSnapshotCardInput,
    PriceSnapshotCardInput,
    PriceSnapshotRow,
    WatchlistRelevanceCardInput,
    WatchlistRelevanceRow,
    build_data_confidence_card,
    build_price_snapshot_card,
    build_watchlist_relevance_card,
)
from investo.visuals.paths import visual_asset_dir, visual_asset_path, visual_asset_relative_path
from investo.visuals.policy import (
    EXTERNAL_IMAGE_SCRAPING_ENABLED,
    ExternalAssetManifest,
    ExternalAssetPolicyError,
    assert_external_asset_allowed,
)
from investo.visuals.render import SVG_HEIGHT, SVG_WIDTH, render_card_svg

__all__ = [
    "EXTERNAL_IMAGE_SCRAPING_ENABLED",
    "SVG_HEIGHT",
    "SVG_WIDTH",
    "CardKind",
    "DataConfidenceCardInput",
    "ExternalAssetManifest",
    "ExternalAssetPolicyError",
    "MarketSnapshotCardInput",
    "PreparedVisualAssets",
    "PriceSnapshotCardInput",
    "PriceSnapshotRow",
    "VisualAssetError",
    "WatchlistRelevanceCardInput",
    "WatchlistRelevanceRow",
    "assert_external_asset_allowed",
    "build_data_confidence_card",
    "build_price_snapshot_card",
    "build_watchlist_relevance_card",
    "insert_visual_links",
    "prepare_segment_visual_assets",
    "render_card_svg",
    "validate_visual_asset",
    "visual_asset_dir",
    "visual_asset_path",
    "visual_asset_relative_path",
]
