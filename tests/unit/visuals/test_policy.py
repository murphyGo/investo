"""Tests for u19 external image policy."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from investo.visuals.policy import (
    EXTERNAL_IMAGE_SCRAPING_ENABLED,
    ExternalAssetManifest,
    ExternalAssetPolicyError,
    assert_external_asset_allowed,
)


def test_external_image_scraping_is_disabled_by_default() -> None:
    assert EXTERNAL_IMAGE_SCRAPING_ENABLED is False
    with pytest.raises(ExternalAssetPolicyError, match="disabled"):
        assert_external_asset_allowed(None)


def test_external_asset_requires_manifest_when_policy_is_enabled() -> None:
    with pytest.raises(ExternalAssetPolicyError, match="requires a license manifest"):
        assert_external_asset_allowed(None, scraping_enabled=True)


def test_external_asset_manifest_is_required_for_allowed_external_asset() -> None:
    manifest = ExternalAssetManifest(
        kind="explicit-license",
        source_url="https://example.com/image.png",
        license="CC BY 4.0",
        attribution="Example Author / CC BY 4.0",
        author="Example Author",
        fetched_on=date(2026, 5, 7),
        allowed_use="Public redistribution with attribution",
    )

    assert_external_asset_allowed(manifest, scraping_enabled=True)


def test_external_asset_manifest_rejects_missing_license_terms() -> None:
    with pytest.raises(ValidationError):
        ExternalAssetManifest(
            kind="explicit-license",
            source_url="https://example.com/image.png",
            license="",
            attribution="Example Author / CC BY 4.0",
            author="Example Author",
            fetched_on=date(2026, 5, 7),
            allowed_use="Public redistribution with attribution",
        )
