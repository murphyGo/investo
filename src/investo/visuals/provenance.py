"""Provenance manifests for briefing visual assets (u24).

Every visual asset published in the public archive must declare *where it
came from* and *who generated it*. This module owns:

* :class:`VisualProvenanceManifest` — closed pydantic v2 schema covering
  the three asset families u19/u22 emit (``generated_svg``,
  ``ai_generated``, ``external``).
* :func:`build_generated_svg_provenance` /
  :func:`build_ai_generated_provenance` /
  :func:`build_external_provenance` — typed builders that pre-sanitize
  any reader-facing text before it lands in a manifest.
* :func:`write_manifest` / :func:`read_manifest` — JSON sidecar I/O. The
  manifest lives at ``<asset>.json`` beside the asset file, so the
  publisher's archive sweep keeps them together.
* :func:`provenance_caption` — short Korean attribution caption used
  next to each visual in the public markdown.

Secret hygiene (R8/R13)
-----------------------
``source_attribution`` and every ``additional_metadata`` value pass
through :func:`sanitize_provenance_text`, which delegates to
:func:`investo.models.sanitize_source_error_message`. The sanitizer
already redacts:

* current values of the secret env vars (``OPENAI_API_KEY``,
  ``TELEGRAM_BOT_TOKEN``, etc.)
* Telegram bot-token / chat-id shapes
* JWT / OAuth / PAT base64 runs
* ``?key=value&...`` query strings (which can carry API keys)

The manifest never carries the raw OpenAI prompt, the raw image URL
query string, or any environment value. The single sanitizer chokepoint
is the only allowed write path — direct ``model.copy(update={...})``
around the sanitizer is not allowed.

Free-API rule
-------------
The ``external`` source-type is **schema only** in u24. The builder
exists so the manifest layer is forward-compatible, but no code path
actually fetches third-party imagery in v1 (see
``visuals/policy.py``). Any real fetch implementation must remain
free-tier only.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from investo.models import sanitize_source_error_message

VisualSourceType = Literal["generated_svg", "ai_generated", "external"]

GENERATOR_NAME: Final[str] = "investo"
SCHEMA_VERSION: Final[str] = "1"
_MANIFEST_SUFFIX: Final[str] = ".json"

_CARD_KIND_LABELS: Final[dict[str, str]] = {
    "ai-market-hero": "AI 시황 이미지",
    "data-confidence": "데이터 신뢰도",
    "external-context-image": "실제 시황 이미지",
    "market-snapshot": "시장 스냅샷",
    "price-snapshot": "가격 스냅샷",
    "watchlist-relevance": "관심 자산 관련성",
}

_SOURCE_TYPE_KOREAN: Final[dict[VisualSourceType, str]] = {
    "generated_svg": "investo 자체 생성",
    "ai_generated": "AI 생성 이미지",
    "external": "외부 라이선스 이미지",
}


def sanitize_provenance_text(text: str) -> str:
    """Redact secret-shaped substrings from any reader-facing manifest text.

    Single chokepoint for ``source_attribution`` and
    ``additional_metadata`` writes. Delegates to
    :func:`sanitize_source_error_message` (R13 — same policy as the
    coverage failure_reason sanitizer) so manifests never carry env
    values, bot tokens, chat ids, JWT-shaped strings, or query string
    secrets.
    """
    return sanitize_source_error_message(text)


class VisualProvenanceManifest(BaseModel):
    """Closed manifest schema for any briefing visual asset.

    The schema covers three source types — generated SVG cards (u19/u22),
    AI-generated PNGs (u23 OpenAI), and licensed external images (u19
    schema, no fetcher in v1). Adding a new source type requires a
    schema update + audit log entry, not a runtime config tweak.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default=SCHEMA_VERSION, min_length=1, max_length=8)
    asset_path: str = Field(min_length=1, max_length=240)
    source_type: VisualSourceType
    source_attribution: str = Field(min_length=1, max_length=240)
    generated_at: datetime
    generator: str = Field(min_length=1, max_length=80)
    version: str = Field(min_length=1, max_length=24)
    content_type: Literal["image/svg+xml", "image/png", "image/jpeg"]
    dimensions: tuple[int, int] = Field(min_length=2, max_length=2)
    additional_metadata: dict[str, str] = Field(default_factory=dict)
    card_kind: str = Field(min_length=1, max_length=48)

    @field_validator("source_attribution", "generator", "version")
    @classmethod
    def _scrub_text_field(cls, value: str) -> str:
        return sanitize_provenance_text(value)

    @field_validator("additional_metadata")
    @classmethod
    def _scrub_additional_metadata(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            return {}
        return {key: sanitize_provenance_text(item) for key, item in value.items()}

    @field_validator("dimensions")
    @classmethod
    def _check_dimensions(cls, value: tuple[int, int]) -> tuple[int, int]:
        width, height = value
        if width <= 0 or height <= 0:
            raise ValueError("dimensions must be positive")
        return value


def manifest_path_for(asset_path: Path) -> Path:
    """Return the manifest sidecar path for an asset (``<asset>.json``)."""
    return asset_path.with_suffix(asset_path.suffix + _MANIFEST_SUFFIX)


def build_generated_svg_provenance(
    *,
    asset_relative_path: str,
    card_kind: str,
    generated_at: datetime,
    width: int,
    height: int,
    source_attribution: str = "investo 자체 데이터로 결정적 SVG 카드 생성",
    additional_metadata: dict[str, str] | None = None,
) -> VisualProvenanceManifest:
    """Build a manifest for a deterministically rendered SVG card."""
    return VisualProvenanceManifest(
        asset_path=asset_relative_path,
        source_type="generated_svg",
        source_attribution=source_attribution,
        generated_at=generated_at,
        generator=GENERATOR_NAME,
        version=_investo_version(),
        content_type="image/svg+xml",
        dimensions=(width, height),
        additional_metadata=additional_metadata or {},
        card_kind=card_kind,
    )


def build_ai_generated_provenance(
    *,
    asset_relative_path: str,
    card_kind: str,
    generated_at: datetime,
    width: int,
    height: int,
    model_name: str,
    source_attribution: str = "OpenAI 이미지 모델 자동 생성 (프롬프트는 공개 데이터만 사용)",
) -> VisualProvenanceManifest:
    """Build a manifest for an AI-generated PNG hero image."""
    safe_model = sanitize_provenance_text(model_name)
    return VisualProvenanceManifest(
        asset_path=asset_relative_path,
        source_type="ai_generated",
        source_attribution=source_attribution,
        generated_at=generated_at,
        generator=GENERATOR_NAME,
        version=_investo_version(),
        content_type="image/png",
        dimensions=(width, height),
        additional_metadata={"ai_model": safe_model},
        card_kind=card_kind,
    )


def build_external_provenance(
    *,
    asset_relative_path: str,
    card_kind: str,
    generated_at: datetime,
    width: int,
    height: int,
    content_type: Literal["image/png", "image/jpeg"],
    license_name: str,
    attribution: str,
    author: str,
    allowed_use: str,
    fetched_from_host: str,
) -> VisualProvenanceManifest:
    """Build a manifest for an externally licensed image (schema-only in v1).

    The actual fetcher remains gated by the u19 policy
    (``EXTERNAL_IMAGE_SCRAPING_ENABLED``); this builder only ensures the
    manifest layer can describe such an asset without leaking secrets.
    No real third-party network calls are introduced here.
    """
    safe_license = sanitize_provenance_text(license_name)
    safe_attribution = sanitize_provenance_text(attribution)
    safe_author = sanitize_provenance_text(author)
    safe_use = sanitize_provenance_text(allowed_use)
    safe_host = sanitize_provenance_text(fetched_from_host)
    composed_attribution = f"{safe_attribution} ({safe_author}) — {safe_license}"
    return VisualProvenanceManifest(
        asset_path=asset_relative_path,
        source_type="external",
        source_attribution=composed_attribution,
        generated_at=generated_at,
        generator=GENERATOR_NAME,
        version=_investo_version(),
        content_type=content_type,
        dimensions=(width, height),
        additional_metadata={
            "license": safe_license,
            "author": safe_author,
            "allowed_use": safe_use,
            "fetched_from_host": safe_host,
        },
        card_kind=card_kind,
    )


def write_manifest(manifest: VisualProvenanceManifest, asset_path: Path) -> Path:
    """Write a manifest JSON sidecar atomically beside ``asset_path``."""
    sidecar = manifest_path_for(asset_path)
    payload = manifest.model_dump(mode="json")
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = sidecar.with_suffix(sidecar.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(sidecar)
    return sidecar


def read_manifest(asset_path: Path) -> VisualProvenanceManifest:
    """Read and validate the manifest sidecar for ``asset_path``."""
    sidecar = manifest_path_for(asset_path)
    if not sidecar.exists():
        raise FileNotFoundError(f"manifest missing for asset: {asset_path}")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    return VisualProvenanceManifest.model_validate(payload)


def provenance_caption(manifest: VisualProvenanceManifest) -> str:
    """Render a short Korean attribution caption for public markdown.

    The caption is intentionally short (single italic line) so the
    public archive page stays readable. ``source_attribution`` is
    already sanitized at field-validator time, so this function may
    interpolate it safely.
    """
    label = _CARD_KIND_LABELS.get(manifest.card_kind, manifest.card_kind)
    type_label = _SOURCE_TYPE_KOREAN[manifest.source_type]
    timestamp = manifest.generated_at.date().isoformat()
    return (
        f"*이미지: {label} · 출처: {type_label} · "
        f"생성: {manifest.generator} {manifest.version} · {timestamp} UTC*"
    )


def _investo_version() -> str:
    """Return the running ``investo`` package version, with a safe fallback."""
    try:
        from investo import __version__ as version
    except ImportError:  # pragma: no cover - defensive only
        return "0"
    return str(version)


__all__ = [
    "GENERATOR_NAME",
    "SCHEMA_VERSION",
    "VisualProvenanceManifest",
    "VisualSourceType",
    "build_ai_generated_provenance",
    "build_external_provenance",
    "build_generated_svg_provenance",
    "manifest_path_for",
    "provenance_caption",
    "read_manifest",
    "sanitize_provenance_text",
    "write_manifest",
]
