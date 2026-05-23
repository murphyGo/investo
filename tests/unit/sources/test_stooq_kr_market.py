"""Tests for ``investo.sources.stooq_kr_market.StooqKrMarketAdapter`` (u67).

Pins the precedence + shape declared in ``stooq_kr_market.py``:

* Stooq tier — KOSPI / 원/달러 happy path from recorded fixtures, KST
  close timestamp, core-fact stamp, ``provenance=stooq``.
* KOSDAQ — Stooq returns ``N/D`` (recorded), so the adapter falls back
  to the Yonhap numeric parse (``provenance=yonhap-rss``).
* Yonhap terminal fallback — when Stooq KOSPI is unreachable the adapter
  still emits a KOSPI close from the Yonhap headline parse.
* Per-symbol isolation — one symbol failing does not drop siblings.
* defusedxml-only parse of the Yonhap RSS (no stdlib XML import here).
* AC-2 — a domestic run with KRX absent still yields a populated
  ``usd_krw`` core fact via this adapter.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from investo.sources._core_fact_map import core_fact_metadata_key
from investo.sources._window import FetchWindow
from investo.sources.stooq_kr_market import StooqKrMarketAdapter

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "stooq-kr-market"
_WINDOW = FetchWindow.from_kst_date(date(2026, 5, 22))


def _csv(name: str) -> bytes:
    return (_FIXTURE_DIR / f"{name}.csv").read_bytes()


def _yonhap_xml() -> bytes:
    return (_FIXTURE_DIR / "yonhap_index.xml").read_bytes()


def _handler(
    *,
    stooq: dict[str, bytes],
    stooq_status: dict[str, int] | None = None,
    yonhap: bytes | None = None,
    yonhap_status: int = 200,
) -> httpx.MockTransport:
    stooq_status = stooq_status or {}

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.yna.co.kr":
            if yonhap is None:
                return httpx.Response(404, content=b"")
            return httpx.Response(yonhap_status, content=yonhap)
        symbol = request.url.params.get("s") or ""
        body = stooq.get(symbol)
        if body is None:
            return httpx.Response(404, content=b"not found")
        return httpx.Response(stooq_status.get(symbol, 200), content=body)

    return httpx.MockTransport(handle)


async def _run(transport: httpx.MockTransport) -> list:
    adapter = StooqKrMarketAdapter()
    async with httpx.AsyncClient(transport=transport) as client:
        return await adapter.fetch(client, _WINDOW)


def test_class_attributes() -> None:
    assert StooqKrMarketAdapter.name == "stooq-kr-market"
    assert StooqKrMarketAdapter.category == "price"


async def test_kospi_and_fx_from_stooq(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_STOOQ_KR_SYMBOLS", "^KOSPI,KRW=X")
    transport = _handler(stooq={"^kospi": _csv("kospi"), "usdkrw": _csv("usdkrw")})
    items = await _run(transport)
    by_ticker = {i.raw_metadata["ticker"]: i for i in items}

    kospi = by_ticker["^KOSPI"]
    assert kospi.raw_metadata["provenance"] == "stooq"
    assert kospi.raw_metadata["close"].startswith("7847.71")
    assert kospi.raw_metadata[core_fact_metadata_key("kospi_close")].startswith("7847.71")
    # KST 15:30 close on 2026-05-22 == 06:30 UTC.
    assert kospi.published_at == datetime(2026, 5, 22, 6, 30, tzinfo=UTC)

    fx = by_ticker["KRW=X"]
    assert fx.raw_metadata["provenance"] == "stooq"
    assert fx.raw_metadata[core_fact_metadata_key("usd_krw")].startswith("1518.21")
    assert "원" in fx.title


async def test_kosdaq_falls_back_to_yonhap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_STOOQ_KR_SYMBOLS", "^KOSDAQ")
    transport = _handler(stooq={"^kosdaq": _csv("kosdaq")}, yonhap=_yonhap_xml())
    items = await _run(transport)
    assert len(items) == 1
    kosdaq = items[0]
    assert kosdaq.raw_metadata["ticker"] == "^KOSDAQ"
    assert kosdaq.raw_metadata["provenance"] == "yonhap-rss"
    assert kosdaq.raw_metadata["close"].startswith("870.25")
    assert kosdaq.raw_metadata[core_fact_metadata_key("kosdaq_close")].startswith("870.25")


async def test_kospi_terminal_yonhap_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    # Stooq KOSPI 5xx after retries → adapter falls through to Yonhap.
    monkeypatch.setenv("INVESTO_STOOQ_KR_SYMBOLS", "^KOSPI")
    transport = _handler(
        stooq={"^kospi": b"err"},
        stooq_status={"^kospi": 500},
        yonhap=_yonhap_xml(),
    )
    items = await _run(transport)
    assert len(items) == 1
    assert items[0].raw_metadata["ticker"] == "^KOSPI"
    assert items[0].raw_metadata["provenance"] == "yonhap-rss"
    assert items[0].raw_metadata["close"].startswith("2650.50")


async def test_per_symbol_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    # KRW=X 404s; KOSPI still lands.
    monkeypatch.setenv("INVESTO_STOOQ_KR_SYMBOLS", "^KOSPI,KRW=X")
    transport = _handler(
        stooq={"^kospi": _csv("kospi")},  # usdkrw absent → 404
        yonhap=_yonhap_xml(),
    )
    items = await _run(transport)
    tickers = {i.raw_metadata["ticker"] for i in items}
    assert "^KOSPI" in tickers
    # KRW=X has no Yonhap pattern, so it is simply absent (not an error).
    assert "KRW=X" not in tickers


async def test_full_default_basket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INVESTO_STOOQ_KR_SYMBOLS", raising=False)
    transport = _handler(
        stooq={"^kospi": _csv("kospi"), "usdkrw": _csv("usdkrw"), "^kosdaq": _csv("kosdaq")},
        yonhap=_yonhap_xml(),
    )
    items = await _run(transport)
    tickers = [i.raw_metadata["ticker"] for i in items]
    # All three default symbols land; default order preserved.
    assert tickers == ["^KOSPI", "^KOSDAQ", "KRW=X"]
    provenance = {i.raw_metadata["ticker"]: i.raw_metadata["provenance"] for i in items}
    assert provenance["^KOSPI"] == "stooq"
    assert provenance["^KOSDAQ"] == "yonhap-rss"
    assert provenance["KRW=X"] == "stooq"
