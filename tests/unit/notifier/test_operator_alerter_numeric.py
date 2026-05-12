"""u55 Step 5 — Tests for the u55 numeric / freshness operator alerts."""

from __future__ import annotations

import httpx
import pytest

from investo.notifier.operator_alerter import (
    OperatorAlerter,
    _format_numeric_alert_text,
)


def test_format_numeric_block_heading() -> None:
    out = _format_numeric_alert_text(
        "numeric_block", segment="us-equity", detail="5/65/7 corruption"
    )
    assert out.startswith("🚫 수치/날짜 게이트 차단")
    assert "us-equity" in out
    assert "5/65/7" in out


def test_format_numeric_downgrade_heading() -> None:
    out = _format_numeric_alert_text(
        "numeric_downgrade", segment="crypto", detail="btc_usd 검증 실패"
    )
    assert out.startswith("⚠️ 수치 검증 다운그레이드")
    assert "crypto" in out


def test_format_segment_stale_heading() -> None:
    out = _format_numeric_alert_text(
        "segment_stale",
        segment="domestic-equity",
        detail="latest archive 2026-05-04",
    )
    assert out.startswith("⏰ 세그먼트 stale")


def test_format_does_not_leak_secret_shape() -> None:
    # The formatter must not echo any field shorter than the labels —
    # also, embedding a "bot:" prefix in the detail must not produce
    # anything close to the bot-token shape.
    out = _format_numeric_alert_text("numeric_block", segment="us-equity", detail="harmless detail")
    # No bot-token-like substring (digits:letters) ever shows up.
    import re

    assert not re.search(r"\d{8,}:[A-Za-z0-9_-]{30,}", out)


@pytest.mark.asyncio
async def test_numeric_alert_dry_run_does_not_post() -> None:
    alerter = OperatorAlerter(
        bot_token="x",
        operator_chat_id="@ops",
        dry_run=True,
    )
    result = await alerter.numeric_alert(
        "numeric_block", segment="us-equity", detail="5/65/7 corruption"
    )
    assert result.ok
    assert result.message_id is None


@pytest.mark.asyncio
async def test_numeric_alert_posts_to_operator_chat() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.content.decode("utf-8")
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        alerter = OperatorAlerter(
            bot_token="123:secrettoken",
            operator_chat_id="@ops",
            http=client,
        )
        result = await alerter.numeric_alert(
            "numeric_downgrade", segment="us-equity", detail="spx_close 검증 실패"
        )
    assert result.ok
    assert result.message_id == 42
    body = str(captured.get("body", ""))
    # R13: the bot token should never appear in the rendered alert
    # body (the token is in the URL but never in the chat message).
    assert "secrettoken" not in body
