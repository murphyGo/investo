"""Source Adapters — plugin layer + public re-exports.

This package's ``__init__.py`` is the unit's stable public surface
**and** the discovery point for every adapter. Importing the package
triggers ``@register`` for each adapter module imported below,
populating the singleton registry exactly once per process at first
load (FD §E2).

NFR AC-5.4 — adding a new adapter is a 4-line procedure:

1. Create ``src/investo/sources/<name>.py``
2. Define the adapter class
3. Apply ``@register`` at class definition
4. Add ``from . import <name>  # noqa: F401`` below

The names listed in :data:`__all__` form the plugin contract that
sibling units (orchestrator) and external callers consume. Internal
helpers (``_window``, ``_retry``, ``_sanitize``, ``_registry``) are
intentionally NOT re-exported.
"""

from investo.sources._registry import list_sources
from investo.sources._window import FetchWindow
from investo.sources.aggregator import collect_sources, fetch_all
from investo.sources.protocol import SourceAdapter, SourceFetchError

# Adapter discovery — each import below runs the module's
# ``@register`` decorator at first load.
from . import (
    binance_crypto_market,  # noqa: F401
    cnbc_top_news,  # noqa: F401
    coingecko,  # noqa: F401
    dart_disclosure,  # noqa: F401
    defillama_market_structure,  # noqa: F401
    fomc_calendar,  # noqa: F401
    fomc_rss,  # noqa: F401
    fred,  # noqa: F401
    fred_economic_calendar,  # noqa: F401
    fsc_krx_index_price,  # noqa: F401
    fsc_krx_stock_price,  # noqa: F401
    korea_policy_rss,  # noqa: F401
    nasdaq_earnings_calendar,  # noqa: F401
    nasdaq_stocks_news,  # noqa: F401
    sec_edgar_8k,  # noqa: F401
    stooq_price,  # noqa: F401
    theblock_crypto,  # noqa: F401
    treasury_rates,  # noqa: F401
    us_economic_calendar,  # noqa: F401
    yahoo_finance_news,  # noqa: F401
    yfinance,  # noqa: F401
    yonhap_market,  # noqa: F401
)

__all__ = [
    "FetchWindow",
    "SourceAdapter",
    "SourceFetchError",
    "collect_sources",
    "fetch_all",
    "list_sources",
]
