"""External image policy for public briefing visual assets."""

from __future__ import annotations

import os
from datetime import date
from typing import Final, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

EXTERNAL_IMAGE_SCRAPING_ENABLED: Final[bool] = False
_ENABLE_ENV: Final[str] = "INVESTO_EXTERNAL_IMAGE_ASSETS"
_ALLOWED_HOSTS_ENV: Final[str] = "INVESTO_EXTERNAL_IMAGE_ALLOWED_HOSTS"

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
    _assert_public_http_url(str(manifest.source_url))


def external_image_scraping_enabled() -> bool:
    """Return whether licensed external image fetching is enabled for this run."""
    return os.environ.get(_ENABLE_ENV, "").strip() == "1"


def allowed_external_image_hosts() -> tuple[str, ...]:
    """Return optional host allow-list for external image fetching."""
    raw = os.environ.get(_ALLOWED_HOSTS_ENV, "")
    return tuple(host.strip().lower() for host in raw.split(",") if host.strip())


def assert_external_image_host_allowed(
    url: str,
    *,
    allowed_hosts: tuple[str, ...] | None = None,
) -> None:
    """Reject private/local hosts and enforce the optional host allow-list."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    _assert_public_http_url(url)
    if allowed_hosts and not any(
        host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts
    ):
        raise ExternalAssetPolicyError("external image host is not allowed")


def _assert_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ExternalAssetPolicyError("external image URL must be http(s)")
    host = parsed.hostname.lower()
    if (
        host in {"localhost", "0.0.0.0", "::1"}
        or host.startswith("127.")
        or host.startswith("10.")
        or host.startswith("192.168.")
        or _is_private_172_host(host)
    ):
        raise ExternalAssetPolicyError("external image URL must not target private hosts")


def _is_private_172_host(host: str) -> bool:
    parts = host.split(".")
    if len(parts) < 2 or parts[0] != "172":
        return False
    try:
        second = int(parts[1])
    except ValueError:
        return False
    return 16 <= second <= 31


__all__ = [
    "EXTERNAL_IMAGE_SCRAPING_ENABLED",
    "ExternalAssetManifest",
    "ExternalAssetPolicyError",
    "allowed_external_image_hosts",
    "assert_external_asset_allowed",
    "assert_external_image_host_allowed",
    "external_image_scraping_enabled",
]
