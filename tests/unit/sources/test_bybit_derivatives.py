"""Tests for ``investo.sources.bybit_derivatives`` + OKX fallback (FD L6.15, u66).

Covers the Bybit-primary → OKX-fallback precedence and R10 four-path:

* success — recorded Bybit ``tickers.json`` yields funding + OI items
  with ``funding_source=bybit`` / ``oi_source=bybit``.
* Bybit failure → OKX fallback yields the same contract keys with
  ``*_source=okx`` from recorded OKX fixtures.
* empty/malformed Bybit → falls through to OKX; both empty → terminal.
* OKX adapter standalone success.

Also pins the u74 raw_metadata contract and R13 (no secret surface).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.bybit_derivatives import BybitDerivativesAdapter
from investo.sources.okx_derivatives import OkxDerivativesAdapter
from investo.sources.protocol import SourceFetchError

_BYBIT_DIR = Path(__file__).parent / "fixtures" / "api" / "bybit-derivatives"
_OKX_DIR = Path(__file__).parent / "fixtures" / "api" / "okx-derivatives"
_WINDOW = FetchWindow.from_kst_date(date(2026, 5, 23))


def _single(body: bytes, *, status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _routed(
    *,
    bybit_status: int,
    bybit_body: bytes,
) -> httpx.AsyncClient:
    """Route Bybit to a (possibly failing) response and OKX to recorded fixtures."""

    funding = (_OKX_DIR / "funding-rate.json").read_bytes()
    oi = (_OKX_DIR / "open-interest.json").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host == "api.bybit.com":
            return httpx.Response(
                bybit_status, content=bybit_body, headers={"content-type": "application/json"}
            )
        if "funding-rate" in request.url.path:
            return httpx.Response(
                200, content=funding, headers={"content-type": "application/json"}
            )
        if "open-interest" in request.url.path:
            return httpx.Response(200, content=oi, headers={"content-type": "application/json"})
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --------------------------------------------------------------------------
# Bybit primary success
# --------------------------------------------------------------------------


async def test_bybit_success_yields_funding_and_oi() -> None:
    adapter = BybitDerivativesAdapter()
    async with _single((_BYBIT_DIR / "tickers.json").read_bytes()) as client:
        items = await adapter.fetch(client, _WINDOW)
    by_ind = {i.raw_metadata["indicator"]: i for i in items}
    assert set(by_ind) == {"btc_funding", "btc_oi"}

    funding = by_ind["btc_funding"]
    assert funding.source_name == "bybit-derivatives"
    assert funding.category == "macro"
    assert funding.raw_metadata["btc_funding_rate"] == "0.00003545"
    assert funding.raw_metadata["funding_source"] == "bybit"

    oi = by_ind["btc_oi"]
    assert oi.raw_metadata["btc_oi_usd"] == "4103494620"
    assert oi.raw_metadata["oi_source"] == "bybit"
    assert all(isinstance(v, str) for v in oi.raw_metadata.values())


# --------------------------------------------------------------------------
# Bybit failure → OKX fallback
# --------------------------------------------------------------------------


async def test_bybit_4xx_falls_back_to_okx() -> None:
    adapter = BybitDerivativesAdapter()
    async with _routed(bybit_status=451, bybit_body=b"geo blocked") as client:
        items = await adapter.fetch(client, _WINDOW)
    by_ind = {i.raw_metadata["indicator"]: i for i in items}
    assert set(by_ind) == {"btc_funding", "btc_oi"}
    funding = by_ind["btc_funding"]
    assert funding.source_name == "okx-derivatives"
    assert funding.raw_metadata["funding_source"] == "okx"
    assert funding.raw_metadata["btc_funding_rate"] == "-0.0000258648920016"
    oi = by_ind["btc_oi"]
    assert oi.raw_metadata["oi_source"] == "okx"
    assert oi.raw_metadata["btc_oi_usd"] == "470195870"


async def test_bybit_empty_list_falls_back_to_okx() -> None:
    adapter = BybitDerivativesAdapter()
    async with _routed(
        bybit_status=200, bybit_body=(_BYBIT_DIR / "empty.json").read_bytes()
    ) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert {
        i.raw_metadata["funding_source"] for i in items if "funding_source" in i.raw_metadata
    } == {"okx"}


async def test_bybit_malformed_falls_back_to_okx() -> None:
    adapter = BybitDerivativesAdapter()
    async with _routed(
        bybit_status=200, bybit_body=(_BYBIT_DIR / "malformed.json").read_bytes()
    ) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert any(i.raw_metadata.get("oi_source") == "okx" for i in items)


# --------------------------------------------------------------------------
# Both fail → terminal
# --------------------------------------------------------------------------


async def test_both_fail_raises_terminal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.bybit.com":
            return httpx.Response(451, content=b"geo blocked")
        # OKX returns empty data arrays for both calls.
        return httpx.Response(
            200,
            content=b'{"code":"0","data":[],"msg":""}',
            headers={"content-type": "application/json"},
        )

    adapter = BybitDerivativesAdapter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceFetchError) as exc:
            await adapter.fetch(client, _WINDOW)
    assert "OKX fallback also failed" in str(exc.value)


# --------------------------------------------------------------------------
# OKX adapter standalone
# --------------------------------------------------------------------------


async def test_okx_adapter_standalone_success() -> None:
    funding = (_OKX_DIR / "funding-rate.json").read_bytes()
    oi = (_OKX_DIR / "open-interest.json").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        if "funding-rate" in request.url.path:
            return httpx.Response(
                200, content=funding, headers={"content-type": "application/json"}
            )
        return httpx.Response(200, content=oi, headers={"content-type": "application/json"})

    adapter = OkxDerivativesAdapter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await adapter.fetch(client, _WINDOW)
    by_ind = {i.raw_metadata["indicator"]: i for i in items}
    assert set(by_ind) == {"btc_funding", "btc_oi"}
    assert all(i.source_name == "okx-derivatives" for i in items)
    assert by_ind["btc_funding"].raw_metadata["funding_source"] == "okx"


async def test_okx_empty_raises_terminal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b'{"code":"0","data":[],"msg":""}',
            headers={"content-type": "application/json"},
        )

    adapter = OkxDerivativesAdapter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceFetchError) as exc:
            await adapter.fetch(client, _WINDOW)
    assert exc.value.transient is False


def test_class_attributes() -> None:
    assert BybitDerivativesAdapter.name == "bybit-derivatives"
    assert BybitDerivativesAdapter.category == "macro"
    assert OkxDerivativesAdapter.name == "okx-derivatives"
    assert OkxDerivativesAdapter.category == "macro"
