"""Tests for ``investo.orchestrator.pipeline._stage_collect``.

Pins AC-003-1 (per-source failure already swallowed at u1's
aggregator boundary), AC-003-2 (empty collect → EmptyCollectError),
and AC-005-5 (INFO log on stage entry/exit).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime

import pytest

from investo.models import NormalizedItem
from investo.orchestrator.errors import EmptyCollectError
from investo.orchestrator.pipeline import _stage_collect

_TARGET = date(2026, 4, 25)


def _item(title: str = "x") -> NormalizedItem:
    """Minimal valid NormalizedItem for tests."""
    return NormalizedItem(
        source_name="fake-src",
        category="news",
        title=title,
        published_at=datetime(2026, 4, 25, 12, 0, tzinfo=UTC),
    )


def _make_fetch(
    items: list[NormalizedItem],
) -> Callable[[date], Awaitable[list[NormalizedItem]]]:
    """Build a fake aggregator returning ``items`` when awaited."""

    async def _fake(target_date: date) -> list[NormalizedItem]:
        assert target_date == _TARGET
        return items

    return _fake


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_collect_returns_items_from_aggregator() -> None:
    """Happy path — fake aggregator returns 3 items; ``_stage_collect``
    forwards them. The legacy items-only ``fetch=`` test seam yields
    empty per-source outcomes (the u22 transparency surface only
    populates when the production ``collect_sources`` path runs).
    """
    items = [_item("a"), _item("b"), _item("c")]
    result_items, outcomes = await _stage_collect(_TARGET, fetch=_make_fetch(items))
    assert result_items == items
    assert len(result_items) == 3
    assert outcomes == ()


@pytest.mark.asyncio
async def test_stage_collect_passes_target_date_through() -> None:
    """Forwarded ``target_date`` lands at the aggregator unchanged —
    asserted inside ``_make_fetch``'s body.
    """
    captured: list[date] = []

    async def _capturing_fetch(target_date: date) -> list[NormalizedItem]:
        captured.append(target_date)
        return [_item()]

    await _stage_collect(_TARGET, fetch=_capturing_fetch)
    assert captured == [_TARGET]


@pytest.mark.asyncio
async def test_stage_collect_partial_aggregator_result_returns_remaining() -> None:
    """AC-003-1 — per-source failure is already swallowed inside u1's
    aggregator (returns the union of successful sources). The
    orchestrator-side stage runner sees a non-empty list with the
    remaining items and proceeds normally; no error is raised.
    """
    # Simulate "3 sources registered, 2 succeeded, 1 failed and got
    # swallowed" by returning only 2 items.
    items = [_item("survivor-1"), _item("survivor-2")]
    result_items, _outcomes = await _stage_collect(_TARGET, fetch=_make_fetch(items))
    assert len(result_items) == 2


# ---------------------------------------------------------------------------
# AC-003-2 — empty collect raises EmptyCollectError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_collect_empty_result_raises_empty_collect_error() -> None:
    """Aggregator returned ``[]`` → orchestrator raises
    ``EmptyCollectError`` so ``run_pipeline`` can route to operator
    alert.
    """
    with pytest.raises(EmptyCollectError, match="0 items"):
        await _stage_collect(_TARGET, fetch=_make_fetch([]))


@pytest.mark.asyncio
async def test_stage_collect_empty_collect_error_message_includes_target_date() -> None:
    """The error message embeds ``target_date`` so logs / alerts have
    enough context without requiring a separate ``FailureContext``
    field at the raise site.
    """
    try:
        await _stage_collect(_TARGET, fetch=_make_fetch([]))
        pytest.fail("expected EmptyCollectError")
    except EmptyCollectError as caught:
        assert "2026-04-25" in str(caught)


# ---------------------------------------------------------------------------
# AC-005-5 — INFO logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_collect_logs_info_on_entry_and_exit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Per AC-005-5: stage entry/exit emits INFO under
    ``investo.orchestrator.pipeline``.
    """
    items = [_item("one"), _item("two")]
    with caplog.at_level(logging.INFO, logger="investo.orchestrator.pipeline"):
        await _stage_collect(_TARGET, fetch=_make_fetch(items))

    # Two INFO records: starting + returned.
    info_records = [r for r in caplog.records if r.name == "investo.orchestrator.pipeline"]
    assert any("[collect] starting" in r.message for r in info_records)
    assert any(
        "[collect] returned 2 items" in r.message or "returned 2" in r.getMessage()
        for r in info_records
    )


@pytest.mark.asyncio
async def test_stage_collect_logs_info_even_on_empty_result(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Empty collect still logs the "returned 0 items" line BEFORE
    raising — operators want to see the count in GHA logs even on
    failure.
    """
    with (
        caplog.at_level(logging.INFO, logger="investo.orchestrator.pipeline"),
        pytest.raises(EmptyCollectError),
    ):
        await _stage_collect(_TARGET, fetch=_make_fetch([]))

    info_records = [r for r in caplog.records if r.name == "investo.orchestrator.pipeline"]
    assert any("[collect] returned 0 items" in r.message for r in info_records)


# ---------------------------------------------------------------------------
# Default-aggregator wiring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_collect_default_fetch_is_real_aggregator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``fetch=None`` (production path), ``_stage_collect`` calls
    ``investo.sources.collect_sources``. Verify by monkeypatching that
    binding inside the pipeline module and confirming it's invoked.
    The u22 collect_sources contract returns a SourceCollectionReport
    so the spy mirrors that shape.
    """
    from investo.models import SourceCollectionReport, SourceOutcome

    called_with: list[date] = []
    fake_outcome = SourceOutcome.ok("fake-src", "news", item_count=1)

    async def _spy(target_date: date) -> SourceCollectionReport:
        called_with.append(target_date)
        return SourceCollectionReport(items=(_item(),), outcomes=(fake_outcome,))

    monkeypatch.setattr(
        "investo.orchestrator.pipeline._default_collect_sources", _spy, raising=True
    )

    items, outcomes = await _stage_collect(_TARGET)  # No fetch= override.
    assert called_with == [_TARGET]
    assert outcomes == (fake_outcome,)
    assert len(items) == 1


# ---------------------------------------------------------------------------
# Programmer error from aggregator propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_collect_propagates_unexpected_exception() -> None:
    """If the aggregator raises a non-source exception (programmer
    error per u1's aggregator contract), ``_stage_collect`` does NOT
    swallow it — propagates so ``main()``'s top-level guard catches
    it (AC-003-7).
    """

    async def _broken_fetch(target_date: date) -> list[NormalizedItem]:
        raise RuntimeError("aggregator blew up")

    with pytest.raises(RuntimeError, match="aggregator blew up"):
        await _stage_collect(_TARGET, fetch=_broken_fetch)
