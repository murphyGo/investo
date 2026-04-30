"""Tests for ``investo.orchestrator.pipeline._stage_notify_briefing``.

Pins AC-003-6 (notify failure → SendResult(ok=False) returned, NO
operator alert at this layer; ``run_pipeline`` decides PARTIAL),
AC-003-8 (the SendResult round-trip the orchestrator depends on for
status taxonomy), and AC-005-5 + AC-005-6 (INFO on success / WARNING
on failure).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date

import httpx
import pytest
from pydantic import HttpUrl, TypeAdapter

from investo.briefing.disclaimer import DISCLAIMER
from investo.models import Briefing
from investo.notifier import BriefingPublisher
from investo.orchestrator.pipeline import _stage_notify_briefing

_TARGET = date(2026, 4, 25)
_PUBLIC_CHANNEL = "@example_channel"
_BOT_TOKEN = "1234567890:AAFakeBotTokenThatLooksLikeARealOneXYZ"
_SITE_URL_STR = "https://example.github.io/investo/2026/04/2026-04-25/"
_SITE_URL: HttpUrl = TypeAdapter(HttpUrl).validate_python(_SITE_URL_STR)


def _briefing() -> Briefing:
    body = (
        "오늘 시장 요약\n\n"
        "## ② 전일 핵심 이슈\n핵심 이슈\n\n"
        "## ③ 섹터/수급 동향\n섹터\n\n"
        "## ④ 지표·이벤트\n지표\n\n"
        "## ⑤ 주요 종목\n종목\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전\n\n" + DISCLAIMER
    )
    return Briefing(
        target_date=_TARGET,
        market_summary="오늘 시장 요약",
        key_issues="핵심 이슈",
        sector_flow="섹터",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer=DISCLAIMER,
        rendered_markdown="## ① 요약\n" + body,
    )


@asynccontextmanager
async def _mock_client(handler: object) -> AsyncIterator[httpx.AsyncClient]:
    """Build an httpx.AsyncClient backed by ``MockTransport(handler)``."""
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport) as client:
        yield client


# ---------------------------------------------------------------------------
# Happy path — Telegram returns 200 + ok:true
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_notify_briefing_returns_send_result_on_success() -> None:
    """End-to-end happy path: SendResult(ok=True, message_id=...)."""

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 99}})

    async with _mock_client(_handler) as client:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_PUBLIC_CHANNEL, http=client)
        result = await _stage_notify_briefing(_briefing(), publisher=publisher, site_url=_SITE_URL)

    assert result.ok is True
    assert result.message_id == 99
    assert result.error is None


@pytest.mark.asyncio
async def test_stage_notify_briefing_request_targets_public_channel() -> None:
    """The request body's ``chat_id`` matches the publisher's channel —
    pins that ``_stage_notify_briefing`` does not somehow re-route to a
    different ID. CLAUDE.md #5 chat-isolation safety net at the stage
    layer (orchestrator already enforces disjointness in main()).
    """
    captured: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured.update(_json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with _mock_client(_handler) as client:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_PUBLIC_CHANNEL, http=client)
        await _stage_notify_briefing(_briefing(), publisher=publisher, site_url=_SITE_URL)

    assert captured["chat_id"] == _PUBLIC_CHANNEL


@pytest.mark.asyncio
async def test_stage_notify_briefing_request_text_is_built_summary() -> None:
    """The request body's ``text`` matches what ``build_summary`` would
    have produced — pins the orchestrator's composition path
    (build_summary → BriefingNotification → publisher.send) without
    re-asserting the full summary content (already covered in
    ``test_summary.py``).
    """
    captured: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured.update(_json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with _mock_client(_handler) as client:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_PUBLIC_CHANNEL, http=client)
        await _stage_notify_briefing(_briefing(), publisher=publisher, site_url=_SITE_URL)

    text = captured["text"]
    assert isinstance(text, str)
    assert "2026-04-25" in text  # date header
    assert "오늘 시장 요약" in text  # market summary body
    assert _SITE_URL_STR in text  # footer URL preserved


# ---------------------------------------------------------------------------
# AC-003-6 / AC-003-8 — failure returns SendResult(ok=False), NEVER raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_notify_briefing_returns_failure_send_result_on_telegram_api_error() -> None:
    """Telegram returned ``{"ok": false, ...}`` — u4 surfaces this as
    SendResult(ok=False, error=...). ``_stage_notify_briefing`` must
    forward it without raising so ``run_pipeline`` can mark PARTIAL.
    """

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "description": "channel not found"})

    async with _mock_client(_handler) as client:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_PUBLIC_CHANNEL, http=client)
        # MUST NOT raise.
        result = await _stage_notify_briefing(_briefing(), publisher=publisher, site_url=_SITE_URL)

    assert result.ok is False
    assert result.message_id is None
    assert result.error is not None
    assert "channel not found" in result.error


@pytest.mark.asyncio
async def test_stage_notify_briefing_returns_failure_on_http_transport_error() -> None:
    """HTTP transport failure (connect refused, timeout, etc.) →
    SendResult(ok=False); orchestrator does not raise.
    """

    def _handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic connect failure")

    async with _mock_client(_handler) as client:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_PUBLIC_CHANNEL, http=client)
        result = await _stage_notify_briefing(_briefing(), publisher=publisher, site_url=_SITE_URL)

    assert result.ok is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_stage_notify_briefing_does_not_swallow_programmer_errors() -> None:
    """If the ``BriefingPublisher.send`` somehow raises an unexpected
    exception (programmer error rather than transport failure), it
    propagates. u4's contract says it doesn't raise on HTTP failure,
    but a malformed ``BriefingPublisher`` (e.g., a test stub with a
    bug) might raise — the orchestrator must NOT silently swallow
    such bugs.
    """

    class _BrokenPublisher:
        async def send(self, payload: object) -> object:
            raise RuntimeError("publisher bug")

    with pytest.raises(RuntimeError, match="publisher bug"):
        await _stage_notify_briefing(
            _briefing(),
            publisher=_BrokenPublisher(),  # type: ignore[arg-type]
            site_url=_SITE_URL,
        )


# ---------------------------------------------------------------------------
# AC-005-5 / AC-005-6 — INFO on success, WARNING on failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_notify_briefing_logs_info_on_success(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    async with _mock_client(_handler) as client:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_PUBLIC_CHANNEL, http=client)
        with caplog.at_level(logging.DEBUG, logger="investo.orchestrator.pipeline"):
            await _stage_notify_briefing(_briefing(), publisher=publisher, site_url=_SITE_URL)

    pipeline_records = [r for r in caplog.records if r.name == "investo.orchestrator.pipeline"]
    info_msgs = [r.getMessage() for r in pipeline_records if r.levelno == logging.INFO]
    assert any("[notify_briefing] starting" in m for m in info_msgs)
    # Success path includes the message_id in the log line.
    assert any("[notify_briefing] ok" in m and "message_id=7" in m for m in info_msgs)
    # No WARNING records on success.
    assert not [r for r in pipeline_records if r.levelno == logging.WARNING]


@pytest.mark.asyncio
async def test_stage_notify_briefing_logs_warning_on_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC-005-6: notify failure logs at WARNING (NOT ERROR — failure
    here is non-fatal; pipeline continues to PARTIAL).
    """

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "description": "rate limited"})

    async with _mock_client(_handler) as client:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_PUBLIC_CHANNEL, http=client)
        with caplog.at_level(logging.DEBUG, logger="investo.orchestrator.pipeline"):
            await _stage_notify_briefing(_briefing(), publisher=publisher, site_url=_SITE_URL)

    warning_msgs = [
        r.getMessage()
        for r in caplog.records
        if r.name == "investo.orchestrator.pipeline" and r.levelno == logging.WARNING
    ]
    assert any("[notify_briefing] failed" in m for m in warning_msgs)
    assert any("rate limited" in m for m in warning_msgs)


# ---------------------------------------------------------------------------
# Site URL flows through both build_summary and BriefingNotification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_notify_briefing_site_url_appears_in_summary_text() -> None:
    """The ``site_url`` is threaded through ``build_summary`` (footer)
    AND ``BriefingNotification`` (model field). Verify both paths
    landed correctly via the request body.
    """
    captured_text: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode("utf-8"))
        captured_text.append(body["text"])
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with _mock_client(_handler) as client:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_PUBLIC_CHANNEL, http=client)
        await _stage_notify_briefing(_briefing(), publisher=publisher, site_url=_SITE_URL)

    assert len(captured_text) == 1
    assert _SITE_URL_STR in captured_text[0]
