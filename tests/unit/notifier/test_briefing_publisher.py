"""Tests for ``investo.notifier.briefing_publisher.BriefingPublisher``.

Pins FR-004 + the kwargs-only construction (CLAUDE.md #5 anti-swap)
+ the chat_id dispatch isolation + non-raising contract.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import httpx
import pytest

from investo.models import BriefingNotification
from investo.notifier.briefing_publisher import BriefingPublisher
from tests.unit.notifier.conftest import mock_client

_BOT_TOKEN = "1234567890:AAFakeBotTokenThatLooksLikeARealOneXYZ"
_CHANNEL_ID = "@example_channel"
_TARGET_DATE = date(2026, 4, 25)
_SITE_URL = "https://example.github.io/investo/2026/04/2026-04-25/"


def _build_notification(text: str = "오늘의 시황 요약") -> BriefingNotification:
    return BriefingNotification(
        target_date=_TARGET_DATE,
        summary_text=text,
        site_url=_SITE_URL,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Construction — kwargs-only, no token leak
# ---------------------------------------------------------------------------


def test_briefing_publisher_construction_is_kwargs_only() -> None:
    """Positional construction must raise TypeError. Pinning the
    CLAUDE.md #5 anti-swap design: callers cannot accidentally pass
    ``operator_chat_id`` as ``channel_id`` positionally.
    """
    with pytest.raises(TypeError):
        BriefingPublisher(_BOT_TOKEN, _CHANNEL_ID)  # type: ignore[misc]


def test_briefing_publisher_does_not_leak_bot_token_in_repr() -> None:
    """Default ``object.__repr__`` shows the class name and id, not
    the field values. Confirms no `__repr__` override leaks the token.
    """
    publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_CHANNEL_ID)
    assert _BOT_TOKEN not in repr(publisher)


# ---------------------------------------------------------------------------
# Happy path — successful dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_briefing_publisher_send_returns_ok_on_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 99}})

    async with mock_client(handler) as http:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_CHANNEL_ID, http=http)
        result = await publisher.send(_build_notification())

    assert result.ok is True
    assert result.message_id == 99


@pytest.mark.asyncio
async def test_briefing_publisher_send_dispatches_to_channel_id() -> None:
    """The request body's `chat_id` matches the constructor's
    `channel_id`, NEVER any other value (CLAUDE.md #5 isolation).
    """
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode("utf-8"))
        captured.append(str(body["chat_id"]))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with mock_client(handler) as http:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_CHANNEL_ID, http=http)
        await publisher.send(_build_notification())

    assert captured == [_CHANNEL_ID]


@pytest.mark.asyncio
async def test_briefing_publisher_sends_summary_text_as_body() -> None:
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode("utf-8"))
        captured.append(str(body["text"]))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with mock_client(handler) as http:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_CHANNEL_ID, http=http)
        await publisher.send(_build_notification(text="bespoke summary"))

    assert captured == ["bespoke summary"]


# ---------------------------------------------------------------------------
# Failure modes — non-raising contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_briefing_publisher_handles_http_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic connect failure")

    async with mock_client(handler) as http:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_CHANNEL_ID, http=http)
        result = await publisher.send(_build_notification())

    assert result.ok is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_briefing_publisher_handles_telegram_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "description": "channel not found"})

    async with mock_client(handler) as http:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_CHANNEL_ID, http=http)
        result = await publisher.send(_build_notification())

    assert result.ok is False
    assert result.error is not None
    assert "channel not found" in result.error


@pytest.mark.asyncio
async def test_briefing_publisher_retries_markdown_parse_error_as_plain_text() -> None:
    captured_parse_modes: list[object] = []
    captured_texts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode("utf-8"))
        captured_parse_modes.append(body.get("parse_mode"))
        captured_texts.append(str(body["text"]))
        if len(captured_parse_modes) == 1:
            return httpx.Response(
                200,
                json={
                    "ok": False,
                    "description": "Bad Request: can't parse entities: unmatched marker",
                },
            )
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 77}})

    async with mock_client(handler) as http:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_CHANNEL_ID, http=http)
        result = await publisher.send(_build_notification(text="bad *markdown"))

    assert result.ok is True
    assert result.message_id == 77
    assert captured_parse_modes == ["Markdown", None]
    assert captured_texts == ["bad *markdown", "bad markdown"]


@pytest.mark.asyncio
async def test_briefing_publisher_does_not_retry_non_markdown_api_error() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200, json={"ok": False, "description": "channel not found"})

    async with mock_client(handler) as http:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_CHANNEL_ID, http=http)
        result = await publisher.send(_build_notification())

    assert result.ok is False
    assert result.error is not None
    assert "channel not found" in result.error
    assert request_count == 1


# ---------------------------------------------------------------------------
# Default httpx client created when http=None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_briefing_publisher_creates_default_client_when_http_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When constructed without an injected client, ``send`` creates an
    `httpx.AsyncClient` for the duration of the call. We monkeypatch
    `httpx.AsyncClient` to track the construction site.
    """
    from investo.notifier import briefing_publisher as bp_module

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
        )
    )
    async_client_factory = MagicMock(return_value=client)
    monkeypatch.setattr(bp_module.httpx, "AsyncClient", async_client_factory)

    publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_CHANNEL_ID, http=None)
    result = await publisher.send(_build_notification())

    assert result.ok is True
    async_client_factory.assert_called_once()
    # Production default has a 30s timeout.
    assert async_client_factory.call_args.kwargs["timeout"] == 30.0


# ---------------------------------------------------------------------------
# u31 Step 2 — dry-run mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_briefing_publisher_dry_run_returns_ok_without_dispatch() -> None:
    """dry_run=True returns ok=True without ever calling send_message.

    Constructed with ``http=None`` so any non-dry-run code path would
    instantiate a real httpx client; if dry-run leaked through, the
    request would either raise or trip the test's lack of monkeypatch.
    """
    publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_CHANNEL_ID, dry_run=True)
    result = await publisher.send(_build_notification())

    assert result.ok is True
    assert result.message_id is None
    assert result.error is None
