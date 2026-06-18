"""Tests for ``investo.sources.bls_macro_actuals.BlsMacroActualsAdapter``."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx

from investo.models.macro import macro_event_key, macro_event_status, macro_prompt_payload
from investo.sources._window import FetchWindow
from investo.sources.bls_macro_actuals import BlsMacroActualsAdapter

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "bls-macro-actuals"
_WINDOW = FetchWindow.from_kst_date(date(2026, 6, 10))


def _mock_client(fixtures: dict[str, bytes]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        series_id = request.url.path.rstrip("/").split("/")[-1]
        body = fixtures.get(series_id, (_FIXTURE_DIR / "empty.json").read_bytes())
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_returns_official_cpi_and_payroll_actuals() -> None:
    adapter = BlsMacroActualsAdapter()

    async with _mock_client(
        {
            "CUSR0000SA0": (_FIXTURE_DIR / "CUSR0000SA0.json").read_bytes(),
            "CES0000000001": (_FIXTURE_DIR / "CES0000000001.json").read_bytes(),
        }
    ) as client:
        items = await adapter.fetch(client, _WINDOW)

    by_series = {item.raw_metadata["series_id"]: item for item in items}
    cpi = by_series["CUSR0000SA0"]
    payrolls = by_series["CES0000000001"]
    assert cpi.source_name == "bls-macro-actuals"
    assert cpi.category == "macro"
    assert cpi.raw_metadata["actual_value"] == "333.979"
    assert cpi.raw_metadata["prior_value"] == "332.407"
    assert cpi.raw_metadata["release_period"] == "2026-05"
    assert macro_event_key(cpi) == "us:CPI:period=2026-05"
    assert macro_event_status(cpi) == "actual"
    assert cpi.raw_metadata["macro_priority"] == "P1"
    assert "required_macro_actual" not in cpi.raw_metadata
    assert macro_prompt_payload(cpi) is not None
    assert payrolls.raw_metadata["actual_value"] == "159001"
    assert "consensus" not in payrolls.raw_metadata
    assert "surprise" not in payrolls.raw_metadata


async def test_empty_bls_payload_degrades_to_no_items() -> None:
    adapter = BlsMacroActualsAdapter()

    async with _mock_client({"CUSR0000SA0": (_FIXTURE_DIR / "empty.json").read_bytes()}) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert items == []


async def test_malformed_bls_payload_is_isolated() -> None:
    adapter = BlsMacroActualsAdapter()

    async with _mock_client({"CUSR0000SA0": b"{bad"}) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert items == []


async def test_malformed_bls_row_is_dropped() -> None:
    adapter = BlsMacroActualsAdapter()
    malformed_row = (
        b'{"status":"REQUEST_SUCCEEDED","Results":{"series":[{"seriesID":"CUSR0000SA0",'
        b'"data":[{"year":"bad","period":"M05","value":"333.979"}]}]}}'
    )

    async with _mock_client({"CUSR0000SA0": malformed_row}) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert items == []


async def test_stale_bls_period_is_filtered() -> None:
    adapter = BlsMacroActualsAdapter()
    stale_window = FetchWindow.from_kst_date(date(2026, 12, 31))

    async with _mock_client(
        {"CUSR0000SA0": (_FIXTURE_DIR / "CUSR0000SA0.json").read_bytes()}
    ) as client:
        items = await adapter.fetch(client, stale_window)

    assert items == []


def test_bls_fixture_does_not_contain_secret_shapes() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in _FIXTURE_DIR.glob("*"))
    assert "api_key" not in text.lower()
    assert "BEA_API_KEY" not in text
    assert "FRED_API_KEY" not in text
