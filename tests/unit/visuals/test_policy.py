"""Tests for u19 external image policy."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from investo.visuals.policy import (
    EXTERNAL_IMAGE_SCRAPING_ENABLED,
    ExternalAssetManifest,
    ExternalAssetPolicyError,
    allowed_external_image_hosts,
    assert_external_asset_allowed,
    assert_external_image_host_allowed,
    external_image_scraping_enabled,
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


def test_external_image_scraping_env_is_strict_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_EXTERNAL_IMAGE_ASSETS", "true")
    assert external_image_scraping_enabled() is False

    monkeypatch.setenv("INVESTO_EXTERNAL_IMAGE_ASSETS", "1")
    assert external_image_scraping_enabled() is True


def test_external_image_host_policy_blocks_private_hosts() -> None:
    with pytest.raises(ExternalAssetPolicyError, match="private"):
        assert_external_image_host_allowed("https://127.0.0.1/image.jpg")


def test_external_image_host_policy_can_enforce_allow_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_EXTERNAL_IMAGE_ALLOWED_HOSTS", "images.example.com")
    assert allowed_external_image_hosts() == ("images.example.com",)
    assert_external_image_host_allowed(
        "https://cdn.images.example.com/image.jpg",
        allowed_hosts=allowed_external_image_hosts(),
    )
    with pytest.raises(ExternalAssetPolicyError, match="not allowed"):
        assert_external_image_host_allowed(
            "https://other.example.com/image.jpg",
            allowed_hosts=allowed_external_image_hosts(),
        )
