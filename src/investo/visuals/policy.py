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

AllowedExternalAssetKind = Literal["project-owned", "explicit-license", "curated-licensed"]

# u86 — recognized clean license tokens for the curated context-asset
# library (R2 / AC-1.3). The clearance gate is fail-closed: a license
# string that does not match one of these (case-insensitively, after a
# light normalization) is rejected. The set covers the confirmed
# sourcing scope: US federal-government public domain (17 U.S.C. §105),
# file-specific PD / CC0 declarations, and the commercially-reusable
# Unsplash / Pexels stock licenses.
CURATED_ALLOWED_LICENSES: Final[frozenset[str]] = frozenset(
    {
        "public-domain",
        "public domain",
        "pd",
        "pd-usgov",
        "us-gov-pd",
        "17-usc-105",
        "cc0",
        "cc0-1.0",
        "creative-commons-zero",
        "unsplash",
        "unsplash-license",
        "pexels",
        "pexels-license",
    }
)

# u86 — the explicit deferral marker token (I16). A registered key may
# lack a committed binary and still pass the CI gate (R8) only when its
# manifest ``allowed_use`` contains this exact substring, OR a sibling
# ``{asset_id}.deferred`` marker file is present. Both are
# machine-checkable; this string is the in-manifest form.
CURATED_DEFERRAL_MARKER: Final[str] = "not-yet-available"


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


def assert_curated_asset_allowed(manifest: ExternalAssetManifest | None) -> None:
    """Clear a curated-licensed asset WITHOUT requiring runtime scraping (u86 R4).

    Unlike :func:`assert_external_asset_allowed` — which hard-rejects
    while ``EXTERNAL_IMAGE_SCRAPING_ENABLED`` is ``False`` because it
    guards a *runtime fetch* — the curated library is pre-committed,
    pre-cleared local data. This branch never reads the scraping flag
    (R4 / AC-1.5) and never performs a fetch. It enforces:

    * manifest presence (R1);
    * ``kind == "curated-licensed"`` (I2 — the runtime ``project-owned``
      / ``explicit-license`` kinds never appear in the library);
    * a public http(s) ``source_url`` pointing at the original
      license-clean source for provenance traceability (I6);
    * a recognized clean ``license`` token (R2 / AC-1.3, fail-closed).

    Excluded-category rejection (R3) and the binary signature /
    dimension / byte budget (R4 / AC-1.1) are enforced by the library
    loader, not here.
    """
    if manifest is None:
        raise ExternalAssetPolicyError("curated asset requires a license manifest")
    if manifest.kind != "curated-licensed":
        raise ExternalAssetPolicyError(
            f"curated asset manifest kind must be 'curated-licensed', got {manifest.kind!r}"
        )
    _assert_public_http_url(str(manifest.source_url))
    if not is_curated_license_clean(manifest.license):
        raise ExternalAssetPolicyError(
            f"curated asset license is not a recognized clean token: {manifest.license!r}"
        )


def is_curated_license_clean(license_name: str) -> bool:
    """Return True iff ``license_name`` normalizes to a recognized clean token (R2)."""
    return _normalize_curated_license(license_name) in CURATED_ALLOWED_LICENSES


def _normalize_curated_license(license_name: str) -> str:
    """Normalize a license string for clean-token comparison (fail-closed)."""
    token = license_name.strip().lower()
    # Collapse common separators so "CC0 1.0" / "CC0-1.0" / "cc0_1.0" align.
    token = token.replace("_", "-").replace(" ", "-")
    # Strip a leading "the " / trailing " license" decoration.
    token = token.removesuffix("-license")
    return token


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
    "CURATED_ALLOWED_LICENSES",
    "CURATED_DEFERRAL_MARKER",
    "EXTERNAL_IMAGE_SCRAPING_ENABLED",
    "ExternalAssetManifest",
    "ExternalAssetPolicyError",
    "allowed_external_image_hosts",
    "assert_curated_asset_allowed",
    "assert_external_asset_allowed",
    "assert_external_image_host_allowed",
    "external_image_scraping_enabled",
    "is_curated_license_clean",
]
