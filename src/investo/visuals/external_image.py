"""Licensed external image fetching for briefing visuals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

import httpx
from pydantic import ValidationError

from investo.models import NormalizedItem
from investo.visuals.policy import (
    ExternalAssetManifest,
    ExternalAssetPolicyError,
    allowed_external_image_hosts,
    assert_external_asset_allowed,
    assert_external_image_host_allowed,
    external_image_scraping_enabled,
)

_IMAGE_URL_KEYS: Final[tuple[str, ...]] = (
    "visual_image_url",
    "image_url",
    "thumbnail_url",
)
_LICENSE_KEYS: Final[tuple[str, ...]] = ("visual_image_license", "image_license", "license")
_ATTRIBUTION_KEYS: Final[tuple[str, ...]] = (
    "visual_image_attribution",
    "image_attribution",
    "attribution",
)
_AUTHOR_KEYS: Final[tuple[str, ...]] = ("visual_image_author", "image_author", "author")
_ALLOWED_USE_KEYS: Final[tuple[str, ...]] = (
    "visual_image_allowed_use",
    "image_allowed_use",
    "allowed_use",
)
_KIND_KEYS: Final[tuple[str, ...]] = ("visual_image_kind", "image_kind", "asset_kind")
_ALLOWED_CONTENT_TYPES: Final[dict[str, str]] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
}
_PNG_SIGNATURE: Final[bytes] = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE: Final[bytes] = b"\xff\xd8\xff"
_MAX_IMAGE_BYTES: Final[int] = 2_000_000
_MIN_IMAGE_BYTES: Final[int] = 100


@dataclass(frozen=True, slots=True)
class ExternalImageAsset:
    """Downloaded image bytes plus the license manifest that made reuse allowed."""

    content: bytes
    extension: str
    manifest: ExternalAssetManifest
    source_item_title: str


def fetch_contextual_external_image(
    items: tuple[NormalizedItem, ...],
    *,
    target_date: date,
    client: httpx.Client | None = None,
) -> ExternalImageAsset | None:
    """Fetch the first licensed contextual image advertised by source metadata."""
    if not external_image_scraping_enabled():
        return None
    for item in items:
        manifest = _manifest_from_item(item, target_date=target_date)
        if manifest is None:
            continue
        fetched = _fetch_manifest_image(manifest, item.title, client=client)
        if fetched is not None:
            return fetched
    return None


def _manifest_from_item(
    item: NormalizedItem,
    *,
    target_date: date,
) -> ExternalAssetManifest | None:
    image_url = _metadata_text(item, _IMAGE_URL_KEYS)
    license_text = _metadata_text(item, _LICENSE_KEYS)
    attribution = _metadata_text(item, _ATTRIBUTION_KEYS)
    author = _metadata_text(item, _AUTHOR_KEYS)
    allowed_use = _metadata_text(item, _ALLOWED_USE_KEYS)
    if not all((image_url, license_text, attribution, author, allowed_use)):
        return None
    kind = _metadata_text(item, _KIND_KEYS) or "explicit-license"
    try:
        manifest = ExternalAssetManifest(
            kind=kind,
            source_url=image_url,
            license=license_text,
            attribution=attribution,
            author=author,
            fetched_on=target_date,
            allowed_use=allowed_use,
        )
        assert_external_asset_allowed(manifest, scraping_enabled=True)
    except (ExternalAssetPolicyError, ValidationError):
        return None
    return manifest


def _fetch_manifest_image(
    manifest: ExternalAssetManifest,
    source_item_title: str,
    *,
    client: httpx.Client | None,
) -> ExternalImageAsset | None:
    url = str(manifest.source_url)
    try:
        assert_external_image_host_allowed(url, allowed_hosts=allowed_external_image_hosts())
        if client is None:
            with httpx.Client(timeout=15.0, follow_redirects=True) as owned_client:
                response = owned_client.get(url)
        else:
            response = client.get(url)
        response.raise_for_status()
        content = response.content
        extension = _extension_for_image(response.headers.get("content-type", ""), content)
        if extension is None:
            return None
        return ExternalImageAsset(
            content=content,
            extension=extension,
            manifest=manifest,
            source_item_title=source_item_title,
        )
    except (ExternalAssetPolicyError, httpx.HTTPError):
        return None


def _extension_for_image(content_type: str, content: bytes) -> str | None:
    if len(content) < _MIN_IMAGE_BYTES or len(content) > _MAX_IMAGE_BYTES:
        return None
    media_type = content_type.split(";", maxsplit=1)[0].strip().lower()
    if media_type in _ALLOWED_CONTENT_TYPES:
        expected = _ALLOWED_CONTENT_TYPES[media_type]
        if _matches_signature(expected, content):
            return expected
        return None
    if content.startswith(_PNG_SIGNATURE):
        return ".png"
    if content.startswith(_JPEG_SIGNATURE):
        return ".jpg"
    return None


def _matches_signature(extension: str, content: bytes) -> bool:
    if extension == ".png":
        return content.startswith(_PNG_SIGNATURE)
    return content.startswith(_JPEG_SIGNATURE)


def _metadata_text(item: NormalizedItem, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        raw_value = item.raw_metadata.get(key)
        if isinstance(raw_value, str):
            value = raw_value.strip()
            if value:
                return value
    return None


__all__ = ["ExternalImageAsset", "fetch_contextual_external_image"]
