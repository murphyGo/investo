"""Integration smoke test — u4 notifier end-to-end.

Three pinning scenarios:

1. End-to-end public dispatch via :class:`BriefingPublisher`.
2. End-to-end operator dispatch via :class:`OperatorAlerter`.
3. Chat-ID separation invariant — when both classes share a bot
   token but receive disjoint chat IDs at construction time, each
   dispatch lands at its respective constructor parameter, NEVER
   cross-pollinating. This pins the dispatch-level half of CLAUDE
   .md project rule #5; the orchestrator-level half (the
   disjointness assertion) is u5's responsibility.

HTTP is mocked via ``httpx.MockTransport``; no real network access.
"""

from __future__ import annotations

import json as _json
from datetime import UTC, date, datetime

import httpx
import pytest

from investo.models import BriefingNotification, FailureContext
from investo.notifier import (
    BriefingPublisher,
    OperatorAlerter,
    build_summary,
)

_BOT_TOKEN = "1234567890:AAFakeBotTokenThatLooksLikeARealOneXYZ"
_PUBLIC_CHANNEL_ID = "@investo_briefing"
_OPERATOR_CHAT_ID = "987654321"
_TARGET_DATE = date(2026, 4, 25)
_SITE_URL = "https://example.github.io/investo/2026/04/2026-04-25/"


def _ok_response(message_id: int = 1) -> httpx.Response:
    return httpx.Response(200, json={"ok": True, "result": {"message_id": message_id}})


@pytest.mark.asyncio
async def test_briefing_publisher_end_to_end() -> None:
    """Construct → send → verify request shape + ok=True."""
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(_json.loads(request.content.decode("utf-8")))
        return _ok_response(message_id=42)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        publisher = BriefingPublisher(
            bot_token=_BOT_TOKEN,
            channel_id=_PUBLIC_CHANNEL_ID,
            http=http,
        )
        notification = BriefingNotification(
            target_date=_TARGET_DATE,
            summary_text="end-to-end summary",
            site_url=_SITE_URL,  # type: ignore[arg-type]
        )
        result = await publisher.send(notification)

    assert result.ok is True
    assert result.message_id == 42
    assert len(captured) == 1
    assert captured[0]["chat_id"] == _PUBLIC_CHANNEL_ID
    assert captured[0]["text"] == "end-to-end summary"


@pytest.mark.asyncio
async def test_operator_alerter_end_to_end() -> None:
    """Construct → alert → verify chat_id targets operator + alert
    text contains stage + error context.
    """
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(_json.loads(request.content.decode("utf-8")))
        return _ok_response(message_id=99)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        alerter = OperatorAlerter(
            bot_token=_BOT_TOKEN,
            operator_chat_id=_OPERATOR_CHAT_ID,
            http=http,
        )
        failure = FailureContext(
            stage="generate",
            error_type="BriefingGenerationError",
            error_message="synthesis failed after 3 attempts",
            traceback_excerpt=None,
            occurred_at=datetime(2026, 4, 25, 7, 0, tzinfo=UTC),
        )
        result = await alerter.alert(failure)

    assert result.ok is True
    assert result.message_id == 99
    assert len(captured) == 1
    assert captured[0]["chat_id"] == _OPERATOR_CHAT_ID
    text = str(captured[0]["text"])
    assert "Pipeline failure: generate" in text
    assert "BriefingGenerationError: synthesis failed after 3 attempts" in text


@pytest.mark.asyncio
async def test_chat_id_separation_invariant() -> None:
    """CLAUDE.md #5 dispatch-level pin: when both classes use the
    same bot token but disjoint chat IDs, each dispatch lands at its
    own constructor parameter. NEVER cross-pollinated.

    Same MockTransport handler captures both requests so we can
    inspect them side-by-side. The orchestrator-level disjointness
    assertion (`assert channel_id != operator_chat_id`) is u5's job;
    this pin verifies that GIVEN disjoint IDs, the dispatch respects
    them.
    """
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(_json.loads(request.content.decode("utf-8")))
        return _ok_response()

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        publisher = BriefingPublisher(
            bot_token=_BOT_TOKEN,
            channel_id=_PUBLIC_CHANNEL_ID,
            http=http,
        )
        alerter = OperatorAlerter(
            bot_token=_BOT_TOKEN,
            operator_chat_id=_OPERATOR_CHAT_ID,
            http=http,
        )

        notification = BriefingNotification(
            target_date=_TARGET_DATE,
            summary_text="pub",
            site_url=_SITE_URL,  # type: ignore[arg-type]
        )
        failure = FailureContext(
            stage="generate",
            error_type="X",
            error_message="y",
            traceback_excerpt=None,
            occurred_at=datetime(2026, 4, 25, 7, 0, tzinfo=UTC),
        )

        await publisher.send(notification)
        await alerter.alert(failure)

    assert len(captured) == 2
    # First call: publisher → public channel ID
    assert captured[0]["chat_id"] == _PUBLIC_CHANNEL_ID
    # Second call: alerter → operator chat ID
    assert captured[1]["chat_id"] == _OPERATOR_CHAT_ID
    # No cross-pollination: ID values are not swapped
    assert captured[0]["chat_id"] != captured[1]["chat_id"]


@pytest.mark.asyncio
async def test_public_surface_is_importable() -> None:
    """All 3 expected names resolve from ``investo.notifier``."""
    # Imports at top of file would have failed if any name were
    # missing — assertions below are documentation + grep-friendly.
    assert callable(BriefingPublisher)
    assert callable(OperatorAlerter)
    assert callable(build_summary)
