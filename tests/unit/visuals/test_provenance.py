"""Tests for u24 visual provenance manifests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from investo.visuals.provenance import (
    GENERATOR_NAME,
    SCHEMA_VERSION,
    VisualProvenanceManifest,
    build_ai_generated_provenance,
    build_external_provenance,
    build_generated_svg_provenance,
    manifest_path_for,
    provenance_caption,
    read_manifest,
    sanitize_provenance_text,
    write_manifest,
)

_GENERATED_AT = datetime(2026, 5, 7, 12, 30, tzinfo=UTC)


def test_build_generated_svg_provenance_uses_investo_generator(tmp_path: Path) -> None:
    asset_path = tmp_path / "data-confidence.svg"
    asset_path.write_text("<svg></svg>", encoding="utf-8")

    manifest = build_generated_svg_provenance(
        asset_relative_path="data-confidence.svg",
        card_kind="data-confidence",
        generated_at=_GENERATED_AT,
        width=1200,
        height=630,
    )

    assert manifest.source_type == "generated_svg"
    assert manifest.generator == GENERATOR_NAME
    assert manifest.schema_version == SCHEMA_VERSION
    assert manifest.dimensions == (1200, 630)
    assert manifest.content_type == "image/svg+xml"
    assert manifest.card_kind == "data-confidence"


def test_build_ai_generated_provenance_records_model_and_redacts_secrets() -> None:
    manifest = build_ai_generated_provenance(
        asset_relative_path="ai-market-hero.png",
        card_kind="ai-market-hero",
        generated_at=_GENERATED_AT,
        width=1536,
        height=1024,
        # Pretend the model name string is contaminated with a long
        # base64-ish run (OAuth/JWT/PAT shape) — sanitizer must redact
        # it before it lands in the manifest.
        model_name=("gpt-image-1.5 token=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUV"),
    )

    assert manifest.source_type == "ai_generated"
    assert manifest.content_type == "image/png"
    assert "ai_model" in manifest.additional_metadata
    assert "[REDACTED]" in manifest.additional_metadata["ai_model"]
    assert (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUV"
        not in manifest.additional_metadata["ai_model"]
    )


def test_build_external_provenance_redacts_secret_query_strings() -> None:
    manifest = build_external_provenance(
        asset_relative_path="external-context-image.jpg",
        card_kind="external-context-image",
        generated_at=_GENERATED_AT,
        width=1024,
        height=768,
        content_type="image/jpeg",
        license_name="CC-BY-4.0",
        attribution="Example Source ?api_key=supersecretvalue123",
        author="Jane Doe",
        allowed_use="editorial",
        fetched_from_host="images.example.com",
    )

    assert manifest.source_type == "external"
    assert "supersecretvalue123" not in manifest.source_attribution
    assert "[REDACTED]" in manifest.source_attribution
    # author / allowed_use / license / host stay in additional_metadata
    assert manifest.additional_metadata["license"] == "CC-BY-4.0"
    assert manifest.additional_metadata["author"] == "Jane Doe"
    assert manifest.additional_metadata["fetched_from_host"] == "images.example.com"


def test_sanitize_provenance_text_redacts_env_var_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-veryrealsecretvaluedefinitelyok")

    sanitized = sanitize_provenance_text("model=gpt key=sk-veryrealsecretvaluedefinitelyok extra")

    assert "sk-veryrealsecretvaluedefinitelyok" not in sanitized
    assert "[REDACTED]" in sanitized


def test_write_manifest_round_trip(tmp_path: Path) -> None:
    asset_path = tmp_path / "card.svg"
    asset_path.write_text("<svg></svg>", encoding="utf-8")
    manifest = build_generated_svg_provenance(
        asset_relative_path="card.svg",
        card_kind="data-confidence",
        generated_at=_GENERATED_AT,
        width=1200,
        height=630,
    )

    sidecar = write_manifest(manifest, asset_path)

    assert sidecar == manifest_path_for(asset_path)
    assert sidecar.exists()
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["asset_path"] == "card.svg"
    assert payload["source_type"] == "generated_svg"
    assert payload["dimensions"] == [1200, 630]

    loaded = read_manifest(asset_path)
    assert loaded == manifest


def test_read_manifest_missing_raises(tmp_path: Path) -> None:
    asset_path = tmp_path / "missing.svg"
    asset_path.write_text("<svg></svg>", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        read_manifest(asset_path)


def test_provenance_caption_renders_korean_label() -> None:
    manifest = build_generated_svg_provenance(
        asset_relative_path="dummy.svg",
        card_kind="data-confidence",
        generated_at=_GENERATED_AT,
        width=1200,
        height=630,
    )

    caption = provenance_caption(manifest)

    assert caption.startswith("*이미지: 데이터 신뢰도")
    assert "investo 자체 생성" in caption
    assert "2026-05-07" in caption


def test_provenance_caption_external_attribution_safe() -> None:
    manifest = build_external_provenance(
        asset_relative_path="external-context-image.jpg",
        card_kind="external-context-image",
        generated_at=_GENERATED_AT,
        width=1024,
        height=768,
        content_type="image/jpeg",
        license_name="CC-BY-4.0",
        attribution="Example Source",
        author="Jane Doe",
        allowed_use="editorial",
        fetched_from_host="images.example.com",
    )

    caption = provenance_caption(manifest)

    assert "외부 라이선스 이미지" in caption
    # Sanity: caption never contains a token-shaped string by construction.
    assert "Bearer" not in caption


def test_manifest_rejects_non_positive_dimensions() -> None:
    with pytest.raises(ValueError):
        VisualProvenanceManifest(
            schema_version=SCHEMA_VERSION,
            asset_path="card.svg",
            source_type="generated_svg",
            source_attribution="investo",
            generated_at=_GENERATED_AT,
            generator="investo",
            version="0.1.0",
            content_type="image/svg+xml",
            dimensions=(0, 100),
            card_kind="data-confidence",
        )


def test_manifest_extra_fields_rejected() -> None:
    with pytest.raises(ValueError):
        VisualProvenanceManifest.model_validate(
            {
                "schema_version": SCHEMA_VERSION,
                "asset_path": "card.svg",
                "source_type": "generated_svg",
                "source_attribution": "investo",
                "generated_at": _GENERATED_AT.isoformat(),
                "generator": "investo",
                "version": "0.1.0",
                "content_type": "image/svg+xml",
                "dimensions": [1200, 630],
                "card_kind": "data-confidence",
                "unexpected_field": "boom",
            }
        )
