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
from investo.visuals.external_image import ExternalImageAsset, fetch_contextual_external_image
from investo.visuals.openai_image import (
    OpenAIVisualConfig,
    generate_openai_visual,
    load_openai_visual_config,
)
from investo.visuals.paths import visual_asset_dir, visual_asset_path, visual_asset_relative_path
from investo.visuals.policy import (
    EXTERNAL_IMAGE_SCRAPING_ENABLED,
    ExternalAssetManifest,
    ExternalAssetPolicyError,
    allowed_external_image_hosts,
    assert_external_asset_allowed,
    assert_external_image_host_allowed,
    external_image_scraping_enabled,
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
    "ExternalImageAsset",
    "MarketSnapshotCardInput",
    "OpenAIVisualConfig",
    "PreparedVisualAssets",
    "PriceSnapshotCardInput",
    "PriceSnapshotRow",
    "VisualAssetError",
    "WatchlistRelevanceCardInput",
    "WatchlistRelevanceRow",
    "allowed_external_image_hosts",
    "assert_external_asset_allowed",
    "assert_external_image_host_allowed",
    "build_data_confidence_card",
    "build_price_snapshot_card",
    "build_watchlist_relevance_card",
    "external_image_scraping_enabled",
    "fetch_contextual_external_image",
    "generate_openai_visual",
    "insert_visual_links",
    "load_openai_visual_config",
    "prepare_segment_visual_assets",
    "render_card_svg",
    "validate_visual_asset",
    "visual_asset_dir",
    "visual_asset_path",
    "visual_asset_relative_path",
]
