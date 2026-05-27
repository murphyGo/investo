"""Shared JSON-decode and numeric/string parse helpers for source adapters.

This module is the single home for the mechanical payload-parsing
patterns that were copy-pasted across many adapters (Wave 14 u77
extraction). It is internal to ``investo.sources`` — sibling units must
not import it.

Design choices / pins:

* ``parse_json_response`` consolidates the identical
  ``try: response.json() except json.JSONDecodeError`` boilerplate found
  in 15 adapters. The ``SourceFetchError`` it raises keeps the original
  ``source_name``, ``transient=False``, and ``cause`` so behavior is
  byte-identical. The two message shapes seen in the wild are supported
  via ``message`` + ``append_exc`` (some adapters appended ``": {exc}"``,
  others did not — e.g. DART / FRED name the resource only).
* ``required_str`` is the byte-identical ``_required_str`` shared by the
  binance / fsc_krx_index_price / fsc_krx_stock_price adapters.
* ``parse_float`` / ``parse_int`` unify ONLY the two truly-identical
  *raising* numeric parsers. binance does not strip commas; the two
  fsc_krx adapters do — the sole difference is comma handling, captured
  by ``strip_commas`` (default ``False`` reproduces binance byte-for-byte;
  ``strip_commas=True`` reproduces fsc_krx). The ``defillama`` (``float |
  None``, never raises) and ``krx_foreign_flows`` (``int | None``, comma)
  parsers encode DIFFERENT contracts and are intentionally NOT migrated
  here (see u77 plan Step 3).
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from investo.sources.protocol import SourceFetchError


def parse_json_response(
    response: httpx.Response,
    *,
    source_name: str,
    message: str = "malformed JSON",
    append_exc: bool = True,
) -> Any:
    """Decode ``response`` as JSON, raising ``SourceFetchError`` on failure.

    On :class:`json.JSONDecodeError` raises ``SourceFetchError`` with the
    given ``source_name``, ``transient=False``, and the decode error as
    ``cause``. When ``append_exc`` is true the exception text is appended
    to ``message`` as ``"{message}: {exc}"`` (the common shape); set it
    false for adapters that name only the resource (DART / FRED).
    """

    try:
        return response.json()
    except json.JSONDecodeError as exc:
        text = f"{message}: {exc}" if append_exc else message
        raise SourceFetchError(
            source_name=source_name,
            message=text,
            transient=False,
            cause=exc,
        ) from exc


def required_str(payload: dict[str, Any], key: str) -> str:
    """Return ``payload[key]`` as a non-empty stripped string, else raise.

    Reproduces the ``_required_str`` shared by binance / fsc_krx adapters:
    coerces ``None``/falsey to ``""`` before stripping and raises
    ``ValueError(f"missing {key}")`` when the result is empty.
    """

    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"missing {key}")
    return value


def parse_float(value: Any, *, strip_commas: bool = False) -> float:
    """Parse ``value`` to ``float``, raising ``ValueError`` when empty.

    Default (``strip_commas=False``) reproduces the binance parser; pass
    ``strip_commas=True`` for the comma-formatted fsc_krx values.
    """

    text = str(value or "").strip()
    if strip_commas:
        text = text.replace(",", "")
    if not text:
        raise ValueError("missing float")
    return float(text)


def parse_int(value: Any, *, strip_commas: bool = False) -> int:
    """Parse ``value`` to ``int`` (via ``float``), raising when empty.

    Default (``strip_commas=False``) reproduces the binance parser; pass
    ``strip_commas=True`` for the comma-formatted fsc_krx values.
    """

    text = str(value or "").strip()
    if strip_commas:
        text = text.replace(",", "")
    if not text:
        raise ValueError("missing int")
    return int(float(text))
