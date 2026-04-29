"""Tests for ``investo.notifier.briefing_publisher.BriefingPublisher``.

Pins FR-004 + the kwargs-only construction (CLAUDE.md #5 anti-swap)
+ the chat_id dispatch isolation + non-raising contract.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from investo.models import BriefingNotification
from investo.notifier.briefing_publisher import BriefingPublisher

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


def _mock_client(handler: object) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return httpx.AsyncClient(transport=transport)


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

    async with _mock_client(handler) as http:
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

    async with _mock_client(handler) as http:
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

    async with _mock_client(handler) as http:
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

    async with _mock_client(handler) as http:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_CHANNEL_ID, http=http)
        result = await publisher.send(_build_notification())

    assert result.ok is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_briefing_publisher_handles_telegram_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "description": "channel not found"})

    async with _mock_client(handler) as http:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_CHANNEL_ID, http=http)
        result = await publisher.send(_build_notification())

    assert result.ok is False
    assert result.error is not None
    assert "channel not found" in result.error


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

    construction_calls: list[dict[str, object]] = []
    real_client = httpx.AsyncClient

    class _TrackingClient(httpx.AsyncClient):
        def __init__(self, **kwargs: object) -> None:
            construction_calls.append(kwargs)
            # Inject a mock transport so the call doesn't hit the network.
            kwargs["transport"] = httpx.MockTransport(
                lambda req: httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
            )
            super().__init__(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(bp_module.httpx, "AsyncClient", _TrackingClient)

    publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_CHANNEL_ID, http=None)
    result = await publisher.send(_build_notification())

    assert result.ok is True
    assert len(construction_calls) == 1
    # Production default has a 30s timeout.
    assert construction_calls[0].get("timeout") == 30.0

    # Cleanup the monkeypatch reference.
    _ = real_client
