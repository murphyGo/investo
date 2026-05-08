"""Tests for ``investo.notifier._telegram`` HTTP helper.

Pins the non-raising contract + bot-token redaction (NFR-007).
HTTP is mocked via ``httpx.MockTransport``; no real network access.
"""

from __future__ import annotations

import httpx
import pytest

from investo.notifier._telegram import (
    _redact_bot_token,
    send_message,
    telegram_api_url,
)
from tests.unit.notifier.conftest import mock_client

# A realistic-looking bot token for redaction tests.
_BOT_TOKEN = "1234567890:AAFakeBotTokenThatLooksLikeARealOneXYZ"
_CHAT_ID = "@example_channel"

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

    async with mock_client(handler) as client:
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

    async with mock_client(handler) as client:
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
async def test_send_message_omits_parse_mode_when_none() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured.update(_json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with mock_client(handler) as client:
        await send_message(
            client,
            bot_token=_BOT_TOKEN,
            chat_id=_CHAT_ID,
            text="plain text",
            parse_mode=None,
        )

    assert "parse_mode" not in captured


@pytest.mark.asyncio
async def test_send_message_request_url_targets_bot_token_endpoint() -> None:
    captured_url: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_url.append(str(request.url))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with mock_client(handler) as client:
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

    async with mock_client(handler) as client:
        result = await send_message(client, bot_token=_BOT_TOKEN, chat_id="bad", text="x")

    assert result.ok is False
    assert result.message_id is None
    assert result.error is not None
    assert "chat not found" in result.error


@pytest.mark.asyncio
async def test_send_message_handles_non_200_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Too Many Requests")

    async with mock_client(handler) as client:
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

    async with mock_client(handler) as client:
        result = await send_message(client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x")

    assert result.ok is False
    assert result.error is not None
    assert "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_send_message_handles_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic connect failure")

    async with mock_client(handler) as client:
        result = await send_message(client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x")

    assert result.ok is False
    assert result.error is not None
    assert "http error" in result.error.lower() or "connect" in result.error.lower()


@pytest.mark.asyncio
async def test_send_message_handles_invalid_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>500 internal</html>")

    async with mock_client(handler) as client:
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
    # u27 M1: redaction now delegates to the project chokepoint, which
    # replaces the token shape with the named marker
    # ``[REDACTED_BOT_TOKEN]``. The surrounding ``/bot`` / ``/sendMessage``
    # path segments are preserved (only the token portion is rewritten).
    assert "/bot[REDACTED_BOT_TOKEN]/sendMessage" in redacted


def test_redact_bot_token_handles_multiple_occurrences() -> None:
    leaked = (
        f"first https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage "
        f"second https://api.telegram.org/bot{_BOT_TOKEN}/getUpdates"
    )
    redacted = _redact_bot_token(leaked)
    assert _BOT_TOKEN not in redacted
    # Both occurrences rewritten by the chokepoint.
    assert redacted.count("[REDACTED_BOT_TOKEN]") == 2


def test_redact_bot_token_passthrough_when_no_token() -> None:
    plain = "no token in this string"
    assert _redact_bot_token(plain) == plain


def test_redact_bot_token_catches_bare_shape_without_leading_slash() -> None:
    """Step 7 sub-agent review M1 — a hand-crafted log line like
    ``"used token bot{TOKEN}"`` (no ``/`` prefix) MUST also be
    redacted via the shape pattern. Token shape:
    ``<digits>:<≥20 alphanumeric/underscore/dash>``. u27 M1: the
    chokepoint emits the named marker ``[REDACTED_BOT_TOKEN]``.
    """
    leaked = f"used token bot{_BOT_TOKEN}"
    redacted = _redact_bot_token(leaked)
    assert _BOT_TOKEN not in redacted
    assert "[REDACTED_BOT_TOKEN]" in redacted


def test_redact_bot_token_does_not_false_positive_on_botany() -> None:
    """The chokepoint's bot-token regex requires ``\\d{6,}:`` plus a
    tail of ≥20 alphanumeric/underscore/dash chars — words starting
    with ``bot`` like ``botany`` or ``robot:foo`` are NOT matched.
    """
    plain = "botany analyzed at robot.local"
    assert _redact_bot_token(plain) == plain
    # Short tails are also passed through.
    plain2 = "bot123:short"
    assert _redact_bot_token(plain2) == plain2


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

    async with mock_client(handler) as client:
        result = await send_message(client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x")

    assert result.ok is False
    assert result.error is not None
    assert _BOT_TOKEN not in result.error
    # u27 M1: chokepoint marker is ``[REDACTED_BOT_TOKEN]``.
    assert "[REDACTED_BOT_TOKEN]" in result.error


@pytest.mark.asyncio
async def test_send_message_redacts_token_in_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            f"connection refused to https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage"
        )

    async with mock_client(handler) as client:
        result = await send_message(client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x")

    assert result.ok is False
    assert result.error is not None
    assert _BOT_TOKEN not in result.error


# ---------------------------------------------------------------------------
# u31 Step 1 — bounded retry policy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_retries_on_429_and_honors_retry_after_header() -> None:
    """HTTP 429 with ``Retry-After`` header → wait then retry; recover on 2nd attempt."""
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "5"}, text="too many requests")
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    async with mock_client(handler) as client:
        result = await send_message(
            client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x", sleep=fake_sleep
        )

    assert result.ok is True
    assert result.message_id == 7
    # Backoff for 2nd attempt is at least the Retry-After header value.
    assert sleeps and sleeps[0] >= 5.0


@pytest.mark.asyncio
async def test_send_message_retries_on_429_and_honors_retry_after_json_body() -> None:
    """``parameters.retry_after`` JSON field is honored too."""
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(
                429,
                json={
                    "ok": False,
                    "error_code": 429,
                    "description": "Too Many Requests",
                    "parameters": {"retry_after": 3},
                },
            )
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 9}})

    async with mock_client(handler) as client:
        result = await send_message(
            client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x", sleep=fake_sleep
        )

    assert result.ok is True
    assert sleeps and sleeps[0] >= 3.0


@pytest.mark.asyncio
async def test_send_message_retries_on_5xx() -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(503, text="service unavailable")
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with mock_client(handler) as client:
        result = await send_message(
            client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x", sleep=fake_sleep
        )

    assert result.ok is True
    assert len(sleeps) == 2  # two backoffs before the 3rd successful attempt


@pytest.mark.asyncio
async def test_send_message_does_not_retry_on_non_transient_4xx() -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(400, text="bad request")

    async with mock_client(handler) as client:
        result = await send_message(
            client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x", sleep=fake_sleep
        )

    assert result.ok is False
    assert attempts["count"] == 1  # no retry
    assert sleeps == []


@pytest.mark.asyncio
async def test_send_message_retry_after_is_capped() -> None:
    """A hostile server sending Retry-After: 999999 must not hang the cron."""
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "999999"}, text="x")
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with mock_client(handler) as client:
        result = await send_message(
            client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x", sleep=fake_sleep
        )

    assert result.ok is True
    # Cap at 30 seconds — the module's _RETRY_AFTER_CEILING_S.
    assert sleeps and sleeps[0] <= 30.0


@pytest.mark.asyncio
async def test_send_message_respects_global_retry_budget(monkeypatch) -> None:
    """When the process-wide retry budget is exhausted, the Telegram retry
    loop stops even if its own local quota still has slack.
    """
    from investo._internal import retry_budget

    retry_budget.reset_budget()
    monkeypatch.setenv("INVESTO_RETRY_BUDGET", "0")
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(503, text="service unavailable")

    async with mock_client(handler) as client:
        result = await send_message(
            client, bot_token=_BOT_TOKEN, chat_id=_CHAT_ID, text="x", sleep=fake_sleep
        )

    assert result.ok is False
    # Budget=0 means the loop runs once and skips every retry.
    assert attempts["count"] == 1
    assert sleeps == []
    retry_budget.reset_budget()
