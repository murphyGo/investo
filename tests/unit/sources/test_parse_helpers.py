"""Tests for the Wave 14 u77 shared source-adapter helpers.

Covers the four extracted helper families:

* ``investo.sources._parse`` — ``parse_json_response`` /
  ``required_str`` / ``parse_float`` / ``parse_int``.
* ``investo.sources._fanout`` — ``gather_with_error_isolation``.
* ``investo.sources._config`` — ``parse_rfc822_to_utc`` /
  ``parse_iso8601_to_utc``.
* ``investo.sources._xml_namespaces`` — ``ATOM_NS`` +
  Treasury dataservices constants.

These supplement (never replace) the unchanged per-adapter suites that
prove behavior preservation.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from investo.models import NormalizedItem
from investo.sources._config import parse_iso8601_to_utc, parse_rfc822_to_utc
from investo.sources._fanout import gather_with_error_isolation
from investo.sources._parse import (
    parse_float,
    parse_int,
    parse_json_response,
    required_str,
)
from investo.sources._xml_namespaces import (
    ATOM_NS,
    DATASERVICES_D_NS,
    DATASERVICES_M_NS,
)
from investo.sources.protocol import SourceFetchError


def _response(body: bytes) -> httpx.Response:
    return httpx.Response(200, content=body, request=httpx.Request("GET", "https://x"))


# --------------------------------------------------------------------------
# parse_json_response
# --------------------------------------------------------------------------


def test_parse_json_response_valid() -> None:
    payload = parse_json_response(_response(b'{"a": 1}'), source_name="s")
    assert payload == {"a": 1}


def test_parse_json_response_malformed_raises_terminal() -> None:
    with pytest.raises(SourceFetchError) as exc_info:
        parse_json_response(_response(b"not json"), source_name="binance")
    err = exc_info.value
    assert err.source_name == "binance"
    assert err.transient is False
    assert err.cause is not None
    assert "malformed JSON:" in str(err)


def test_parse_json_response_custom_message_appends_exc() -> None:
    with pytest.raises(SourceFetchError) as exc_info:
        parse_json_response(
            _response(b"oops"),
            source_name="yfinance",
            message="malformed JSON for AAPL",
        )
    assert "malformed JSON for AAPL:" in str(exc_info.value)


def test_parse_json_response_no_append_exc() -> None:
    with pytest.raises(SourceFetchError) as exc_info:
        parse_json_response(
            _response(b"oops"),
            source_name="dart",
            message="malformed JSON from endpoint",
            append_exc=False,
        )
    # No trailing ": <exc>" appended.
    assert str(exc_info.value).endswith("malformed JSON from endpoint")


# --------------------------------------------------------------------------
# required_str
# --------------------------------------------------------------------------


def test_required_str_valid_strips() -> None:
    assert required_str({"k": "  v  "}, "k") == "v"


def test_required_str_missing_raises() -> None:
    with pytest.raises(ValueError, match="missing k"):
        required_str({}, "k")


def test_required_str_empty_raises() -> None:
    with pytest.raises(ValueError, match="missing k"):
        required_str({"k": "   "}, "k")


def test_required_str_none_raises() -> None:
    with pytest.raises(ValueError, match="missing k"):
        required_str({"k": None}, "k")


# --------------------------------------------------------------------------
# parse_float / parse_int
# --------------------------------------------------------------------------


def test_parse_float_plain() -> None:
    assert parse_float("12.5") == 12.5


def test_parse_float_empty_raises() -> None:
    with pytest.raises(ValueError, match="missing float"):
        parse_float("")


def test_parse_float_none_raises() -> None:
    with pytest.raises(ValueError, match="missing float"):
        parse_float(None)


def test_parse_float_no_comma_strip_by_default() -> None:
    # binance contract: commas are NOT stripped → "1,000" is non-numeric.
    with pytest.raises(ValueError):
        parse_float("1,000")


def test_parse_float_strip_commas() -> None:
    assert parse_float("1,000.5", strip_commas=True) == 1000.5


def test_parse_int_via_float() -> None:
    assert parse_int("42.0") == 42


def test_parse_int_empty_raises() -> None:
    with pytest.raises(ValueError, match="missing int"):
        parse_int("")


def test_parse_int_strip_commas() -> None:
    assert parse_int("1,234", strip_commas=True) == 1234


def test_parse_int_no_strip_by_default() -> None:
    with pytest.raises(ValueError):
        parse_int("1,234")


# --------------------------------------------------------------------------
# gather_with_error_isolation
# --------------------------------------------------------------------------


def _item(name: str) -> NormalizedItem:
    return NormalizedItem(
        source_name=name,
        category="price",
        title="t",
        summary=None,
        url="https://example.com",
        published_at=datetime(2026, 5, 1, tzinfo=UTC),
        raw_metadata={},
    )


async def _ok() -> NormalizedItem | None:
    return _item("a")


async def _none() -> NormalizedItem | None:
    return None


async def _source_fail() -> NormalizedItem | None:
    raise SourceFetchError("a", "boom", transient=False)


async def _programmer_error() -> NormalizedItem | None:
    raise RuntimeError("bug")


@pytest.mark.asyncio
async def test_gather_keeps_items_skips_source_errors() -> None:
    items = await gather_with_error_isolation(
        [_ok(), _source_fail(), _none()],
        source_name="a",
    )
    assert len(items) == 1
    assert items[0].source_name == "a"


@pytest.mark.asyncio
async def test_gather_reraises_other_exceptions() -> None:
    with pytest.raises(RuntimeError, match="bug"):
        await gather_with_error_isolation([_ok(), _programmer_error()], source_name="a")


@pytest.mark.asyncio
async def test_gather_default_returns_empty_when_all_fail() -> None:
    items = await gather_with_error_isolation([_source_fail()], source_name="a")
    assert items == []


@pytest.mark.asyncio
async def test_gather_raise_if_all_failed_reraises_first() -> None:
    with pytest.raises(SourceFetchError, match="boom"):
        await gather_with_error_isolation(
            [_source_fail()],
            source_name="a",
            raise_if_all_failed=True,
        )


@pytest.mark.asyncio
async def test_gather_raise_if_all_failed_keeps_items_when_some_succeed() -> None:
    items = await gather_with_error_isolation(
        [_ok(), _source_fail()],
        source_name="a",
        raise_if_all_failed=True,
    )
    assert len(items) == 1


@pytest.mark.asyncio
async def test_gather_preserves_input_order() -> None:
    async def slow() -> NormalizedItem | None:
        await asyncio.sleep(0.01)
        return _item("slow")

    async def fast() -> NormalizedItem | None:
        return _item("fast")

    items = await gather_with_error_isolation([slow(), fast()], source_name="a")
    assert [i.source_name for i in items] == ["slow", "fast"]


# --------------------------------------------------------------------------
# parse_rfc822_to_utc
# --------------------------------------------------------------------------


def test_parse_rfc822_gmt() -> None:
    dt = parse_rfc822_to_utc("Fri, 24 Apr 2026 20:00:00 GMT")
    assert dt == datetime(2026, 4, 24, 20, 0, tzinfo=UTC)


def test_parse_rfc822_offset_converted_to_utc() -> None:
    dt = parse_rfc822_to_utc("Fri, 01 May 2026 10:35:20 -0400")
    assert dt == datetime(2026, 5, 1, 14, 35, 20, tzinfo=UTC)


def test_parse_rfc822_naive_raises() -> None:
    with pytest.raises(ValueError):
        parse_rfc822_to_utc("Fri, 01 May 2026 10:35:20")


def test_parse_rfc822_unparseable_raises() -> None:
    with pytest.raises(ValueError):
        parse_rfc822_to_utc("definitely not a date")


# --------------------------------------------------------------------------
# parse_iso8601_to_utc
# --------------------------------------------------------------------------


def test_parse_iso8601_z_suffix() -> None:
    dt = parse_iso8601_to_utc("2026-04-30T17:25:01.044Z")
    assert dt == datetime(2026, 4, 30, 17, 25, 1, 44000, tzinfo=UTC)


def test_parse_iso8601_offset() -> None:
    dt = parse_iso8601_to_utc("2026-04-30T13:25:01-04:00")
    assert dt == datetime(2026, 4, 30, 17, 25, 1, tzinfo=UTC)


def test_parse_iso8601_naive_raises() -> None:
    with pytest.raises(ValueError):
        parse_iso8601_to_utc("2026-04-30T17:25:00")


def test_parse_iso8601_unparseable_raises() -> None:
    with pytest.raises(ValueError):
        parse_iso8601_to_utc("nonsense")


# --------------------------------------------------------------------------
# XML namespace constants
# --------------------------------------------------------------------------


def test_xml_namespace_constants() -> None:
    assert ATOM_NS == "{http://www.w3.org/2005/Atom}"
    assert DATASERVICES_M_NS == ("{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}")
    assert DATASERVICES_D_NS == "{http://schemas.microsoft.com/ado/2007/08/dataservices}"
