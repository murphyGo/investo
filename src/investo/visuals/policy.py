"""External image policy for public briefing visual assets."""

from __future__ import annotations

from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

EXTERNAL_IMAGE_SCRAPING_ENABLED: Final[bool] = False

AllowedExternalAssetKind = Literal["project-owned", "explicit-license"]


class ExternalAssetPolicyError(ValueError):
    """Raised when an external image asset violates the u19 policy."""


class ExternalAssetManifest(BaseModel):
    """Minimum manifest required before any external image can be republished."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: AllowedExternalAssetKind
    source_url: HttpUrl
    license: str = Field(min_length=1, max_length=160)
    attribution: str = Field(min_length=1, max_length=240)
    author: str = Field(min_length=1, max_length=160)
    fetched_on: date
    allowed_use: str = Field(min_length=1, max_length=240)


def assert_external_asset_allowed(
    manifest: ExternalAssetManifest | None,
    *,
    scraping_enabled: bool = EXTERNAL_IMAGE_SCRAPING_ENABLED,
) -> None:
    """Block third-party image reuse unless scraping is explicitly enabled and licensed."""
    if not scraping_enabled:
        raise ExternalAssetPolicyError("external image scraping is disabled for u19 v1")
    if manifest is None:
        raise ExternalAssetPolicyError("external image asset requires a license manifest")


__all__ = [
    "EXTERNAL_IMAGE_SCRAPING_ENABLED",
    "ExternalAssetManifest",
    "ExternalAssetPolicyError",
    "assert_external_asset_allowed",
]
