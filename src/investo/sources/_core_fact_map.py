"""u55 Step 1 — Source-ticker → :class:`CoreFact` mapping table.

Adapters (stooq-price, yfinance) call :func:`core_fact_for_ticker`
when building ``raw_metadata["core_facts"]`` so the numeric_verify
gate can look up "what does this ticker stand for" without
hard-coding ticker knowledge in every adapter.

The mapping covers indices, FX, yields, and the two crypto majors.
Tickers without a known core-fact identity simply do not register a
``core_facts`` entry — the gate then treats the body number as
non-core (``warn``) rather than ``unverified`` (``downgrade``).

Module boundary: this module is under ``investo.sources`` (shared
adapter helper), imports only :mod:`investo.models.core_fact`.
"""

from __future__ import annotations

from typing import Final

from investo.models.core_fact import (
    CORE_FACT_METADATA_PREFIX,
    CoreFact,
    core_fact_metadata_key,
)

# yfinance-style ticker → CoreFact. We use the yfinance vocabulary as
# the canonical adapter-side name (matches stooq-price's
# :data:`_TICKER_MAP` and yfinance's own ticker list).
_TICKER_TO_CORE_FACT: Final[dict[str, CoreFact]] = {
    "^KS11": "kospi_close",
    "^KOSPI": "kospi_close",  # alt
    "^KQ11": "kosdaq_close",
    "^KOSDAQ": "kosdaq_close",  # alt
    "^GSPC": "spx_close",
    "^IXIC": "ndx_close",
    "^DJI": "dji_close",
    "BTC-USD": "btc_usd",
    "ETH-USD": "eth_usd",
    "KRW=X": "usd_krw",
    "USDKRW=X": "usd_krw",
    "^TNX": "us10y_yield",
    "^VIX": "vix",
}


def core_fact_for_ticker(ticker: str) -> CoreFact | None:
    """Resolve ``ticker`` (yfinance vocabulary) to its :class:`CoreFact`.

    Returns ``None`` when the ticker is not one of the ten core facts —
    adapters then omit the ``core_facts`` entry for that row. Lookup is
    O(1) and case-sensitive (tickers are already normalized upstream).
    """
    return _TICKER_TO_CORE_FACT.get(ticker)


__all__ = [
    "CORE_FACT_METADATA_PREFIX",
    "core_fact_for_ticker",
    "core_fact_metadata_key",
]
