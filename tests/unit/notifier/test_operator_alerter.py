"""Tests for ``investo.notifier.operator_alerter.OperatorAlerter``.

Pins FR-007 + the kwargs-only construction (CLAUDE.md #5 anti-swap)
+ traceback embedding + bot-token redaction in alert text + UTF-16
truncation defense + the chat_id dispatch isolation.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from investo.models import FailureContext
from investo.notifier.operator_alerter import OperatorAlerter
from tests.unit.notifier.conftest import mock_client

_BOT_TOKEN = "1234567890:AAFakeBotTokenThatLooksLikeARealOneXYZ"
_OPERATOR_CHAT_ID = "123456789"


def _build_failure(
    *,
    stage: str = "generate",
    error_type: str = "BriefingGenerationError",
    error_message: str = "synthesis failed after 3 attempts",
    traceback_excerpt: str | None = None,
) -> FailureContext:
    return FailureContext(
        stage=stage,  # type: ignore[arg-type]
        error_type=error_type,
        error_message=error_message,
        traceback_excerpt=traceback_excerpt,
        occurred_at=datetime(2026, 4, 25, 7, 0, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_operator_alerter_construction_is_kwargs_only() -> None:
    """Positional ctor must raise. Anti-swap pin (CLAUDE.md #5)."""
    with pytest.raises(TypeError):
        OperatorAlerter(_BOT_TOKEN, _OPERATOR_CHAT_ID)  # type: ignore[misc]


def test_operator_alerter_does_not_leak_bot_token_in_repr() -> None:
    alerter = OperatorAlerter(bot_token=_BOT_TOKEN, operator_chat_id=_OPERATOR_CHAT_ID)
    assert _BOT_TOKEN not in repr(alerter)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_operator_alerter_sends_formatted_failure_text() -> None:
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode("utf-8"))
        captured.append(str(body["text"]))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with mock_client(handler) as http:
        alerter = OperatorAlerter(
            bot_token=_BOT_TOKEN, operator_chat_id=_OPERATOR_CHAT_ID, http=http
        )
        result = await alerter.alert(_build_failure())

    assert result.ok is True
    assert len(captured) == 1
    text = captured[0]
    assert "⚠️ Pipeline failure: generate" in text
    assert "BriefingGenerationError: synthesis failed after 3 attempts" in text
    assert "Occurred: 2026-04-25T07:00:00+00:00" in text


@pytest.mark.asyncio
async def test_operator_alerter_dispatches_to_operator_chat_id() -> None:
    """Chat_id matches operator_chat_id (CLAUDE.md #5 isolation)."""
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode("utf-8"))
        captured.append(str(body["chat_id"]))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with mock_client(handler) as http:
        alerter = OperatorAlerter(
            bot_token=_BOT_TOKEN, operator_chat_id=_OPERATOR_CHAT_ID, http=http
        )
        await alerter.alert(_build_failure())

    assert captured == [_OPERATOR_CHAT_ID]


# ---------------------------------------------------------------------------
# Traceback handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_operator_alerter_includes_traceback_in_code_fence() -> None:
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode("utf-8"))
        captured.append(str(body["text"]))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    tb = "Traceback (most recent call last):\n  File ..."
    async with mock_client(handler) as http:
        alerter = OperatorAlerter(
            bot_token=_BOT_TOKEN, operator_chat_id=_OPERATOR_CHAT_ID, http=http
        )
        await alerter.alert(_build_failure(traceback_excerpt=tb))

    text = captured[0]
    assert "```" in text
    assert tb in text


@pytest.mark.asyncio
async def test_operator_alerter_omits_traceback_when_none() -> None:
    """When `traceback_excerpt is None`, the alert has no stray
    triple-backticks / empty code fence.
    """
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode("utf-8"))
        captured.append(str(body["text"]))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with mock_client(handler) as http:
        alerter = OperatorAlerter(
            bot_token=_BOT_TOKEN, operator_chat_id=_OPERATOR_CHAT_ID, http=http
        )
        await alerter.alert(_build_failure(traceback_excerpt=None))

    assert "```" not in captured[0]


# ---------------------------------------------------------------------------
# Failure modes — non-raising
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_operator_alerter_handles_http_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic connect failure")

    async with mock_client(handler) as http:
        alerter = OperatorAlerter(
            bot_token=_BOT_TOKEN, operator_chat_id=_OPERATOR_CHAT_ID, http=http
        )
        result = await alerter.alert(_build_failure())

    assert result.ok is False
    assert result.error is not None


# ---------------------------------------------------------------------------
# Bot-token redaction in alert text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_operator_alerter_redacts_bot_token_from_error_message() -> None:
    """A `FailureContext.error_message` that accidentally embeds the
    bot token (poorly sanitized log line) → final alert text MUST
    NOT contain the token. Critical NFR-007 safety.
    """
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode("utf-8"))
        captured.append(str(body["text"]))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    leaky_message = f"failed to call https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage"
    async with mock_client(handler) as http:
        alerter = OperatorAlerter(
            bot_token=_BOT_TOKEN, operator_chat_id=_OPERATOR_CHAT_ID, http=http
        )
        await alerter.alert(_build_failure(error_message=leaky_message))

    text = captured[0]
    assert _BOT_TOKEN not in text
    assert "[REDACTED]" in text


# ---------------------------------------------------------------------------
# UTF-16 truncation defense
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_operator_alerter_truncates_long_alert_under_4096_units() -> None:
    """A pathologically long error_message + traceback that produces
    an alert text > 4096 UTF-16 units MUST be truncated before send.
    """
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode("utf-8"))
        captured.append(str(body["text"]))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    huge_message = "X" * 5000  # 5000 UTF-16 units of pure body
    huge_tb = "Y" * 1500  # leaves room over the 4096 cap

    async with mock_client(handler) as http:
        alerter = OperatorAlerter(
            bot_token=_BOT_TOKEN, operator_chat_id=_OPERATOR_CHAT_ID, http=http
        )
        await alerter.alert(_build_failure(error_message=huge_message, traceback_excerpt=huge_tb))

    text = captured[0]
    assert len(text.encode("utf-16-le")) // 2 <= 4096
    assert text.endswith("…")


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def test_operator_alerter_module_exports_expected_names() -> None:
    from investo.notifier import operator_alerter

    assert hasattr(operator_alerter, "OperatorAlerter")
