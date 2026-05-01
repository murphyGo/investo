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
from investo.sources.aggregator import fetch_all
from investo.sources.protocol import SourceAdapter, SourceFetchError

# Adapter discovery — each import below runs the module's
# ``@register`` decorator at first load.
from . import (
    coingecko,  # noqa: F401
    fomc_rss,  # noqa: F401
    fred,  # noqa: F401
    sec_edgar_8k,  # noqa: F401
    yahoo_finance_news,  # noqa: F401
    yfinance,  # noqa: F401
)

__all__ = [
    "FetchWindow",
    "SourceAdapter",
    "SourceFetchError",
    "fetch_all",
    "list_sources",
]
