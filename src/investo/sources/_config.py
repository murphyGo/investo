"""Shared env-var symbol-list parser for source adapters (FD R12).

Adapters that expose user-configurable symbol / coin / series lists
(yfinance tickers, CoinGecko coin ids, FRED series ids) read those
lists from environment variables following the
``INVESTO_<ADAPTER>_<NOUN>`` naming convention defined in
``aidlc-docs/construction/u1-sources/functional-design/business-rules.md``
R12.

This module is the single shared parsing path so adapters can't drift
on whitespace handling, empty-token policy, or fall-through-to-default
semantics. It is internal to ``investo.sources`` — sibling units must
not import it.

Behaviour summary (R12):

* env var unset / empty / yields zero non-empty tokens → return
  ``defaults`` (the fail-safe; adapters always have a working
  configuration).
* otherwise → return the comma-split, whitespace-stripped, non-empty
  tokens as a tuple.
* case is preserved (Yahoo tickers like ``^GSPC`` are case-sensitive).

The function never raises on parse failure — defaults are the
fail-safe.
"""

from __future__ import annotations

import os
from typing import Final

# Per-item summary truncation cap (R8 NormalizedItem field rules — keeps LLM prompt bounded).
SUMMARY_MAX_LEN: Final[int] = 280


def parse_symbol_list(env_var_name: str, defaults: tuple[str, ...]) -> tuple[str, ...]:
    """Read a comma-separated symbol list from ``env_var_name``.

    Returns the parsed tuple, or ``defaults`` when the env var is
    unset, empty, or yields zero non-empty tokens after parsing.

    See module docstring for the full R12 behaviour contract.
    """

    raw = os.environ.get(env_var_name, "")
    tokens = tuple(stripped for token in raw.split(",") if (stripped := token.strip()))
    if not tokens:
        return defaults
    return tokens
