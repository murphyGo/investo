"""Tests for ``investo.sources.aggregator.fetch_all``.

Pins the failure-isolation contract per FD R6 and NFR-003 ACs 3.1-3.5,
plus programmer-error propagation (FD §E5, business-logic-model.md L4).
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import ClassVar

import httpx
import pytest

from investo.models import Category, NormalizedItem
from investo.sources._registry import register
from investo.sources._window import FetchWindow
from investo.sources.aggregator import fetch_all
from investo.sources.protocol import SourceFetchError

# The registry-isolation fixture lives in tests/unit/sources/conftest.py.

_TARGET_DATE = date(2026, 4, 27)
_PUBLISHED = datetime(2026, 4, 27, 12, 0, tzinfo=UTC)


def _item(source_name: str, title: str = "headline") -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name,
        category="news",
        title=title,
        published_at=_PUBLISHED,
    )


# ---------------------------------------------------------------------------
# Empty registry / empty result (AC-3.5 owner-of-policy split)
# ---------------------------------------------------------------------------


async def test_fetch_all_empty_registry_returns_empty_list() -> None:
    # AC-3.5: u1 does not interpret "no items" as failure — that policy
    # belongs to the orchestrator. fetch_all returns [] and does not raise.
    result = await fetch_all(_TARGET_DATE)
    assert result == []


async def test_fetch_all_empty_result_does_not_raise() -> None:
    @register
    class EmptyStub:
        name: ClassVar[str] = "empty"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return []

    result = await fetch_all(_TARGET_DATE)
    assert result == []


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_fetch_all_single_adapter_returns_items() -> None:
    @register
    class StubA:
        name: ClassVar[str] = "stub-a"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return [_item("stub-a"), _item("stub-a", "second")]

    result = await fetch_all(_TARGET_DATE)
    assert len(result) == 2
    assert all(item.source_name == "stub-a" for item in result)


async def test_fetch_all_multiple_adapters_concatenates_results() -> None:
    @register
    class StubA:
        name: ClassVar[str] = "stub-a"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return [_item("stub-a")]

    @register
    class StubB:
        name: ClassVar[str] = "stub-b"
        category: ClassVar[Category] = "macro"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return [_item("stub-b")]

    result = await fetch_all(_TARGET_DATE)
    names = sorted(item.source_name for item in result)
    assert names == ["stub-a", "stub-b"]


async def test_fetch_all_drops_items_more_than_30_days_in_future(
    caplog: pytest.LogCaptureFixture,
) -> None:
    future_published = datetime(2026, 6, 28, 0, 0, tzinfo=UTC)

    @register
    class FutureDatedStub:
        name: ClassVar[str] = "future-dated"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return [
                _item("future-dated", "normal"),
                NormalizedItem(
                    source_name="future-dated",
                    category="news",
                    title="future typo",
                    published_at=future_published,
                ),
            ]

    with caplog.at_level(logging.WARNING, logger="investo.sources.aggregator"):
        result = await fetch_all(_TARGET_DATE)

    assert [item.title for item in result] == ["normal"]
    assert "future-dated item" in caplog.text


async def test_fetch_all_passes_window_to_adapter() -> None:
    captured: dict[str, FetchWindow | None] = {"window": None}

    @register
    class CapturingStub:
        name: ClassVar[str] = "capturing"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            captured["window"] = window
            return []

    await fetch_all(_TARGET_DATE)
    assert captured["window"] is not None
    assert captured["window"].target_date == _TARGET_DATE


# ---------------------------------------------------------------------------
# AC-3.1, 3.2: SourceFetchError is caught and logged, not raised
# ---------------------------------------------------------------------------


async def test_fetch_all_does_not_raise_on_source_fetch_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    @register
    class FailingStub:
        name: ClassVar[str] = "failing"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            raise SourceFetchError("failing", "synthetic", transient=True)

    with caplog.at_level(logging.WARNING, logger="investo.sources.aggregator"):
        result = await fetch_all(_TARGET_DATE)

    assert result == []
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    rendered = warnings[0].getMessage()
    assert "failing" in rendered
    assert "transient=True" in rendered


async def test_fetch_all_logs_terminal_failure_with_transient_false(
    caplog: pytest.LogCaptureFixture,
) -> None:
    @register
    class FailingStub:
        name: ClassVar[str] = "terminal"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            raise SourceFetchError("terminal", "schema mismatch", transient=False)

    with caplog.at_level(logging.WARNING, logger="investo.sources.aggregator"):
        await fetch_all(_TARGET_DATE)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "transient=False" in warnings[0].getMessage()


# ---------------------------------------------------------------------------
# AC-3.3: 1 fails, 2 succeed → 2 good lists' concatenation
# ---------------------------------------------------------------------------


async def test_fetch_all_isolates_one_failure_from_two_successes() -> None:
    @register
    class GoodA:
        name: ClassVar[str] = "good-a"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return [_item("good-a")]

    @register
    class BadStub:
        name: ClassVar[str] = "bad"
        category: ClassVar[Category] = "macro"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            raise SourceFetchError("bad", "boom", transient=False)

    @register
    class GoodB:
        name: ClassVar[str] = "good-b"
        category: ClassVar[Category] = "calendar"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return [_item("good-b")]

    result = await fetch_all(_TARGET_DATE)
    names = sorted(item.source_name for item in result)
    assert names == ["good-a", "good-b"]


# ---------------------------------------------------------------------------
# AC-3.4: all raise → []
# ---------------------------------------------------------------------------


async def test_fetch_all_all_failures_returns_empty_list() -> None:
    @register
    class FailA:
        name: ClassVar[str] = "fail-a"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            raise SourceFetchError("fail-a", "boom", transient=True)

    @register
    class FailB:
        name: ClassVar[str] = "fail-b"
        category: ClassVar[Category] = "macro"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            raise SourceFetchError("fail-b", "boom", transient=False)

    result = await fetch_all(_TARGET_DATE)
    assert result == []


# ---------------------------------------------------------------------------
# Programmer-error propagation (FD R6 second clause, L4 last row)
# ---------------------------------------------------------------------------


async def test_fetch_all_programmer_error_propagates() -> None:
    @register
    class BuggyStub:
        name: ClassVar[str] = "buggy"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            raise KeyError("buggy parser")

    with pytest.raises(KeyError, match="buggy parser"):
        await fetch_all(_TARGET_DATE)


async def test_fetch_all_programmer_error_kills_run_even_with_good_adapters() -> None:
    # A buggy adapter must not be silenced by sibling adapters that
    # happen to succeed — the bug is ours, not the source's.
    @register
    class GoodStub:
        name: ClassVar[str] = "good"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return [_item("good")]

    @register
    class BuggyStub:
        name: ClassVar[str] = "buggy"
        category: ClassVar[Category] = "macro"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            raise RuntimeError("internal bug")

    with pytest.raises(RuntimeError, match="internal bug"):
        await fetch_all(_TARGET_DATE)
