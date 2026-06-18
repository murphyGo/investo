"""Tests for ``investo.sources.bea_macro_actuals.BeaMacroActualsAdapter``."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest

from investo.models.macro import macro_event_key, macro_event_status
from investo.sources._window import FetchWindow
from investo.sources.bea_macro_actuals import BeaMacroActualsAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "bea-macro-actuals"
_WINDOW = FetchWindow.from_kst_date(date(2026, 4, 30))
_SENTINEL_KEY = "BEA_SECRET_VALUE_DO_NOT_LEAK"


def _mock_client(
    fixtures: dict[str, bytes],
    captured: list[httpx.Request] | None = None,
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        table = request.url.params.get("TableName", "")
        body = fixtures.get(table, b'{"BEAAPI":{"Results":{"Data":[]}}}')
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_missing_bea_key_raises_terminal_without_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BEA_API_KEY", raising=False)
    seen: list[httpx.Request] = []
    adapter = BeaMacroActualsAdapter()

    async with _mock_client({}, captured=seen) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _WINDOW)

    assert exc_info.value.transient is False
    assert "BEA_API_KEY" in str(exc_info.value)
    assert seen == []


async def test_fetch_returns_gdp_and_pce_actuals_without_secret_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BEA_API_KEY", _SENTINEL_KEY)
    captured: list[httpx.Request] = []
    adapter = BeaMacroActualsAdapter()

    async with _mock_client(
        {
            "T10101": (_FIXTURE_DIR / "gdp.json").read_bytes(),
            "T20804": (_FIXTURE_DIR / "pce.json").read_bytes(),
        },
        captured=captured,
    ) as client:
        items = await adapter.fetch(client, _WINDOW)

    by_code = {item.raw_metadata["macro_event_label"]: item for item in items}
    gdp = by_code["Gross Domestic Product"]
    pce = by_code["Personal Consumption Expenditures"]
    assert captured[0].url.params["UserID"] == _SENTINEL_KEY
    assert _SENTINEL_KEY not in str(gdp.raw_metadata)
    assert gdp.raw_metadata["actual_value"] == "2.8"
    assert gdp.raw_metadata["prior_value"] == "3.1"
    assert gdp.raw_metadata["release_period"] == "2026Q1"
    assert macro_event_key(gdp) == "us:GDP:period=2026Q1"
    assert macro_event_status(gdp) == "actual"
    assert pce.raw_metadata["actual_value"] == "0.3"
    assert pce.raw_metadata["macro_event_key"] == "us:PCE:period=2026-05"
    assert pce.raw_metadata["macro_priority"] == "P1"
    assert "required_macro_actual" not in pce.raw_metadata
    assert "consensus" not in pce.raw_metadata
    assert "surprise" not in pce.raw_metadata


async def test_bea_error_payload_is_isolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BEA_API_KEY", _SENTINEL_KEY)
    adapter = BeaMacroActualsAdapter()

    async with _mock_client({"T10101": (_FIXTURE_DIR / "error.json").read_bytes()}) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert items == []


def test_bea_fixtures_do_not_contain_api_key() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in _FIXTURE_DIR.glob("*"))
    assert _SENTINEL_KEY not in text
    assert "UserID" not in text
