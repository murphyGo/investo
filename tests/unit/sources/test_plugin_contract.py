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
from investo._internal.source_specs import SOURCE_SPECS_BY_NAME
from investo.briefing.segments import (
    _CRYPTO_ONLY_SOURCES,
    _DOMESTIC_ONLY_SOURCES,
    _OUTCOME_EXTRA_SOURCES_BY_SEGMENT,
    _SEGMENT_SOURCES,
    _SHARED_SOURCES_BY_SEGMENT,
    _US_ONLY_SOURCES,
)
from investo.models import Category, NormalizedItem
from investo.sources import FetchWindow, SourceAdapter, SourceFetchError, fetch_all, list_sources
from investo.sources._registry import _ADAPTERS, _clear_for_test, register
from investo.sources.alternative_fng import AlternativeFearGreedAdapter
from investo.sources.bea_macro_actuals import BeaMacroActualsAdapter
from investo.sources.binance_crypto_market import BinanceCryptoMarketAdapter
from investo.sources.bls_macro_actuals import BlsMacroActualsAdapter
from investo.sources.bybit_derivatives import BybitDerivativesAdapter
from investo.sources.cboe_volatility_indices import CboeVolatilityIndicesAdapter
from investo.sources.cftc_cot_positioning import CftcCotPositioningAdapter
from investo.sources.cftc_policy_rss import CftcPolicyRssAdapter
from investo.sources.cnbc_top_news import CnbcTopNewsAdapter
from investo.sources.coingecko import CoinGeckoPriceAdapter
from investo.sources.coingecko_global_market import CoinGeckoGlobalMarketAdapter
from investo.sources.dart_disclosure import DartDisclosureAdapter
from investo.sources.defillama_market_structure import DefiLlamaMarketStructureAdapter
from investo.sources.eia_petroleum_weekly import EiaPetroleumWeeklyAdapter
from investo.sources.fed_board_leadership import FedBoardLeadershipAdapter
from investo.sources.fed_speech_rss import FedSpeechRssAdapter
from investo.sources.fomc_calendar import FomcCalendarAdapter
from investo.sources.fomc_rss import FomcRssAdapter
from investo.sources.fred import FredMacroAdapter
from investo.sources.fred_economic_calendar import FredEconomicCalendarAdapter
from investo.sources.fsc_krx_index_price import FscKrxIndexPriceAdapter
from investo.sources.fsc_krx_stock_price import FscKrxStockPriceAdapter
from investo.sources.korea_policy_rss import KoreaPolicyRssAdapter
from investo.sources.krx_foreign_flows import KrxForeignFlowsAdapter
from investo.sources.nasdaq_earnings_calendar import NasdaqEarningsCalendarAdapter
from investo.sources.nasdaq_stocks_news import NasdaqStocksNewsAdapter
from investo.sources.nasdaq_symbol_directory import NasdaqSymbolDirectoryAdapter
from investo.sources.nyfed_reference_rates import NyfedReferenceRatesAdapter
from investo.sources.official_policy import (
    CongressGovBillActionsAdapter,
    HouseFinancialServicesPolicyAdapter,
    SenateBankingPolicyAdapter,
)
from investo.sources.okx_derivatives import OkxDerivativesAdapter
from investo.sources.sec_company_facts import SecCompanyFactsAdapter
from investo.sources.sec_edgar_8k import SecEdgar8kAdapter
from investo.sources.sec_newsroom_rss import SecNewsroomRssAdapter
from investo.sources.stooq_kr_market import StooqKrMarketAdapter
from investo.sources.stooq_price import StooqPriceAdapter
from investo.sources.theblock_crypto import TheBlockCryptoAdapter
from investo.sources.tiers import ADAPTER_TIERS
from investo.sources.treasury_auctions import TreasuryAuctionsAdapter
from investo.sources.treasury_rates import TreasuryRatesAdapter
from investo.sources.us_economic_calendar import UsEconomicCalendarAdapter
from investo.sources.yahoo_finance_news import YahooFinanceNewsAdapter
from investo.sources.yfinance import YFinancePriceAdapter
from investo.sources.yonhap_market import YonhapMarketAdapter

EXPECTED_ADAPTER_NAMES = set(SOURCE_SPECS_BY_NAME)
EXPECTED_ADAPTER_COUNT = len(EXPECTED_ADAPTER_NAMES)


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
    register(AlternativeFearGreedAdapter)
    register(BeaMacroActualsAdapter)
    register(BlsMacroActualsAdapter)
    register(BybitDerivativesAdapter)
    register(CboeVolatilityIndicesAdapter)
    register(CftcCotPositioningAdapter)
    register(CftcPolicyRssAdapter)
    register(CoinGeckoGlobalMarketAdapter)
    register(OkxDerivativesAdapter)
    register(BinanceCryptoMarketAdapter)
    register(DartDisclosureAdapter)
    register(DefiLlamaMarketStructureAdapter)
    register(EiaPetroleumWeeklyAdapter)
    register(FedBoardLeadershipAdapter)
    register(FedSpeechRssAdapter)
    register(FomcCalendarAdapter)
    register(FomcRssAdapter)
    register(FscKrxIndexPriceAdapter)
    register(FscKrxStockPriceAdapter)
    register(KoreaPolicyRssAdapter)
    register(KrxForeignFlowsAdapter)
    register(YFinancePriceAdapter)
    register(StooqPriceAdapter)
    register(StooqKrMarketAdapter)
    register(CoinGeckoPriceAdapter)
    register(FredEconomicCalendarAdapter)
    register(FredMacroAdapter)
    register(NasdaqEarningsCalendarAdapter)
    register(NasdaqSymbolDirectoryAdapter)
    register(NasdaqStocksNewsAdapter)
    register(NyfedReferenceRatesAdapter)
    register(CongressGovBillActionsAdapter)
    register(SenateBankingPolicyAdapter)
    register(HouseFinancialServicesPolicyAdapter)
    register(YahooFinanceNewsAdapter)
    register(SecCompanyFactsAdapter)
    register(SecEdgar8kAdapter)
    register(SecNewsroomRssAdapter)
    register(YonhapMarketAdapter)
    register(TheBlockCryptoAdapter)
    register(TreasuryAuctionsAdapter)
    register(TreasuryRatesAdapter)
    register(UsEconomicCalendarAdapter)
    register(CnbcTopNewsAdapter)
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


def test_registered_adapters_have_explicit_tiers() -> None:
    missing_tier_entries = {
        adapter.name for adapter in list_sources() if adapter.name not in ADAPTER_TIERS
    }

    assert missing_tier_entries == set()


def test_adapter_tiers_do_not_include_unregistered_production_sources() -> None:
    registered_names = {adapter.name for adapter in list_sources()}

    assert set(ADAPTER_TIERS) == registered_names


def test_registered_adapters_have_explicit_segment_routing() -> None:
    shared_sources = set().union(*_SHARED_SOURCES_BY_SEGMENT.values())
    item_level_routed_sources = {"cftc-cot-positioning"}
    segment_only_sources = (
        _DOMESTIC_ONLY_SOURCES,
        _US_ONLY_SOURCES,
        _CRYPTO_ONLY_SOURCES,
    )
    missing_segment_routing: set[str] = set()
    ambiguous_segment_routing: set[str] = set()

    for adapter in list_sources():
        single_segment_memberships = sum(
            adapter.name in sources for sources in segment_only_sources
        )
        shared_membership = adapter.name in shared_sources
        if (
            single_segment_memberships == 0
            and not shared_membership
            and adapter.name not in item_level_routed_sources
        ):
            missing_segment_routing.add(adapter.name)
        if single_segment_memberships > 1 or (
            single_segment_memberships == 1 and shared_membership
        ):
            ambiguous_segment_routing.add(adapter.name)

    assert missing_segment_routing == set()
    assert ambiguous_segment_routing == set()


def test_segment_outcome_sources_match_declared_routing_maps() -> None:
    expected_segment_sources = {
        "domestic-equity": (
            _DOMESTIC_ONLY_SOURCES
            | _SHARED_SOURCES_BY_SEGMENT["domestic-equity"]
            | _OUTCOME_EXTRA_SOURCES_BY_SEGMENT["domestic-equity"]
        ),
        "us-equity": (
            _US_ONLY_SOURCES
            | _SHARED_SOURCES_BY_SEGMENT["us-equity"]
            | _OUTCOME_EXTRA_SOURCES_BY_SEGMENT["us-equity"]
        ),
        "crypto": (
            _CRYPTO_ONLY_SOURCES
            | _SHARED_SOURCES_BY_SEGMENT["crypto"]
            | _OUTCOME_EXTRA_SOURCES_BY_SEGMENT["crypto"]
        ),
    }

    assert expected_segment_sources == _SEGMENT_SOURCES


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
        "collect_sources",
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
        "binance_crypto_market",
        "BinanceCryptoMarketAdapter",
        "defillama_market_structure",
        "DefiLlamaMarketStructureAdapter",
        "fomc_calendar",
        "FomcCalendarAdapter",
        "fomc_rss",
        "FomcRssAdapter",
        "fed_speech_rss",
        "FedSpeechRssAdapter",
        "fsc_krx_index_price",
        "FscKrxIndexPriceAdapter",
        "fsc_krx_stock_price",
        "FscKrxStockPriceAdapter",
        "korea_policy_rss",
        "KoreaPolicyRssAdapter",
        "krx_foreign_flows",
        "KrxForeignFlowsAdapter",
        "yfinance",
        "YFinancePriceAdapter",
        "coingecko",
        "CoinGeckoPriceAdapter",
        "fred",
        "FredMacroAdapter",
        "fred_economic_calendar",
        "FredEconomicCalendarAdapter",
        "nasdaq_earnings_calendar",
        "NasdaqEarningsCalendarAdapter",
        "nasdaq_symbol_directory",
        "NasdaqSymbolDirectoryAdapter",
        "nasdaq_stocks_news",
        "NasdaqStocksNewsAdapter",
        "yahoo_finance_news",
        "YahooFinanceNewsAdapter",
        "sec_company_facts",
        "SecCompanyFactsAdapter",
        "sec_edgar_8k",
        "SecEdgar8kAdapter",
        "sec_newsroom_rss",
        "SecNewsroomRssAdapter",
        "stooq_price",
        "StooqPriceAdapter",
        "yonhap_market",
        "YonhapMarketAdapter",
        "theblock_crypto",
        "TheBlockCryptoAdapter",
        "treasury_auctions",
        "TreasuryAuctionsAdapter",
        "treasury_rates",
        "TreasuryRatesAdapter",
        "us_economic_calendar",
        "UsEconomicCalendarAdapter",
        "cnbc_top_news",
        "CnbcTopNewsAdapter",
        "dart_disclosure",
        "DartDisclosureAdapter",
        "alternative_fng",
        "AlternativeFearGreedAdapter",
        "bea_macro_actuals",
        "BeaMacroActualsAdapter",
        "bls_macro_actuals",
        "BlsMacroActualsAdapter",
        "bybit_derivatives",
        "BybitDerivativesAdapter",
        "cboe_volatility_indices",
        "CboeVolatilityIndicesAdapter",
        "cftc_cot_positioning",
        "CftcCotPositioningAdapter",
        "coingecko_global_market",
        "CoinGeckoGlobalMarketAdapter",
        "eia_petroleum_weekly",
        "EiaPetroleumWeeklyAdapter",
        "nyfed_reference_rates",
        "NyfedReferenceRatesAdapter",
        "okx_derivatives",
        "OkxDerivativesAdapter",
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
