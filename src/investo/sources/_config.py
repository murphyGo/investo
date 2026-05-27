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

import math
import os
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
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


def format_float(value: float, *, precision: int = 6) -> str:
    """Format raw-metadata floats consistently across source adapters.

    R8 requires ``raw_metadata`` values to be strings; R9 needs stable
    serialization for idempotence. Rejecting NaN/inf keeps non-finite
    upstream payloads from leaking inconsistent platform spellings into
    downstream prompts.
    """

    if not math.isfinite(value):
        raise ValueError(f"non-finite numeric value: {value!r}")
    return f"{value:.{precision}f}"


def format_int(value: int) -> str:
    """Format integer raw-metadata values consistently."""

    return str(value)


def parse_rfc822_to_utc(text: str) -> datetime:
    """Parse an RFC-822 ``pubDate`` string to a tz-aware UTC datetime.

    Used by the RSS adapters (FOMC RSS, The Block, Yonhap). The input is
    expected to carry a timezone (``GMT``/``+0900``/``-0400``);
    :func:`email.utils.parsedate_to_datetime` returns a tz-aware datetime
    in that case. A ``None`` or naive result indicates a malformed input
    and raises :class:`ValueError` — callers that prefer to drop the
    entry catch ``(TypeError, ValueError)`` and skip it (per R8: reject
    naive timestamps rather than assume UTC).
    """

    parsed = parsedate_to_datetime(text)
    if parsed is None or parsed.tzinfo is None:
        raise ValueError(f"naive or unparseable RFC-822 date: {text!r}")
    return parsed.astimezone(UTC)


def parse_iso8601_to_utc(text: str) -> datetime:
    """Parse an ISO-8601 string to a tz-aware UTC datetime.

    Used by CoinGecko (``last_updated`` with millisecond precision and a
    trailing ``Z``, accepted by ``fromisoformat`` on Python 3.11+). A
    naive result raises :class:`ValueError` (per R8) so callers can drop
    the entry rather than silently assume UTC.
    """

    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError(f"naive ISO-8601 datetime: {text!r}")
    return parsed.astimezone(UTC)
