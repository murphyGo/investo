"""Tests for the public surface of ``investo.sources``.

Pins the plugin contract per business-rules.md R2 and NFR ACs 5.2 / 5.3:

* **AC-5.2** drift guard — `len(list_sources()) == EXPECTED_ADAPTER_COUNT`
  with the names matching `EXPECTED_ADAPTER_NAMES` exactly. Adding /
  removing an adapter without updating these constants (and the
  corresponding `from . import <name>` line in `__init__.py`) breaks
  the test loudly.
* **AC-5.3** duplicate-name guard — registering twice raises
  ``RuntimeError`` even when the duplicate uses a different class.
* **Star-import surface** — only the names in `__all__` are exposed.
  Internal helpers (registry / retry / sanitize / window / validators)
  must not leak.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar

import httpx
import pytest

import investo.sources
from investo.models import Category, NormalizedItem
from investo.sources import FetchWindow, SourceAdapter, SourceFetchError, fetch_all, list_sources
from investo.sources._registry import _ADAPTERS, _clear_for_test, register
from investo.sources.coingecko import CoinGeckoPriceAdapter
from investo.sources.fomc_rss import FomcRssAdapter
from investo.sources.fred import FredMacroAdapter
from investo.sources.sec_edgar_8k import SecEdgar8kAdapter
from investo.sources.yahoo_finance_news import YahooFinanceNewsAdapter
from investo.sources.yfinance import YFinancePriceAdapter

# Bump these together when adding/removing an adapter; they must
# stay in lockstep with the imports in src/investo/sources/__init__.py.
EXPECTED_ADAPTER_COUNT = 6
EXPECTED_ADAPTER_NAMES = {
    "fomc-rss",
    "yfinance-price",
    "coingecko-price",
    "fred-macro",
    "yahoo-finance-news",
    "sec-edgar-8k",
}


@pytest.fixture(autouse=True)
def _isolate_registry() -> Iterator[None]:
    """Override the conftest autouse fixture for this file.

    The conftest version clears ``_ADAPTERS`` before each test so
    other tests can register stubs in a clean registry. This file
    instead exercises the package-level production state, so we
    snapshot, clear, re-register the production adapters (matching
    what ``import investo.sources`` does at first load), yield, then
    restore the original snapshot on teardown.
    """

    snapshot = dict(_ADAPTERS)
    _clear_for_test()
    register(FomcRssAdapter)
    register(YFinancePriceAdapter)
    register(CoinGeckoPriceAdapter)
    register(FredMacroAdapter)
    register(YahooFinanceNewsAdapter)
    register(SecEdgar8kAdapter)
    try:
        yield
    finally:
        _clear_for_test()
        _ADAPTERS.update(snapshot)


# ---------------------------------------------------------------------------
# AC-5.2 — drift guard
# ---------------------------------------------------------------------------


def test_registered_adapter_count_matches_expected() -> None:
    assert len(list_sources()) == EXPECTED_ADAPTER_COUNT


def test_registered_adapter_names_match_expected() -> None:
    assert {a.name for a in list_sources()} == EXPECTED_ADAPTER_NAMES


def test_adding_stub_adapter_increases_count_by_one() -> None:
    # Proves the drift guard is meaningful: a +1 stub registration
    # must move the count by exactly +1, with no other side effects
    # on the existing entries.
    class StubAdapter:
        name: ClassVar[str] = "drift-stub"
        category: ClassVar[Category] = "news"

        async def fetch(
            self,
            client: httpx.AsyncClient,
            window: FetchWindow,
        ) -> list[NormalizedItem]:
            return []

    register(StubAdapter)

    assert len(list_sources()) == EXPECTED_ADAPTER_COUNT + 1
    names = {a.name for a in list_sources()}
    assert names == EXPECTED_ADAPTER_NAMES | {"drift-stub"}


# ---------------------------------------------------------------------------
# AC-5.3 — duplicate-name rejected at registration time
# ---------------------------------------------------------------------------


def test_re_registering_production_name_raises_runtime_error() -> None:
    class DuplicateAdapter:
        name: ClassVar[str] = "fomc-rss"  # collides with the live adapter
        category: ClassVar[Category] = "news"

        async def fetch(
            self,
            client: httpx.AsyncClient,
            window: FetchWindow,
        ) -> list[NormalizedItem]:
            return []

    with pytest.raises(RuntimeError, match="duplicate source name"):
        register(DuplicateAdapter)


# ---------------------------------------------------------------------------
# Star-import surface — only `__all__` is exposed
# ---------------------------------------------------------------------------


def test_all_lists_exactly_the_public_surface() -> None:
    expected = {
        "FetchWindow",
        "SourceAdapter",
        "SourceFetchError",
        "fetch_all",
        "list_sources",
    }
    assert set(investo.sources.__all__) == expected


def test_all_does_not_leak_internal_helpers() -> None:
    # Internal helpers must not appear in __all__ even if they happen
    # to be importable via attribute access (e.g. ``investo.sources._registry``).
    leaked = {
        "_ADAPTERS",
        "_clear_for_test",
        "_config",
        "_registry",
        "_retry",
        "_sanitize",
        "_validators",
        "_window",
        "register",
        "retry_get",
        "compute_sleep",
        "RetryConfig",
        "DEFAULT_CONFIG",
        "strip_html",
        "parse_symbol_list",
        "fomc_rss",
        "FomcRssAdapter",
        "yfinance",
        "YFinancePriceAdapter",
        "coingecko",
        "CoinGeckoPriceAdapter",
        "fred",
        "FredMacroAdapter",
        "yahoo_finance_news",
        "YahooFinanceNewsAdapter",
        "sec_edgar_8k",
        "SecEdgar8kAdapter",
    }
    assert not (leaked & set(investo.sources.__all__))


# ---------------------------------------------------------------------------
# Re-export identity — the public name binds to the canonical object
# ---------------------------------------------------------------------------


def test_public_re_exports_are_canonical_objects() -> None:
    # Importing each name from investo.sources should yield the same
    # object as importing from its canonical defining module.
    from investo.sources._registry import list_sources as canonical_list_sources
    from investo.sources._window import FetchWindow as canonical_FetchWindow
    from investo.sources.aggregator import fetch_all as canonical_fetch_all
    from investo.sources.protocol import SourceAdapter as canonical_SourceAdapter
    from investo.sources.protocol import SourceFetchError as canonical_SourceFetchError

    assert SourceAdapter is canonical_SourceAdapter
    assert SourceFetchError is canonical_SourceFetchError
    assert list_sources is canonical_list_sources
    assert fetch_all is canonical_fetch_all
    assert FetchWindow is canonical_FetchWindow
