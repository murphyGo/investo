"""Wall-clock budget test for ``fetch_all``.

Pins NFR AC-1.1: with one slow adapter that uses its full budget and
two fast adapters, ``fetch_all`` returns within budget. The
production magnitudes (60-s slow + 70-s ceiling) are shrunken by 100x
here so the test suite stays fast — the structural property is the
same: ``asyncio.gather`` runs adapters concurrently, so total time is
bounded by the slowest, not the sum.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, date, datetime
from typing import ClassVar

import httpx

from investo.models import Category, NormalizedItem
from investo.sources._registry import register
from investo.sources._window import FetchWindow
from investo.sources.aggregator import fetch_all

# The registry-isolation fixture lives in tests/unit/sources/conftest.py.

_TARGET_DATE = date(2026, 4, 27)
_PUBLISHED = datetime(2026, 4, 27, 12, 0, tzinfo=UTC)


def _item(source_name: str) -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name,
        category="news",
        title="headline",
        published_at=_PUBLISHED,
    )


async def test_fetch_all_within_budget_with_one_slow_adapter() -> None:
    # AC-1.1 (scaled): 1 slow adapter (0.5 s) + 2 fast adapters →
    # fetch_all returns ≤ 0.7 s. The slack absorbs AsyncClient
    # construction + gather dispatch on slow CI hosts.

    @register
    class SlowStub:
        name: ClassVar[str] = "slow"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            await asyncio.sleep(0.5)
            return [_item("slow")]

    @register
    class FastA:
        name: ClassVar[str] = "fast-a"
        category: ClassVar[Category] = "macro"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return [_item("fast-a")]

    @register
    class FastB:
        name: ClassVar[str] = "fast-b"
        category: ClassVar[Category] = "calendar"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return [_item("fast-b")]

    start = time.monotonic()
    result = await fetch_all(_TARGET_DATE)
    elapsed = time.monotonic() - start

    assert {item.source_name for item in result} == {"slow", "fast-a", "fast-b"}
    assert elapsed < 0.7


async def test_fetch_all_dispatches_adapters_concurrently() -> None:
    # Concurrency proof: 3 adapters that each sleep 0.3 s. Sequential
    # dispatch would total 0.9 s; concurrent dispatch totals ~0.3 s.
    # Bound at 0.75 s pins concurrency with generous slack for slow CI.

    @register
    class SleepyA:
        name: ClassVar[str] = "sleepy-a"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            await asyncio.sleep(0.3)
            return [_item("sleepy-a")]

    @register
    class SleepyB:
        name: ClassVar[str] = "sleepy-b"
        category: ClassVar[Category] = "macro"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            await asyncio.sleep(0.3)
            return [_item("sleepy-b")]

    @register
    class SleepyC:
        name: ClassVar[str] = "sleepy-c"
        category: ClassVar[Category] = "calendar"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            await asyncio.sleep(0.3)
            return [_item("sleepy-c")]

    start = time.monotonic()
    result = await fetch_all(_TARGET_DATE)
    elapsed = time.monotonic() - start

    assert {item.source_name for item in result} == {"sleepy-a", "sleepy-b", "sleepy-c"}
    assert elapsed < 0.75
