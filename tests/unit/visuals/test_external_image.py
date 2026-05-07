"""Tests for licensed external image fetching."""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest

from investo.models import NormalizedItem
from investo.visuals.external_image import fetch_contextual_external_image

_TARGET = date(2026, 5, 7)
_JPEG_BYTES = b"\xff\xd8\xff" + (b"\0" * 128)
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + (b"\0" * 128)


def _item(raw_metadata: dict[str, str]) -> NormalizedItem:
    return NormalizedItem(
        source_name="licensed-image-source",
        category="news",
        title="AI stocks rally",
        url="https://example.com/article",
        published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        raw_metadata=raw_metadata,
    )


def _client(content: bytes, content_type: str = "image/jpeg") -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": content_type},
            content=content,
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def _metadata() -> dict[str, str]:
    return {
        "visual_image_url": "https://images.example.com/market.jpg",
        "visual_image_license": "CC BY 4.0",
        "visual_image_attribution": "Example Images / CC BY 4.0",
        "visual_image_author": "Example Images",
        "visual_image_allowed_use": "Public redistribution with attribution",
    }


def test_fetch_contextual_external_image_requires_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INVESTO_EXTERNAL_IMAGE_ASSETS", raising=False)
    result = fetch_contextual_external_image(
        (_item(_metadata()),),
        target_date=_TARGET,
        client=_client(_JPEG_BYTES),
    )

    assert result is None


def test_fetch_contextual_external_image_downloads_licensed_jpeg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_EXTERNAL_IMAGE_ASSETS", "1")
    result = fetch_contextual_external_image(
        (_item(_metadata()),),
        target_date=_TARGET,
        client=_client(_JPEG_BYTES),
    )

    assert result is not None
    assert result.content == _JPEG_BYTES
    assert result.extension == ".jpg"
    assert result.manifest.license == "CC BY 4.0"
    assert result.source_item_title == "AI stocks rally"


def test_fetch_contextual_external_image_skips_missing_license(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata = _metadata()
    metadata.pop("visual_image_license")
    monkeypatch.setenv("INVESTO_EXTERNAL_IMAGE_ASSETS", "1")
    result = fetch_contextual_external_image(
        (_item(metadata),),
        target_date=_TARGET,
        client=_client(_JPEG_BYTES),
    )

    assert result is None


def test_fetch_contextual_external_image_rejects_content_type_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_EXTERNAL_IMAGE_ASSETS", "1")
    result = fetch_contextual_external_image(
        (_item(_metadata()),),
        target_date=_TARGET,
        client=_client(_PNG_BYTES, content_type="image/jpeg"),
    )

    assert result is None
