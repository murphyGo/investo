"""u43 — orchestrator wire-through for the lookahead bucket + clock.

Pins DEBT-067 sub-bullets M1 (clock-explicit) and M3 (single-filter
reuse) at the stage helper level, so a refactor that moves the clock
back into the notifier or that introduces a second filter site for
``scheduled_at`` breaks here rather than at code-review time.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest
from pydantic import HttpUrl, TypeAdapter

from investo.briefing.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
    filter_lookahead_items,
)
from investo.models import NormalizedItem, PublicNotificationSummary
from investo.notifier import BriefingPublisher
from investo.orchestrator.pipeline import _stage_notify_segmented_briefing

_TARGET = date(2026, 4, 25)
_PUBLIC_CHANNEL = "@example_channel"
_BOT_TOKEN = "1234567890:AAFakeBotTokenThatLooksLikeARealOneXYZ"
_TYPED_URL = TypeAdapter(HttpUrl)
_SEGMENT_URLS: dict[MarketSegment, HttpUrl] = {
    DOMESTIC_EQUITY: _TYPED_URL.validate_python(
        "https://example.github.io/investo/archive/domestic-equity/2026/04/2026-04-25/"
    ),
    US_EQUITY: _TYPED_URL.validate_python(
        "https://example.github.io/investo/archive/us-equity/2026/04/2026-04-25/"
    ),
    CRYPTO: _TYPED_URL.validate_python(
        "https://example.github.io/investo/archive/crypto/2026/04/2026-04-25/"
    ),
}


def _summary(segment: MarketSegment, label: str) -> PublicNotificationSummary:
    return PublicNotificationSummary(
        segment=segment,
        target_date=_TARGET,
        conclusion=f"{label} 한 줄.",
        coverage_status="normal",
        coverage_label="정상",
    )


def _summaries() -> dict[MarketSegment, PublicNotificationSummary]:
    return {
        DOMESTIC_EQUITY: _summary(DOMESTIC_EQUITY, "국내"),
        US_EQUITY: _summary(US_EQUITY, "미국"),
        CRYPTO: _summary(CRYPTO, "크립토"),
    }


def _fomc_lookahead_item(scheduled_at: datetime) -> NormalizedItem:
    return NormalizedItem(
        source_name="fomc-calendar",
        category="calendar",
        title=f"{scheduled_at.date().isoformat()} — FOMC Press Conference",
        published_at=datetime(2026, 4, 25, tzinfo=UTC),
        scheduled_at=scheduled_at,
        raw_metadata={"event_type": "FOMC", "scheduled_date": scheduled_at.date().isoformat()},
    )


@asynccontextmanager
async def _mock_client(handler: Any) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        yield client


@pytest.mark.asyncio
async def test_stage_passes_lookahead_and_now_utc_to_summary_builder() -> None:
    """Imminent-tag round-trip: a 2-day-out FOMC item ends up tagged
    in the request body the publisher dispatches.
    """
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured.update(_json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    now_utc = datetime(2026, 4, 25, 12, 0, tzinfo=UTC)
    fomc_item = _fomc_lookahead_item(datetime(2026, 4, 27, 18, 0, tzinfo=UTC))

    async with _mock_client(handler) as client:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_PUBLIC_CHANNEL, http=client)
        result = await _stage_notify_segmented_briefing(
            _summaries(),
            publisher=publisher,
            site_urls=_SEGMENT_URLS,
            items=(fomc_item,),
            lookahead_items_by_segment={US_EQUITY: (fomc_item,)},
            now_utc=now_utc,
        )

    assert result.ok is True
    text = captured.get("text")
    assert isinstance(text, str)
    # The deterministic D-2 imminent tag landed on the us-equity line.
    assert "D-2" in text
    assert "📅" in text  # calendar icon for non-earnings sources


@pytest.mark.asyncio
async def test_stage_returns_failure_send_result_when_clock_invariant_violated() -> None:
    """The notifier's M1 invariant raises ``ValueError`` when
    ``lookahead_items_by_segment`` is supplied while ``now_utc`` is
    ``None``. The stage helper catches ``ValueError`` and returns a
    failed ``SendResult`` (preserves the existing failure-isolation
    contract — the notify stage never raises out of the orchestrator).
    """
    fomc_item = _fomc_lookahead_item(datetime(2026, 4, 27, 18, 0, tzinfo=UTC))

    async def never_called(request: httpx.Request) -> httpx.Response:
        raise AssertionError("publisher must not be called when summary build fails")

    async with _mock_client(never_called) as client:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_PUBLIC_CHANNEL, http=client)
        result = await _stage_notify_segmented_briefing(
            _summaries(),
            publisher=publisher,
            site_urls=_SEGMENT_URLS,
            items=(fomc_item,),
            lookahead_items_by_segment={US_EQUITY: (fomc_item,)},
            now_utc=None,
        )

    assert result.ok is False
    assert result.error is not None
    assert "now_utc required" in result.error


@pytest.mark.asyncio
async def test_stage_omits_imminent_tag_when_no_lookahead_supplied() -> None:
    """Backward-compat: callers that don't pass the lookahead bucket
    get the legacy line shape — no D-N tag injected.
    """
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured.update(_json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 2}})

    async with _mock_client(handler) as client:
        publisher = BriefingPublisher(bot_token=_BOT_TOKEN, channel_id=_PUBLIC_CHANNEL, http=client)
        result = await _stage_notify_segmented_briefing(
            _summaries(),
            publisher=publisher,
            site_urls=_SEGMENT_URLS,
        )

    assert result.ok is True
    text = captured.get("text")
    assert isinstance(text, str)
    assert " D-" not in text


def test_filter_lookahead_items_is_chokepoint_for_forward_filtering() -> None:
    """M3 contract: the orchestrator and briefing pipeline both go
    through ``filter_lookahead_items`` for the "what counts as forward"
    decision. Pin that the helper returns exactly the items where
    ``scheduled_at is not None`` (and nothing else, so a future widening
    that adds another criterion lands here, not in two sites).
    """
    backward = NormalizedItem(
        source_name="cnbc-top-news",
        category="news",
        title="Backward news",
        published_at=datetime(2026, 4, 25, tzinfo=UTC),
    )
    forward = _fomc_lookahead_item(datetime(2026, 4, 28, tzinfo=UTC))

    result = filter_lookahead_items([backward, forward])

    assert result == (forward,)


def test_orchestrator_imports_single_filter_helper() -> None:
    """Anti-regression: the orchestrator must import
    ``filter_lookahead_items`` from ``briefing.segments`` rather than
    re-implementing the ``scheduled_at is not None`` predicate inline.
    Pins DEBT-067 M3 at the import-graph level.
    """
    from pathlib import Path

    src = (
        Path(
            __file__,
        )
        .resolve()
        .parent.parent.parent.parent
        / "src"
        / "investo"
        / "orchestrator"
        / "pipeline.py"
    )
    text = src.read_text(encoding="utf-8")
    assert "filter_lookahead_items" in text
    # The orchestrator must NOT carry an inline duplicate of the predicate.
    # Allow the helper itself; reject any other ``scheduled_at is not None``
    # comprehension/expression in the orchestrator module.
    bad_count = text.count("scheduled_at is not None")
    assert bad_count == 0, (
        f"orchestrator must reuse filter_lookahead_items, found "
        f"{bad_count} inline occurrences of 'scheduled_at is not None'"
    )
