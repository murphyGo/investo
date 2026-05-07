"""Tests for u24 visual provenance manifests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from investo.visuals import provenance as provenance_module
from investo.visuals.provenance import (
    GENERATOR_NAME,
    SCHEMA_VERSION,
    VisualProvenanceManifest,
    _git_short_sha,
    _investo_version,
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


def test_investo_version_returns_package_version_when_available() -> None:
    """Default path — production has ``investo.__version__`` set."""
    assert _investo_version() == "0.1.0"


def test_investo_version_falls_back_to_git_short_sha_when_package_version_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """u26 — when ``__version__`` is unavailable, surface the running SHA.

    Persona #2: the previous fallback returned the literal ``"0"``, so
    captions read ``investo 0`` (a beta-looking artefact). The new
    fallback chain prefers a 7-char git SHA before the terminal
    ``"dev"`` literal.
    """
    monkeypatch.setattr(provenance_module, "_git_short_sha", lambda: "a1b2c3d")
    # Strip the ``__version__`` attribute so the ``from investo import
    # __version__`` line inside ``_investo_version`` actually raises.
    import investo

    monkeypatch.delattr(investo, "__version__", raising=False)

    assert _investo_version() == "a1b2c3d"


def test_investo_version_terminal_fallback_is_dev_literal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When neither ``__version__`` nor a git checkout is reachable, return ``"dev"``.

    Pins the persona-#2 expectation: never ``"0"`` again.
    """
    import investo

    monkeypatch.delattr(investo, "__version__", raising=False)
    monkeypatch.setattr(provenance_module, "_git_short_sha", lambda: None)

    assert _investo_version() == "dev"


def test_git_short_sha_returns_none_when_git_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Subprocess errors / missing git / non-repo working tree all → ``None``."""

    def _fake_run(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError("git not installed")

    monkeypatch.setattr(provenance_module.subprocess, "run", _fake_run)

    assert _git_short_sha() is None


def test_git_short_sha_validates_output_against_seven_hex_chars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken ``git`` wrapper that returns junk must not flow into the caption."""
    import subprocess as subprocess_module

    def _fake_run(*_args: object, **_kwargs: object) -> object:
        return subprocess_module.CompletedProcess(
            args=("git",),
            returncode=0,
            stdout="not-a-sha\n",
            stderr="",
        )

    monkeypatch.setattr(provenance_module.subprocess, "run", _fake_run)

    assert _git_short_sha() is None


def test_git_short_sha_accepts_auto_extended_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``git rev-parse --short=7`` extends past 7 chars on ambiguity.

    A 7-char prefix that collides in the local history forces git to
    return 8/9/.. up to the full 40-char SHA-1. The validator must
    accept those longer outputs so the caption does not silently fall
    back to ``investo dev``.
    """
    import subprocess as subprocess_module

    extended_sha = "a1b2c3d4e5"  # 10 hex chars

    def _fake_run(*_args: object, **_kwargs: object) -> object:
        return subprocess_module.CompletedProcess(
            args=("git",),
            returncode=0,
            stdout=f"{extended_sha}\n",
            stderr="",
        )

    monkeypatch.setattr(provenance_module.subprocess, "run", _fake_run)

    assert _git_short_sha() == extended_sha


def test_provenance_caption_never_reads_investo_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persona #2 regression pin — caption must never expose ``investo 0``.

    Even on the worst-case fallback (no package version + no git), the
    caption must read ``investo dev``, not ``investo 0``.
    """
    import investo

    monkeypatch.delattr(investo, "__version__", raising=False)
    monkeypatch.setattr(provenance_module, "_git_short_sha", lambda: None)

    manifest = build_generated_svg_provenance(
        asset_relative_path="dummy.svg",
        card_kind="data-confidence",
        generated_at=_GENERATED_AT,
        width=1200,
        height=630,
    )

    caption = provenance_caption(manifest)

    assert "investo dev" in caption
    assert "investo 0 " not in caption
    assert not caption.endswith("investo 0")


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
