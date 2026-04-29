"""Tests for ``investo.notifier._telegram`` HTTP helper.

Pins the non-raising contract + bot-token redaction (NFR-007).
HTTP is mocked via ``httpx.MockTransport``; no real network access.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest

from investo.notifier._telegram import (
    _redact_bot_token,
    send_message,
    telegram_api_url,
)

# A realistic-looking bot token for redaction tests.
_BOT_TOKEN = "1234567890:AAFakeBotTokenThatLooksLikeARealOneXYZ"
_CHAT_ID = "@example_channel"


@asynccontextmanager
async def _mock_client(handler: object) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport) as client:
        yield client


# ---------------------------------------------------------------------------
# URL builder
# ---------------------------------------------------------------------------


def test_telegram_api_url_default_method() -> None:
    assert telegram_api_url(_BOT_TOKEN) == (f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage")


def test_telegram_api_url_custom_method() -> None:
    assert telegram_api_url(_BOT_TOKEN, method="getMe") == (
        f"https://api.telegram.org/bot{_BOT_TOKEN}/getMe"
    )


# ---------------------------------------------------------------------------
# Happy path — Telegram API success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_returns_ok_on_telegram_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    async with _mock_client(handler) as client:
        result = await send_message(
            client,
            bot_token=_BOT_TOKEN,
            chat_id=_CHAT_ID,
            text="hello",
        )

    assert result.ok is True
    assert result.message_id == 42
    assert result.error is None


@pytest.mark.asyncio
async def test_send_message_request_body_has_expected_fields() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured.update(_json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with _mock_client(handler) as client:
        await send_message(
            client,
            bot_token=_BOT_TOKEN,
            chat_id=_CHAT_ID,
            text="hello *world*",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

    assert captured["chat_id"] == _CHAT_ID
    assert captured["text"] == "hello *world*"
    assert captured["parse_mode"] == "Markdown"
    assert captured["disable_web_page_preview"] is True


@pytest.mark.asyncio
async def test_send_message_request_url_targets_bot_token_endpoint() -> None:
    captured_url: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_url.append(str(request.url))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with _mock_client(handler) as client:
        await send_message(client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x")

    # The token IS in the URL (this is correct — that's how Telegram
    # auths the call). The redaction kicks in only when the URL ends
    # up in error strings.
    assert _BOT_TOKEN in captured_url[0]


# ---------------------------------------------------------------------------
# Telegram API error (HTTP 200 but body says ok: false)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_handles_telegram_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"ok": False, "description": "chat not found"},
        )

    async with _mock_client(handler) as client:
        result = await send_message(client, bot_token=_BOT_TOKEN, chat_id="bad", text="x")

    assert result.ok is False
    assert result.message_id is None
    assert result.error is not None
    assert "chat not found" in result.error


@pytest.mark.asyncio
async def test_send_message_handles_non_200_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Too Many Requests")

    async with _mock_client(handler) as client:
        result = await send_message(client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x")

    assert result.ok is False
    assert result.error is not None
    assert "429" in result.error


# ---------------------------------------------------------------------------
# HTTP transport errors — non-raising
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_handles_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("synthetic timeout")

    async with _mock_client(handler) as client:
        result = await send_message(client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x")

    assert result.ok is False
    assert result.error is not None
    assert "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_send_message_handles_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic connect failure")

    async with _mock_client(handler) as client:
        result = await send_message(client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x")

    assert result.ok is False
    assert result.error is not None
    assert "http error" in result.error.lower() or "connect" in result.error.lower()


@pytest.mark.asyncio
async def test_send_message_handles_invalid_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>500 internal</html>")

    async with _mock_client(handler) as client:
        result = await send_message(client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x")

    assert result.ok is False
    assert result.error is not None


# ---------------------------------------------------------------------------
# Bot-token redaction (NFR-007)
# ---------------------------------------------------------------------------


def test_redact_bot_token_replaces_url_segment() -> None:
    leaked = (
        f"http error: failed to connect to https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage"
    )
    redacted = _redact_bot_token(leaked)
    assert _BOT_TOKEN not in redacted
    assert "/bot[REDACTED]" in redacted


def test_redact_bot_token_handles_multiple_occurrences() -> None:
    leaked = (
        f"first https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage "
        f"second https://api.telegram.org/bot{_BOT_TOKEN}/getUpdates"
    )
    redacted = _redact_bot_token(leaked)
    assert _BOT_TOKEN not in redacted
    assert redacted.count("/bot[REDACTED]") == 2


def test_redact_bot_token_passthrough_when_no_token() -> None:
    plain = "no token in this string"
    assert _redact_bot_token(plain) == plain


@pytest.mark.asyncio
async def test_send_message_redacts_token_in_timeout_error() -> None:
    """A timeout whose message embeds the URL (with token) → SendResult
    .error must NOT contain the token.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        # Some httpx versions include the URL in the timeout message.
        # Simulate by raising with a message that contains the URL.
        raise httpx.TimeoutException(
            f"timeout reaching https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage"
        )

    async with _mock_client(handler) as client:
        result = await send_message(client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x")

    assert result.ok is False
    assert result.error is not None
    assert _BOT_TOKEN not in result.error
    assert "[REDACTED]" in result.error


@pytest.mark.asyncio
async def test_send_message_redacts_token_in_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            f"connection refused to https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage"
        )

    async with _mock_client(handler) as client:
        result = await send_message(client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x")

    assert result.ok is False
    assert result.error is not None
    assert _BOT_TOKEN not in result.error
