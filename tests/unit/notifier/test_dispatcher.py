"""Tests for ``investo.notifier._dispatcher`` (u80 shared dispatch).

Pins the three load-bearing behaviours of the shared, composition-based
dispatch helper:

1. markdown → plain-text fallback on a Telegram "can't parse entities"
   error (the single definition of the fallback, AC-80.2);
2. channel separation (R5) — each client passes its OWN chat id through
   ``dispatch``; the helper introduces no shared/default id;
3. ``parse_mode`` cannot be injected via ``send_kwargs`` (the helper
   owns it; passing it raises ``TypeError``).

HTTP is mocked via ``httpx.MockTransport`` — no real network access.
"""

from __future__ import annotations

import httpx
import pytest

from investo.notifier._dispatcher import dispatch
from tests.unit.notifier.conftest import mock_client

_BOT_TOKEN = "1234567890:AAFakeBotTokenThatLooksLikeARealOneXYZ"


# ---------------------------------------------------------------------------
# markdown → plain-text fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_retries_plain_text_on_markdown_parse_error() -> None:
    """First attempt (Markdown) gets a parse error; second (plain) succeeds."""
    sent: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        payload = json.loads(request.content)
        sent.append(payload)
        if payload.get("parse_mode") == "Markdown":
            return httpx.Response(
                200,
                json={"ok": False, "description": "Bad Request: can't parse entities"},
            )
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    async with mock_client(handler) as client:
        result = await dispatch(
            client,
            bot_token=_BOT_TOKEN,
            chat_id="@public_channel",
            text="*bold but broken",
            plain_text="bold but broken",
        )

    assert result.ok is True
    assert result.message_id == 7
    # Two attempts: Markdown first, then plain text with the fallback body.
    assert len(sent) == 2
    assert sent[0]["parse_mode"] == "Markdown"
    assert sent[0]["text"] == "*bold but broken"
    assert "parse_mode" not in sent[1]  # plain text → parse_mode omitted
    assert sent[1]["text"] == "bold but broken"


@pytest.mark.asyncio
async def test_dispatch_no_retry_on_success() -> None:
    sent: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with mock_client(handler) as client:
        result = await dispatch(
            client,
            bot_token=_BOT_TOKEN,
            chat_id="@public_channel",
            text="clean",
        )

    assert result.ok is True
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_dispatch_resends_same_text_when_no_plain_text_given() -> None:
    """The operator-alert case: fallback resends the same body, Markdown off."""
    sent: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        payload = json.loads(request.content)
        sent.append(payload)
        if payload.get("parse_mode") == "Markdown":
            return httpx.Response(
                200,
                json={"ok": False, "description": "can't parse entities at byte 3"},
            )
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 9}})

    async with mock_client(handler) as client:
        result = await dispatch(
            client,
            bot_token=_BOT_TOKEN,
            chat_id="123456:operator",
            text="alert body",
        )

    assert result.ok is True
    assert sent[1]["text"] == "alert body"


# ---------------------------------------------------------------------------
# channel separation (R5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_uses_caller_supplied_chat_id() -> None:
    """``dispatch`` routes to exactly the chat id the caller passes —
    no shared or default id is baked into the helper (R5)."""
    seen_chat_ids: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen_chat_ids.append(json.loads(request.content)["chat_id"])
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with mock_client(handler) as client:
        await dispatch(client, bot_token=_BOT_TOKEN, chat_id="@public_channel", text="a")
        await dispatch(client, bot_token=_BOT_TOKEN, chat_id="-100999:operator", text="b")

    assert seen_chat_ids == ["@public_channel", "-100999:operator"]


def test_dispatch_module_has_no_default_chat_id() -> None:
    """Guard against a regression that introduces a shared/default id."""
    import inspect

    from investo.notifier import _dispatcher

    sig = inspect.signature(_dispatcher.dispatch)
    chat_param = sig.parameters["chat_id"]
    # chat_id must be required (no default) so no caller can omit it and
    # silently fall back to a shared value.
    assert chat_param.default is inspect.Parameter.empty


# ---------------------------------------------------------------------------
# parse_mode is owned by dispatch (cannot be injected)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_rejects_parse_mode_in_send_kwargs() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with mock_client(handler) as client:
        with pytest.raises(TypeError, match="parse_mode"):
            await dispatch(
                client,
                bot_token=_BOT_TOKEN,
                chat_id="@public_channel",
                text="x",
                parse_mode="HTML",  # type: ignore[arg-type]
            )
