"""Tests for ``investo.sources.fsc_krx_stock_price``."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.fsc_krx_stock_price import FscKrxStockPriceAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "fsc-krx-stock-price"
_WINDOW = FetchWindow.from_kst_date(date(2026, 5, 7))


def _mock_client(fixtures: dict[tuple[str, str], bytes]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        ticker = request.url.params.get("likeSrtnCd", "")
        bas_dt = request.url.params.get("basDt", "")
        body = fixtures.get((ticker, bas_dt)) or _FIXTURE_DIR.joinpath("empty.json").read_bytes()
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_parses_configured_stock_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_KRX_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("INVESTO_KRX_STOCK_TICKERS", "005930,000660")
    adapter = FscKrxStockPriceAdapter()
    fixtures = {
        ("005930", "20260507"): (_FIXTURE_DIR / "005930-20260507.json").read_bytes(),
        ("000660", "20260507"): (_FIXTURE_DIR / "000660-20260507.json").read_bytes(),
    }
    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert [item.raw_metadata["ticker"] for item in items] == ["005930", "000660"]
    samsung = items[0]
    assert samsung.source_name == "fsc-krx-stock-price"
    assert samsung.category == "price"
    assert samsung.title == "삼성전자[005930] 72,000원 (+1.12%, +800)"
    assert samsung.published_at == datetime(2026, 5, 7, 7, 0, tzinfo=UTC)
    assert samsung.raw_metadata["market"] == "KOSPI"
    assert samsung.raw_metadata["close"] == "72000.000000"
    assert samsung.raw_metadata["source_date_lag_days"] == "0"
    assert str(samsung.url) == "https://www.data.go.kr/data/15094808/openapi.do"


async def test_missing_service_key_degrades_as_source_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INVESTO_KRX_SERVICE_KEY", raising=False)
    monkeypatch.delenv("INVESTO_DATA_GO_KR_SERVICE_KEY", raising=False)
    adapter = FscKrxStockPriceAdapter()
    async with _mock_client({}) as client:
        with pytest.raises(SourceFetchError, match="INVESTO_KRX_SERVICE_KEY"):
            await adapter.fetch(client, _WINDOW)


async def test_holiday_fallback_uses_latest_available_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_KRX_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("INVESTO_KRX_STOCK_TICKERS", "005930")
    adapter = FscKrxStockPriceAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    fixtures = {("005930", "20260507"): (_FIXTURE_DIR / "005930-20260507.json").read_bytes()}
    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].raw_metadata["bas_dt"] == "2026-05-07"
    assert items[0].raw_metadata["source_date_lag_days"] == "1"


async def test_invalid_ticker_isolated_from_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_KRX_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("INVESTO_KRX_STOCK_TICKERS", "005930,999999")
    adapter = FscKrxStockPriceAdapter()
    fixtures = {("005930", "20260507"): (_FIXTURE_DIR / "005930-20260507.json").read_bytes()}
    async with _mock_client(fixtures) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert [item.raw_metadata["ticker"] for item in items] == ["005930"]


async def test_data_go_kr_error_shape_raises_terminal_source_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_KRX_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("INVESTO_KRX_STOCK_TICKERS", "005930")
    error_body = b"""
    {
      "response": {
        "header": {"resultCode": "30", "resultMsg": "SERVICE KEY IS NOT REGISTERED"}
      }
    }
    """
    adapter = FscKrxStockPriceAdapter()
    async with _mock_client({("005930", "20260507"): error_body}) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _WINDOW)

    assert exc_info.value.transient is False
    assert "test-service-key" not in str(exc_info.value)
