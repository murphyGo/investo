"""Optional OpenAI image generation for briefing visuals."""

from __future__ import annotations

import base64
import binascii
import os
from dataclasses import dataclass
from typing import Final

import httpx

_ENABLE_ENV: Final[str] = "INVESTO_OPENAI_VISUALS"
_API_KEY_ENV: Final[str] = "OPENAI_API_KEY"
_RESPONSES_MODEL_ENV: Final[str] = "INVESTO_OPENAI_VISUAL_MODEL"
_IMAGE_MODEL_ENV: Final[str] = "INVESTO_OPENAI_IMAGE_TOOL_MODEL"
_IMAGE_SIZE_ENV: Final[str] = "INVESTO_OPENAI_IMAGE_SIZE"
_IMAGE_QUALITY_ENV: Final[str] = "INVESTO_OPENAI_IMAGE_QUALITY"
_OPENAI_RESPONSES_URL: Final[str] = "https://api.openai.com/v1/responses"


@dataclass(frozen=True, slots=True)
class OpenAIVisualConfig:
    """Runtime configuration for opt-in OpenAI briefing image generation."""

    enabled: bool
    api_key: str
    responses_model: str = "gpt-5.5"
    image_model: str = "gpt-image-1.5"
    size: str = "1536x1024"
    quality: str = "medium"
    timeout_seconds: float = 60.0


def load_openai_visual_config() -> OpenAIVisualConfig:
    """Load opt-in OpenAI visual configuration from environment variables."""
    api_key = os.environ.get(_API_KEY_ENV, "").strip()
    return OpenAIVisualConfig(
        enabled=os.environ.get(_ENABLE_ENV, "").strip() == "1" and bool(api_key),
        api_key=api_key,
        responses_model=os.environ.get(_RESPONSES_MODEL_ENV, "gpt-5.5").strip() or "gpt-5.5",
        image_model=os.environ.get(_IMAGE_MODEL_ENV, "gpt-image-1.5").strip() or "gpt-image-1.5",
        size=os.environ.get(_IMAGE_SIZE_ENV, "1536x1024").strip() or "1536x1024",
        quality=os.environ.get(_IMAGE_QUALITY_ENV, "medium").strip() or "medium",
    )


def generate_openai_visual(
    prompt: str,
    *,
    config: OpenAIVisualConfig | None = None,
    client: httpx.Client | None = None,
) -> bytes | None:
    """Generate a PNG image via OpenAI Responses API, returning ``None`` on fallback."""
    resolved = config or load_openai_visual_config()
    if not resolved.enabled:
        return None

    payload = {
        "model": resolved.responses_model,
        "input": prompt,
        "tools": [
            {
                "type": "image_generation",
                "model": resolved.image_model,
                "size": resolved.size,
                "quality": resolved.quality,
            }
        ],
    }
    headers = {"Authorization": f"Bearer {resolved.api_key}"}

    try:
        if client is None:
            with httpx.Client(timeout=resolved.timeout_seconds) as owned_client:
                response = owned_client.post(
                    _OPENAI_RESPONSES_URL,
                    headers=headers,
                    json=payload,
                )
        else:
            response = client.post(_OPENAI_RESPONSES_URL, headers=headers, json=payload)
        response.raise_for_status()
        image_base64 = _find_image_base64(response.json())
        if image_base64 is None:
            return None
        return base64.b64decode(image_base64, validate=True)
    except (binascii.Error, httpx.HTTPError, ValueError, TypeError):
        return None


def _find_image_base64(value: object) -> str | None:
    """Find an image payload in current or older Responses image output shapes."""
    if isinstance(value, dict):
        for key in ("result", "image_base64", "b64_json"):
            candidate = value.get(key)
            if _looks_like_base64(candidate):
                return candidate
        for child in value.values():
            found = _find_image_base64(child)
            if found is not None:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_image_base64(child)
            if found is not None:
                return found
    return None


def _looks_like_base64(value: object) -> bool:
    if not isinstance(value, str) or len(value) < 16:
        return False
    try:
        base64.b64decode(value, validate=True)
    except binascii.Error:
        return False
    return True


__all__ = [
    "OpenAIVisualConfig",
    "generate_openai_visual",
    "load_openai_visual_config",
]
