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

from investo.briefing.segments import _CRYPTO_ONLY_SOURCES, _US_ONLY_SOURCES
from investo.models import Category, NormalizedItem
from investo.sources._registry import register
from investo.sources._window import FetchWindow
from investo.sources.aggregator import (
    _CRYPTO_MARKET_SOURCES,
    _US_MARKET_SOURCES,
    _window_for_adapter,
    fetch_all,
)
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


async def test_fetch_all_logs_source_success_count_and_window(
    caplog: pytest.LogCaptureFixture,
) -> None:
    @register
    class StubA:
        name: ClassVar[str] = "stub-a"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return [_item("stub-a"), _item("stub-a", "second")]

    with caplog.at_level(logging.INFO, logger="investo.sources.aggregator"):
        await fetch_all(_TARGET_DATE)

    info_records = [
        record
        for record in caplog.records
        if record.levelno == logging.INFO and record.getMessage().startswith("source returned")
    ]
    assert len(info_records) == 1
    record = info_records[0]
    assert record.getMessage().startswith(
        "source returned source_name=stub-a category=news item_count=2 "
        "window_start_utc=2026-04-26T15:00:00+00:00 "
        "window_end_utc=2026-04-27T15:00:00+00:00 elapsed_s="
    )
    assert record.source_name == "stub-a"
    assert record.category == "news"
    assert record.item_count == 2
    assert record.window_start_utc == "2026-04-26T15:00:00+00:00"
    assert record.window_end_utc == "2026-04-27T15:00:00+00:00"
    assert record.__dict__["elapsed_s"] >= 0
    # u136 Contract #6 — items without harvested images report zero.
    assert record.image_items == 0
    assert record.getMessage().endswith("image_items=0")


async def test_fetch_all_logs_image_items_count(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # u136 Contract #6 — the per-source diagnostics record counts the
    # returned items whose raw_metadata carries a harvested image_url.
    # R13: only the integer count is logged, never the URLs.
    image_url = "https://img.example.com/photo.jpg"

    def _image_item(title: str) -> NormalizedItem:
        return NormalizedItem(
            source_name="image-stub",
            category="news",
            title=title,
            published_at=_PUBLISHED,
            raw_metadata={"image_url": image_url, "image_mime": "image/jpeg"},
        )

    @register
    class ImageStub:
        name: ClassVar[str] = "image-stub"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return [
                _image_item("with image 1"),
                _item("image-stub", "no image"),
                _image_item("with image 2"),
            ]

    with caplog.at_level(logging.INFO, logger="investo.sources.aggregator"):
        await fetch_all(_TARGET_DATE)

    info_records = [
        record
        for record in caplog.records
        if record.levelno == logging.INFO and record.getMessage().startswith("source returned")
    ]
    assert len(info_records) == 1
    record = info_records[0]
    assert record.item_count == 3
    assert record.image_items == 2
    assert record.getMessage().endswith("image_items=2")
    # R13: the record must not leak the image URL itself.
    assert image_url not in record.getMessage()


async def test_fetch_all_logs_zero_item_success(
    caplog: pytest.LogCaptureFixture,
) -> None:
    @register
    class EmptyStub:
        name: ClassVar[str] = "empty-source"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            return []

    with caplog.at_level(logging.INFO, logger="investo.sources.aggregator"):
        result = await fetch_all(_TARGET_DATE)

    assert result == []
    info_records = [
        record
        for record in caplog.records
        if record.levelno == logging.INFO and record.getMessage().startswith("source returned")
    ]
    assert len(info_records) == 1
    assert (
        info_records[0]
        .getMessage()
        .startswith(
            "source returned source_name=empty-source category=news item_count=0 "
            "window_start_utc=2026-04-26T15:00:00+00:00 "
            "window_end_utc=2026-04-27T15:00:00+00:00 elapsed_s="
        )
    )
    assert info_records[0].source_name == "empty-source"
    assert info_records[0].item_count == 0
    assert info_records[0].__dict__["elapsed_s"] >= 0
    # u136 Contract #6 — zero returned items → image_items=0.
    assert info_records[0].image_items == 0
    assert info_records[0].getMessage().endswith("image_items=0")


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


async def test_fetch_all_passes_new_york_window_to_us_market_adapter() -> None:
    captured: dict[str, FetchWindow | None] = {"window": None}

    @register
    class NasdaqStocksStub:
        name: ClassVar[str] = "nasdaq-stocks-news"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            captured["window"] = window
            return []

    await fetch_all(date(2026, 5, 6))

    assert captured["window"] is not None
    assert captured["window"].start_utc == datetime(2026, 5, 6, 4, 0, tzinfo=UTC)
    assert captured["window"].end_utc == datetime(2026, 5, 7, 4, 0, tzinfo=UTC)


@pytest.mark.parametrize("source_name", ["treasury-rates", "us-economic-calendar"])
async def test_fetch_all_passes_new_york_window_to_new_us_market_adapters(
    source_name: str,
) -> None:
    captured: dict[str, FetchWindow | None] = {"window": None}

    @register
    class NewUsMarketStub:
        name: ClassVar[str] = source_name
        category: ClassVar[Category] = "macro"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            captured["window"] = window
            return []

    await fetch_all(date(2026, 5, 6))

    assert captured["window"] is not None
    assert captured["window"].start_utc == datetime(2026, 5, 6, 4, 0, tzinfo=UTC)
    assert captured["window"].end_utc == datetime(2026, 5, 7, 4, 0, tzinfo=UTC)


def test_all_us_only_sources_have_new_york_market_window_registration() -> None:
    assert _US_ONLY_SOURCES <= _US_MARKET_SOURCES


@pytest.mark.parametrize("source_name", sorted(_US_MARKET_SOURCES))
def test_us_market_sources_resolve_to_new_york_window(source_name: str) -> None:
    window = _window_for_adapter(date(2026, 5, 6), source_name)

    assert window.start_utc == datetime(2026, 5, 6, 4, 0, tzinfo=UTC)
    assert window.end_utc == datetime(2026, 5, 7, 4, 0, tzinfo=UTC)


async def test_fetch_all_passes_utc_window_to_crypto_adapter() -> None:
    captured: dict[str, FetchWindow | None] = {"window": None}

    @register
    class CoinGeckoStub:
        name: ClassVar[str] = "coingecko-price"
        category: ClassVar[Category] = "price"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            captured["window"] = window
            return []

    await fetch_all(date(2026, 5, 6))

    assert captured["window"] is not None
    assert captured["window"].start_utc == datetime(2026, 5, 6, 0, 0, tzinfo=UTC)
    assert captured["window"].end_utc == datetime(2026, 5, 7, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "source_name",
    ["binance-crypto-market", "defillama-market-structure"],
)
async def test_fetch_all_passes_utc_window_to_new_crypto_adapters(source_name: str) -> None:
    captured: dict[str, FetchWindow | None] = {"window": None}

    @register
    class NewCryptoStub:
        name: ClassVar[str] = source_name
        category: ClassVar[Category] = "price"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            captured["window"] = window
            return []

    await fetch_all(date(2026, 5, 6))

    assert captured["window"] is not None
    assert captured["window"].start_utc == datetime(2026, 5, 6, 0, 0, tzinfo=UTC)
    assert captured["window"].end_utc == datetime(2026, 5, 7, 0, 0, tzinfo=UTC)


def test_all_crypto_only_sources_have_utc_market_window_registration() -> None:
    assert _CRYPTO_ONLY_SOURCES <= _CRYPTO_MARKET_SOURCES


@pytest.mark.parametrize("source_name", sorted(_CRYPTO_MARKET_SOURCES))
def test_crypto_market_sources_resolve_to_utc_window(source_name: str) -> None:
    window = _window_for_adapter(date(2026, 5, 6), source_name)

    assert window.start_utc == datetime(2026, 5, 6, 0, 0, tzinfo=UTC)
    assert window.end_utc == datetime(2026, 5, 7, 0, 0, tzinfo=UTC)


async def test_fetch_all_keeps_same_day_us_and_crypto_items_after_kst_cutoff() -> None:
    us_item = NormalizedItem(
        source_name="nasdaq-stocks-news",
        category="news",
        title="Nasdaq afternoon update",
        published_at=datetime(2026, 5, 6, 18, 0, tzinfo=UTC),
    )
    crypto_item = NormalizedItem(
        source_name="coingecko-price",
        category="price",
        title="BTC $100,000.00 (+1.00%)",
        published_at=datetime(2026, 5, 6, 18, 0, tzinfo=UTC),
    )

    @register
    class NasdaqStocksStub:
        name: ClassVar[str] = "nasdaq-stocks-news"
        category: ClassVar[Category] = "news"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            assert window.contains(us_item.published_at)
            return [us_item]

    @register
    class CoinGeckoStub:
        name: ClassVar[str] = "coingecko-price"
        category: ClassVar[Category] = "price"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            assert window.contains(crypto_item.published_at)
            return [crypto_item]

    result = await fetch_all(date(2026, 5, 6))

    assert result == [us_item, crypto_item]


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
    assert (
        warnings[0]
        .getMessage()
        .startswith("source failed source_name=failing category=news transient=True elapsed_s=")
    )
    assert " error=source 'failing' failed: synthetic" in warnings[0].getMessage()
    assert warnings[0].source_name == "failing"
    assert warnings[0].category == "news"
    assert warnings[0].error == "source 'failing' failed: synthetic"
    assert warnings[0].transient is True
    assert warnings[0].__dict__["elapsed_s"] >= 0


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
    assert (
        warnings[0]
        .getMessage()
        .startswith("source failed source_name=terminal category=news transient=False elapsed_s=")
    )
    assert " error=source 'terminal' failed: schema mismatch" in warnings[0].getMessage()
    assert warnings[0].source_name == "terminal"
    assert warnings[0].category == "news"
    assert warnings[0].error == "source 'terminal' failed: schema mismatch"
    assert warnings[0].transient is False
    assert warnings[0].__dict__["elapsed_s"] >= 0


async def test_fetch_all_structured_log_uses_exception_source_name_and_adapter_category(
    caplog: pytest.LogCaptureFixture,
) -> None:
    @register
    class LyingStub:
        name: ClassVar[str] = "registered-name"
        category: ClassVar[Category] = "macro"

        async def fetch(
            self, client: httpx.AsyncClient, window: FetchWindow
        ) -> list[NormalizedItem]:
            raise SourceFetchError("self-reported-name", "boom", transient=False)

    with caplog.at_level(logging.WARNING, logger="investo.sources.aggregator"):
        await fetch_all(_TARGET_DATE)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert (
        warnings[0]
        .getMessage()
        .startswith(
            "source failed source_name=self-reported-name category=macro transient=False elapsed_s="
        )
    )
    assert " error=source 'self-reported-name' failed: boom" in warnings[0].getMessage()
    assert warnings[0].source_name == "self-reported-name"
    assert warnings[0].category == "macro"
    assert warnings[0].error == "source 'self-reported-name' failed: boom"
    assert warnings[0].transient is False
    assert warnings[0].__dict__["elapsed_s"] >= 0


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
