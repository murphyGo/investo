"""u95 runtime-budget tests for orchestrator stage-context loaders."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import httpx
import pytest

from investo.orchestrator import stage_context

_TARGET = date(2026, 4, 27)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, 8.0),
        ("0.25", 0.25),
        ("1", 1.0),
        ("0", 8.0),
        ("-1", 8.0),
        ("abc", 8.0),
    ],
)
def test_market_anchor_history_budget_env_parser(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    raw: str | None,
    expected: float,
) -> None:
    if raw is None:
        monkeypatch.delenv("INVESTO_MARKET_ANCHOR_HISTORY_BUDGET_S", raising=False)
    else:
        monkeypatch.setenv("INVESTO_MARKET_ANCHOR_HISTORY_BUDGET_S", raw)

    with caplog.at_level(logging.WARNING, logger="investo.orchestrator.stage_context"):
        assert stage_context._market_anchor_history_budget_from_env() == expected

    if raw not in {None, "0.25", "1"}:
        assert "INVESTO_MARKET_ANCHOR_HISTORY_BUDGET_S" in caplog.text


@pytest.mark.asyncio
async def test_load_market_anchors_times_out_to_empty_history(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("INVESTO_MARKET_ANCHOR_HISTORY_BUDGET_S", "0.01")

    async def _slow_fetch(client: httpx.AsyncClient) -> dict[str, Any]:
        del client
        await asyncio.sleep(1)
        return {}

    monkeypatch.setattr("investo.sources.yfinance_history.fetch_price_history", _slow_fetch)

    with caplog.at_level(logging.WARNING, logger="investo.orchestrator.stage_context"):
        anchors, history = await stage_context._load_market_anchors_for_run(_TARGET)

    assert anchors == {segment: () for segment in stage_context.SEGMENT_ORDER}
    assert history == {}
    assert "history fetch timed out" in caplog.text
