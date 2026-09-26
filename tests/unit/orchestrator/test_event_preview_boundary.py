"""Code-ready preview must still be rejected by every public entrypoint."""

from __future__ import annotations

from datetime import date
from typing import Never, cast
from unittest.mock import Mock

import pytest
from pydantic import HttpUrl, TypeAdapter

import investo.__main__ as main_module
from investo._internal.llm_config import LlmExecutionConfig
from investo.models.event_config import EventExecutionConfig
from investo.notifier import BriefingPublisher, OperatorAlerter
from investo.orchestrator.pipeline import run_pipeline


def _forbidden(*args: object, **kwargs: object) -> Never:
    pytest.fail("public preview reached a side-effect boundary")


@pytest.mark.parametrize("capability_ready", [False, True])
async def test_public_pipeline_rejects_preview_before_stages_or_io(
    monkeypatch: pytest.MonkeyPatch, capability_ready: bool
) -> None:
    monkeypatch.setattr("investo.models.event_config.EVENT_PREVIEW_READY", capability_ready)
    monkeypatch.setattr("investo.orchestrator.pipeline.build_default_stages", _forbidden)
    monkeypatch.setattr("investo.orchestrator.pipeline.temporary_artifact_staging_root", _forbidden)
    publisher = Mock(spec=BriefingPublisher)
    alerter = Mock(spec=OperatorAlerter)
    with pytest.raises(ValueError, match="isolated non-public preview"):
        await run_pipeline(
            date(2026, 9, 21),
            publisher=cast(BriefingPublisher, publisher),
            alerter=cast(OperatorAlerter, alerter),
            site_url_base=TypeAdapter(HttpUrl).validate_python("https://example.invalid/investo"),
            fetch=_forbidden,
            runner=_forbidden,
            git_runner=_forbidden,
            event_config=EventExecutionConfig("preview"),
        )
    assert publisher.mock_calls == []
    assert alerter.mock_calls == []


async def test_public_main_rejects_ready_preview_before_http_or_pipeline(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr("investo.models.event_config.EVENT_PREVIEW_READY", True)
    for key, value in {
        "CLAUDE_CODE_OAUTH_TOKEN": "synthetic-claude-oauth",
        "TELEGRAM_BOT_TOKEN": "1234567890:AAFakeBotTokenThatLooksLikeARealOneXYZ",
        "TELEGRAM_BRIEFING_CHANNEL_ID": "@example_public_channel",
        "TELEGRAM_OPERATOR_CHAT_ID": "12345678",
        "SITE_URL_BASE": "https://example.invalid/investo",
        "INVESTO_EVENT_BRIEFING_MODE": "preview",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("INVESTO_TARGET_DATE", raising=False)
    monkeypatch.setattr("investo.__main__.httpx.AsyncClient", _forbidden)
    monkeypatch.setattr(main_module, "BriefingPublisher", _forbidden)
    monkeypatch.setattr(main_module, "OperatorAlerter", _forbidden)
    monkeypatch.setattr(main_module, "run_pipeline", _forbidden)
    monkeypatch.setattr(main_module, "_attempt_boot_alert", _forbidden)
    assert await main_module._async_main(llm_config=LlmExecutionConfig()) == 1
    assert "isolated non-public preview" in caplog.text
