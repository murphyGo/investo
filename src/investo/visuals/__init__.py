"""Deterministic visual asset contracts for briefing cards."""

from investo.visuals.cards import (
    CardKind,
    DataConfidenceCardInput,
    MarketSnapshotCardInput,
    PriceSnapshotCardInput,
    PriceSnapshotRow,
    WatchlistRelevanceCardInput,
    WatchlistRelevanceRow,
)
from investo.visuals.paths import visual_asset_dir, visual_asset_path, visual_asset_relative_path
from investo.visuals.policy import (
    EXTERNAL_IMAGE_SCRAPING_ENABLED,
    ExternalAssetManifest,
    ExternalAssetPolicyError,
    assert_external_asset_allowed,
)

__all__ = [
    "EXTERNAL_IMAGE_SCRAPING_ENABLED",
    "CardKind",
    "DataConfidenceCardInput",
    "ExternalAssetManifest",
    "ExternalAssetPolicyError",
    "MarketSnapshotCardInput",
    "PriceSnapshotCardInput",
    "PriceSnapshotRow",
    "WatchlistRelevanceCardInput",
    "WatchlistRelevanceRow",
    "assert_external_asset_allowed",
    "visual_asset_dir",
    "visual_asset_path",
    "visual_asset_relative_path",
]
