"""Tests for optional OpenAI briefing image generation."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from investo.visuals.openai_image import (
    OpenAIVisualConfig,
    generate_openai_visual,
    load_openai_visual_config,
)

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + (b"\0" * 128)


class _RecordingClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.payload: dict[str, Any] | None = None
        self.headers: dict[str, str] | None = None

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> httpx.Response:
        self.payload = json
        self.headers = headers
        return self.response


def test_load_openai_visual_config_requires_opt_in_and_key(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("INVESTO_OPENAI_VISUALS", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = load_openai_visual_config()

    assert config.enabled is False
    assert config.responses_model == "gpt-5.5"
    assert config.image_model == "gpt-image-1.5"


def test_generate_openai_visual_skips_disabled_config() -> None:
    client = _RecordingClient(httpx.Response(200, json={}))

    result = generate_openai_visual(
        "prompt",
        config=OpenAIVisualConfig(enabled=False, api_key="secret"),
        client=client,  # type: ignore[arg-type]
    )

    assert result is None
    assert client.payload is None


def test_generate_openai_visual_decodes_response_image_result() -> None:
    encoded = base64.b64encode(_PNG_BYTES).decode("ascii")
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    client = _RecordingClient(
        httpx.Response(
            200,
            request=request,
            json={"output": [{"type": "image_generation_call", "result": encoded}]},
        )
    )

    result = generate_openai_visual(
        "market prompt",
        config=OpenAIVisualConfig(enabled=True, api_key="test-key"),
        client=client,  # type: ignore[arg-type]
    )

    assert result == _PNG_BYTES
    assert client.payload is not None
    assert client.payload["model"] == "gpt-5.5"
    assert client.payload["tools"][0]["type"] == "image_generation"
    assert client.payload["tools"][0]["model"] == "gpt-image-1.5"
    assert client.headers == {"Authorization": "Bearer test-key"}


def test_generate_openai_visual_returns_none_on_api_failure() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    client = _RecordingClient(httpx.Response(429, request=request))

    result = generate_openai_visual(
        "market prompt",
        config=OpenAIVisualConfig(enabled=True, api_key="test-key"),
        client=client,  # type: ignore[arg-type]
    )

    assert result is None
