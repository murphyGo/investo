"""Explicit lifecycle choices must not become data or collection evidence."""

from dataclasses import asdict, replace
from datetime import UTC, date, datetime
from typing import ClassVar

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from investo._internal.source_specs import SOURCE_SPECS, source_skip_reasons
from investo.models import Category, NormalizedItem, SourceCollectionReport, SourceOutcome
from investo.models.coverage import SOURCE_SKIP_REASON_LABELS
from investo.models.news_window import NewsObservationWindow
from investo.sources._registry import register
from investo.sources.aggregator import collect_sources

_DEFAULTS = {
    "binance-crypto-market": "region_denied",
    "cnbc-top-news": "access_denied",
    "yahoo-finance-news": "endpoint_removed",
    "korea-policy-rss": "upstream_unavailable",
    "krx-foreign-flows": "endpoint_removed",
}
_TARGET = date(2026, 10, 8)


def test_default_registry_and_exact_overrides() -> None:
    assert len(SOURCE_SPECS) == 44
    assert source_skip_reasons() == _DEFAULTS
    assert "cnbc-top-news" not in source_skip_reasons(enable=" cnbc-top-news,cnbc-top-news ")
    assert source_skip_reasons(disable="coingecko-price")["coingecko-price"] == "operator_disabled"


@pytest.mark.parametrize(
    ("enable", "disable"),
    [
        ("CNBC-TOP-NEWS", ""),
        ("not-a-key-or-source", ""),
        ("", "bad"),
        ("cnbc-top-news", "cnbc-top-news"),
    ],
)
def test_unknown_or_conflicting_config_has_bounded_error(enable: str, disable: str) -> None:
    with pytest.raises(ValueError) as error:
        source_skip_reasons(enable=enable, disable=disable)
    assert "not-a-key-or-source" not in str(error.value)


@given(st.sampled_from(tuple(SOURCE_SKIP_REASON_LABELS)))
@settings(max_examples=30)
def test_skip_reason_roundtrip_and_invariants(reason) -> None:
    skipped = SourceOutcome.skipped("cnbc-top-news", "news", reason=reason, tier="B")
    assert SourceOutcome(**asdict(skipped)) == skipped
    assert skipped.item_count == 0 and skipped.skip_reason_label
    for invalid in (
        {"item_count": 1},
        {"elapsed_s": 0.0},
        {"transient": False},
        {"failure_reason": "failed"},
        {"latest_item_at": datetime.now(UTC)},
    ):
        with pytest.raises(ValueError):
            replace(skipped, **invalid)
    with pytest.raises(ValueError):
        replace(SourceOutcome.zero("cnbc-top-news", "news"), skip_reason=reason)


@given(st.sets(st.sampled_from(tuple(_DEFAULTS))))
@settings(max_examples=30)
def test_enables_only_remove_selected_defaults(enabled) -> None:
    resolved = source_skip_reasons(enable=",".join(sorted(enabled)))
    assert set(resolved) == set(_DEFAULTS) - enabled


async def test_default_skips_do_not_open_client_or_call_adapters(monkeypatch) -> None:
    for source_name in _DEFAULTS:

        @register
        class Disabled:
            name: ClassVar[str] = source_name
            category: ClassVar[Category] = "news"

            async def fetch(self, *args):
                pytest.fail("disabled adapter must never fetch")

    monkeypatch.setattr(
        "investo.sources.aggregator.httpx.AsyncClient",
        lambda: pytest.fail("all-skipped collection must not create HTTP client"),
    )
    result = await collect_sources(_TARGET)
    assert not result.items and not result.window_coverages
    assert [outcome.source_name for outcome in result.outcomes] == list(_DEFAULTS)
    assert all(outcome.status == "skipped" for outcome in result.outcomes)


async def test_enable_and_operator_disable_keep_registry_order(monkeypatch) -> None:
    called = []
    for source_name in ("cnbc-top-news", "fed-speech-rss", "yahoo-finance-news"):

        @register
        class Stub:
            name: ClassVar[str] = source_name
            category: ClassVar[Category] = "news"

            async def fetch(self, client, window):
                called.append(self.name)
                return []

    monkeypatch.setenv("INVESTO_SOURCE_ENABLE", "cnbc-top-news")
    monkeypatch.setenv("INVESTO_SOURCE_DISABLE", "fed-speech-rss")
    result = await collect_sources(_TARGET)
    assert called == ["cnbc-top-news"]
    assert [(o.source_name, o.status) for o in result.outcomes] == [
        ("cnbc-top-news", "zero"),
        ("fed-speech-rss", "skipped"),
        ("yahoo-finance-news", "skipped"),
    ]
    assert result.outcomes[1].skip_reason == "operator_disabled"


async def test_invalid_config_precedes_all_source_io(monkeypatch) -> None:
    monkeypatch.setenv("INVESTO_SOURCE_ENABLE", "invalid-secret-sentinel")
    monkeypatch.setattr(
        "investo.sources.aggregator.list_sources", lambda: pytest.fail("not reached")
    )
    with pytest.raises(ValueError, match="unknown names"):
        await collect_sources(_TARGET)


async def test_skipped_news_does_not_emit_completed_window(monkeypatch) -> None:
    @register
    class Stub:
        name: ClassVar[str] = "yahoo-finance-news"
        category: ClassVar[Category] = "news"

        async def fetch_with_coverage(self, client, window):
            pytest.fail("a skip cannot provide pagination evidence")

        async def fetch(self, client, window):
            pytest.fail("a skip cannot fetch")

    start, end = datetime(2026, 10, 8, tzinfo=UTC), datetime(2026, 10, 9, tzinfo=UTC)
    news = NewsObservationWindow(start, start, end, "replay", "u165")
    report = await collect_sources(_TARGET, news_windows={Stub.name: news})
    assert report.outcomes[0].status == "skipped"
    assert report.window_coverages == ()


def test_source_spec_default_reason_invariants() -> None:
    enabled = next(spec for spec in SOURCE_SPECS if spec.default_enabled)
    with pytest.raises(ValueError):
        replace(enabled, disabled_reason="operator_disabled")
    with pytest.raises(ValueError):
        replace(enabled, default_enabled=False)


def test_collection_report_rejects_items_from_skipped_source() -> None:
    skip = SourceOutcome.skipped("cnbc-top-news", "news", reason="access_denied")
    item = NormalizedItem(
        source_name=skip.source_name,
        category="news",
        title="Synthetic item",
        published_at=datetime(2026, 10, 8, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="cannot contribute collection items"):
        SourceCollectionReport((item,), (skip,))
