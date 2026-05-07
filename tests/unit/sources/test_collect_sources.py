"""Tests for ``investo.sources.aggregator.collect_sources`` (u22).

Pins the per-source outcome reporting contract:

* one outcome per registered adapter (registry order)
* ``ok`` outcomes carry ``item_count`` matching the kept items
* ``zero`` outcomes are emitted when an adapter returns ``[]``
* ``failed`` outcomes are emitted when an adapter raises
  :class:`SourceFetchError`, with the ``failure_reason`` already
  passed through :func:`investo.models.sanitize_source_error_message`
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import ClassVar

import httpx
import pytest

from investo.models import Category, NormalizedItem
from investo.sources._registry import register
from investo.sources._window import FetchWindow
from investo.sources.aggregator import collect_sources
from investo.sources.protocol import SourceFetchError

# ``conftest.py`` ships an isolated registry fixture for every test.

_TARGET_DATE = date(2026, 4, 27)
_PUBLISHED = datetime(2026, 4, 27, 12, 0, tzinfo=UTC)


def _item(source_name: str, title: str = "headline") -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name,
        category="news",
        title=title,
        published_at=_PUBLISHED,
    )


async def test_collect_sources_returns_empty_report_for_empty_registry() -> None:
    report = await collect_sources(_TARGET_DATE)
    assert report.items == ()
    assert report.outcomes == ()
    assert report.empty is True


async def test_collect_sources_emits_ok_outcome_with_kept_count() -> None:
    @register
    class StubA:
        name: ClassVar[str] = "stub-a"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return [_item("stub-a"), _item("stub-a", "second")]

    report = await collect_sources(_TARGET_DATE)

    assert len(report.outcomes) == 1
    outcome = report.outcomes[0]
    assert outcome.source_name == "stub-a"
    assert outcome.category == "news"
    assert outcome.status == "ok"
    assert outcome.item_count == 2
    assert outcome.failure_reason is None


async def test_collect_sources_emits_zero_outcome_for_empty_adapter() -> None:
    @register
    class EmptyStub:
        name: ClassVar[str] = "empty-source"
        category: ClassVar[Category] = "macro"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return []

    report = await collect_sources(_TARGET_DATE)

    assert len(report.outcomes) == 1
    outcome = report.outcomes[0]
    assert outcome.status == "zero"
    assert outcome.item_count == 0
    assert outcome.failure_reason is None
    assert outcome.transient is None


async def test_collect_sources_emits_failed_outcome_with_sanitized_reason() -> None:
    @register
    class FailingStub:
        name: ClassVar[str] = "failing-src"
        category: ClassVar[Category] = "price"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            # The transient error message embeds a Telegram-bot-shaped
            # token to verify the sanitizer fires.
            raise SourceFetchError(
                "failing-src",
                "boom 1234567890:abcdefghijklmnopqrstuvwxyzABCDEFGHIJKL trailing",
                transient=True,
            )

    report = await collect_sources(_TARGET_DATE)

    assert len(report.outcomes) == 1
    outcome = report.outcomes[0]
    assert outcome.status == "failed"
    assert outcome.transient is True
    assert outcome.failure_reason is not None
    assert "1234567890:" not in outcome.failure_reason
    assert "[REDACTED" in outcome.failure_reason


async def test_collect_sources_outcomes_match_registry_order() -> None:
    @register
    class FirstStub:
        name: ClassVar[str] = "alpha"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return [_item("alpha")]

    @register
    class SecondStub:
        name: ClassVar[str] = "bravo"
        category: ClassVar[Category] = "macro"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return []

    @register
    class ThirdStub:
        name: ClassVar[str] = "charlie"
        category: ClassVar[Category] = "calendar"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            raise SourceFetchError("charlie", "schema mismatch", transient=False)

    report = await collect_sources(_TARGET_DATE)

    assert [outcome.source_name for outcome in report.outcomes] == ["alpha", "bravo", "charlie"]
    assert [outcome.status for outcome in report.outcomes] == ["ok", "zero", "failed"]


async def test_collect_sources_failure_reason_does_not_carry_secret_env_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R13 — the env-var value gets scrubbed out of the public reason."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "supersecret-token-value-xyz123")

    @register
    class LeakyStub:
        name: ClassVar[str] = "leaky"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            raise SourceFetchError(
                "leaky",
                "request used token supersecret-token-value-xyz123 unexpectedly",
                transient=True,
            )

    report = await collect_sources(_TARGET_DATE)

    assert report.outcomes[0].failure_reason is not None
    assert "supersecret-token-value-xyz123" not in report.outcomes[0].failure_reason
    assert "[REDACTED]" in report.outcomes[0].failure_reason


async def test_collect_sources_excludes_future_items_but_keeps_outcome_ok() -> None:
    """An adapter that emits a single in-window item alongside a future-
    dated row still counts as ``ok`` with the kept count, not the raw
    emitted count.
    """
    future = datetime(2026, 6, 28, 0, 0, tzinfo=UTC)

    @register
    class MixedStub:
        name: ClassVar[str] = "mixed"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return [
                _item("mixed", "current"),
                NormalizedItem(
                    source_name="mixed",
                    category="news",
                    title="future-typo",
                    published_at=future,
                ),
            ]

    report = await collect_sources(_TARGET_DATE)

    assert len(report.items) == 1
    assert report.outcomes[0].status == "ok"
    assert report.outcomes[0].item_count == 1


async def test_collect_sources_emits_zero_when_all_items_are_future_dated() -> None:
    future = datetime(2026, 6, 28, 0, 0, tzinfo=UTC)

    @register
    class AllFutureStub:
        name: ClassVar[str] = "all-future"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return [
                NormalizedItem(
                    source_name="all-future",
                    category="news",
                    title="future-only",
                    published_at=future,
                )
            ]

    report = await collect_sources(_TARGET_DATE)

    assert report.items == ()
    assert report.outcomes[0].status == "zero"
