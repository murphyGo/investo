"""Tests for u33 Step 4 — free-tier webhook fan-out."""

from __future__ import annotations

import httpx
import pytest

from investo.notifier.webhooks import (
    WebhookEndpoint,
    dispatch_watchlist_alert,
    load_webhook_endpoints,
)


def test_load_endpoints_unset_returns_empty(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("INVESTO_WATCHLIST_WEBHOOKS", raising=False)
    assert load_webhook_endpoints() == ()


def test_load_endpoints_invalid_json_returns_empty() -> None:
    assert load_webhook_endpoints("not-json") == ()


def test_load_endpoints_parses_known_channels() -> None:
    raw = (
        '[{"channel": "slack", "url": "https://hooks.slack.com/x"},'
        ' {"channel": "discord", "url": "https://discord.com/api/y"}]'
    )
    endpoints = load_webhook_endpoints(raw)
    assert len(endpoints) == 2
    assert endpoints[0].channel == "slack"
    assert endpoints[1].channel == "discord"


def test_load_endpoints_drops_unknown_channels() -> None:
    raw = '[{"channel": "telegram", "url": "x"}, {"channel": "slack", "url": "y"}]'
    endpoints = load_webhook_endpoints(raw)
    assert len(endpoints) == 1
    assert endpoints[0].channel == "slack"


def test_load_endpoints_drops_missing_url() -> None:
    raw = '[{"channel": "slack"}, {"channel": "slack", "url": "y"}]'
    endpoints = load_webhook_endpoints(raw)
    assert len(endpoints) == 1


@pytest.mark.asyncio
async def test_dispatch_returns_zero_on_no_endpoints() -> None:
    async with httpx.AsyncClient() as http:
        count = await dispatch_watchlist_alert("hello", http=http, endpoints=())
    assert count == 0


@pytest.mark.asyncio
async def test_dispatch_uses_slack_text_field() -> None:
    captured: list[dict] = []  # type: ignore[type-arg]

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        count = await dispatch_watchlist_alert(
            "hi",
            http=http,
            endpoints=[WebhookEndpoint(channel="slack", url="https://hooks.slack.com/x")],
        )
    assert count == 1
    assert captured == [{"text": "hi"}]


@pytest.mark.asyncio
async def test_dispatch_uses_discord_content_field() -> None:
    captured: list[dict] = []  # type: ignore[type-arg]

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(204)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        count = await dispatch_watchlist_alert(
            "hi",
            http=http,
            endpoints=[WebhookEndpoint(channel="discord", url="https://discord.com/api/y")],
        )
    assert count == 1
    assert captured == [{"content": "hi"}]


@pytest.mark.asyncio
async def test_dispatch_swallows_4xx_failures() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        count = await dispatch_watchlist_alert(
            "hi",
            http=http,
            endpoints=[WebhookEndpoint(channel="slack", url="https://x")],
        )
    assert count == 0


@pytest.mark.asyncio
async def test_dispatch_skips_empty_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not be called for empty text")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        count = await dispatch_watchlist_alert(
            "  ",
            http=http,
            endpoints=[WebhookEndpoint(channel="slack", url="https://x")],
        )
    assert count == 0
