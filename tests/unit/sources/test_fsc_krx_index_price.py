"""Tests for ``investo.sources.fsc_krx_index_price``."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.fsc_krx_index_price import FscKrxIndexPriceAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "fsc-krx-index-price"
_WINDOW = FetchWindow.from_kst_date(date(2026, 5, 7))


def _mock_client(fixtures_by_date: dict[str, bytes]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        bas_dt = request.url.params.get("basDt", "")
        body = fixtures_by_date.get(bas_dt) or _FIXTURE_DIR.joinpath("empty.json").read_bytes()
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_parses_official_index_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_KRX_SERVICE_KEY", "test-service-key")
    adapter = FscKrxIndexPriceAdapter()
    async with _mock_client({"20260507": (_FIXTURE_DIR / "20260507.json").read_bytes()}) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert [item.raw_metadata["index_name"] for item in items] == ["코스피", "코스닥", "코스피 200"]
    kospi = items[0]
    assert kospi.source_name == "fsc-krx-index-price"
    assert kospi.category == "price"
    assert kospi.title == "코스피 2,730.34 (+0.79%, +21.44)"
    assert kospi.summary is not None
    assert "거래대금:11,628,200,000,000" in kospi.summary
    assert kospi.published_at == datetime(2026, 5, 7, 7, 0, tzinfo=UTC)
    assert kospi.raw_metadata["close"] == "2730.340000"
    assert kospi.raw_metadata["pct_change"] == "0.790000"
    assert kospi.raw_metadata["source_date_lag_days"] == "0"
    assert str(kospi.url) == "https://www.data.go.kr/data/15094807/openapi.do"


async def test_missing_service_key_degrades_as_source_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INVESTO_KRX_SERVICE_KEY", raising=False)
    monkeypatch.delenv("INVESTO_DATA_GO_KR_SERVICE_KEY", raising=False)
    adapter = FscKrxIndexPriceAdapter()
    async with _mock_client({"20260507": (_FIXTURE_DIR / "20260507.json").read_bytes()}) as client:
        with pytest.raises(SourceFetchError, match="INVESTO_KRX_SERVICE_KEY"):
            await adapter.fetch(client, _WINDOW)


async def test_holiday_fallback_uses_latest_available_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_KRX_SERVICE_KEY", "test-service-key")
    adapter = FscKrxIndexPriceAdapter()
    window = FetchWindow.from_kst_date(date(2026, 5, 8))
    async with _mock_client({"20260507": (_FIXTURE_DIR / "20260507.json").read_bytes()}) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 3
    assert items[0].raw_metadata["bas_dt"] == "2026-05-07"
    assert items[0].raw_metadata["source_date_lag_days"] == "1"


async def test_malformed_numeric_row_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVESTO_KRX_SERVICE_KEY", "test-service-key")
    malformed = """
    {
      "response": {
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
        "body": {"items": {"item": {
          "basDt": "20260507",
          "idxNm": "\ucf54\uc2a4\ud53c",
          "clpr": "not-a-number",
          "vs": "1",
          "fltRt": "0.1",
          "mkp": "1",
          "hipr": "1",
          "lopr": "1",
          "trqu": "1",
          "trPrc": "1",
          "lstgMrktTotAmt": "1"
        }}}
      }
    }
    """.encode()
    adapter = FscKrxIndexPriceAdapter()
    async with _mock_client({"20260507": malformed}) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert items == []


async def test_data_go_kr_error_shape_raises_terminal_source_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_KRX_SERVICE_KEY", "test-service-key")
    error_body = b"""
    {
      "response": {
        "header": {"resultCode": "30", "resultMsg": "SERVICE KEY IS NOT REGISTERED"}
      }
    }
    """
    adapter = FscKrxIndexPriceAdapter()
    async with _mock_client({"20260507": error_body}) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _WINDOW)

    assert exc_info.value.transient is False
    assert "test-service-key" not in str(exc_info.value)
