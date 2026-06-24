"""u55 Step 1 — Typed core market-fact enum.

The numeric verification gate (``briefing/numeric_verify.py``, u55
Step 2) operates over a *fixed* 10-element enum of facts rather than
trying to extract arbitrary numerical prose claims from Stage 2
markdown. This trades coverage for precision: we cannot verify every
number, but the numbers we *can* verify carry a Decimal-as-string
source value with bounded tolerance.

Why "typed" framing instead of "find every claim":

* **No NLP**. Free-prose claim extraction depends on a parser that
  itself can hallucinate ("KOSPI 가 강세였다" — what number?). A typed
  enum sidesteps that by pinning *what we are verifying* up front.
* **Adapter contract**. Source adapters emit Decimal values into
  ``Item.raw_metadata["core_facts"]`` keyed by :class:`CoreFact` value
  string. Lookup is O(1) and Decimal-as-string round-trips for NFR-003
  reproducibility.
* **Append-only**. New facts can be added to the Literal without
  breaking back-compat — old adapters simply do not emit the new key,
  so it lands as ``unverified`` (action ``warn``) until an adapter is
  wired in.

Module boundary (project rule 2): this is foundation under
``investo.models`` — adapters and ``briefing.numeric_verify`` consume
it; we do not import from sibling units here.
"""

from __future__ import annotations

from typing import Final, Literal, get_args

# The closed set of core market facts the numeric gate verifies.
#
# Rationale for the 10 picks (see u55 plan §"CoreFact 10개" table):
#
# * ``kospi_close`` / ``kosdaq_close`` — domestic-equity headline.
# * ``spx_close`` / ``ndx_close`` / ``dji_close`` — US-equity headline.
# * ``btc_usd`` / ``eth_usd`` — crypto headline.
# * ``usd_krw`` — FX anchor that bridges domestic + US narratives.
# * ``us10y_yield`` — macro rate anchor.
# * ``vix`` — risk-regime anchor.
#
# Phase-2 candidates (DEBT-D55-A): structured ``usd_krw`` and
# ``us10y_yield`` adapters do not exist yet — those facts will fall to
# ``unverified`` (action ``warn``) until a free source lands.
CoreFact = Literal[
    "kospi_close",
    "kosdaq_close",
    "spx_close",
    "ndx_close",
    "dji_close",
    "btc_usd",
    "eth_usd",
    "usd_krw",
    "us10y_yield",
    "vix",
]


# Keyword tokens the numeric_verify scoped-window matcher looks for in
# Stage 2 markdown body. Each fact maps to a tuple of (Korean, English,
# optional alias) tokens. The matcher walks ``± WINDOW`` characters
# from each keyword hit to find a nearby Decimal candidate.
#
# Tokens are intentionally short and *not* word-bounded inside the
# regex — Korean prose lacks word boundaries, so matching ``"코스피"``
# as a substring catches both "코스피" and "코스피지수" cleanly. The
# trade-off is over-match on non-finance prose ("S&P 500" might appear
# in a regulatory note), accepted because the numeric proximity check
# fails closed: no nearby Decimal ⇒ skip silently.
CORE_FACT_KEYWORDS: Final[dict[CoreFact, tuple[str, ...]]] = {
    "kospi_close": ("코스피", "KOSPI"),
    "kosdaq_close": ("코스닥", "KOSDAQ"),
    "spx_close": ("S&P 500", "S&P500", "스탠더드앤푸어스", "스탠더드 앤 푸어스"),
    "ndx_close": ("나스닥", "NASDAQ", "Nasdaq"),
    "dji_close": ("다우", "DOW", "Dow Jones", "Dow"),
    "btc_usd": ("BTC", "비트코인", "Bitcoin", "bitcoin"),
    "eth_usd": ("ETH", "이더리움", "Ethereum", "ethereum"),
    "usd_krw": ("달러/원", "원/달러", "USD/KRW", "원화 환율", "USDKRW"),
    "us10y_yield": ("10년물", "10Y", "10년 국채", "10-year", "10년 금리"),
    "vix": ("VIX", "변동성지수", "변동성 지수"),
}


# Tolerance shape per fact group. Numeric verify imports these to
# compare body-extracted Decimal vs source-emitted Decimal.
#
# Values are absolute (Decimal-as-string) and *not* percentages
# (a tolerance of ``"0.01"`` for ``kospi_close`` means ±0.01 KOSPI
# index points, not 0.01%). Percent moves and yields carry their own
# narrower tolerances — see ``briefing/numeric_verify.py``.
CORE_FACT_TOLERANCE: Final[dict[CoreFact, str]] = {
    "kospi_close": "0.01",
    "kosdaq_close": "0.01",
    "spx_close": "0.01",
    "ndx_close": "0.01",
    "dji_close": "0.01",
    "btc_usd": "1",
    "eth_usd": "0.5",
    "usd_krw": "0.10",
    "us10y_yield": "0.01",
    "vix": "0.01",
}

# Flat-key prefix used inside ``NormalizedItem.raw_metadata`` for
# core-fact values. The shared ``_MetadataValue`` union (see
# ``models/items.py``) forbids nested dicts, so adapters emit one flat
# string-typed key per fact instead of a nested ``core_facts`` map.
CORE_FACT_METADATA_PREFIX: Final[str] = "core_fact:"


def is_core_fact(value: str) -> bool:
    """Return ``True`` iff ``value`` is one of the ten enum values.

    Adapters use this when registering ``raw_metadata["core_facts"]``
    keys to fail-fast on a typo rather than silently emitting a key the
    gate ignores.
    """
    return value in get_args(CoreFact)


def core_fact_metadata_key(fact: CoreFact) -> str:
    """Return the flat ``raw_metadata`` key for ``fact``."""
    return f"{CORE_FACT_METADATA_PREFIX}{fact}"


__all__ = [
    "CORE_FACT_KEYWORDS",
    "CORE_FACT_METADATA_PREFIX",
    "CORE_FACT_TOLERANCE",
    "CoreFact",
    "core_fact_metadata_key",
    "is_core_fact",
]
