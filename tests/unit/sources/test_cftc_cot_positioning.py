"""Tests for ``investo.sources.cftc_cot_positioning``."""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.cftc_cot_positioning import (
    CftcCotPositioningAdapter,
    _estimated_release_date,
)
from investo.sources.protocol import SourceFetchError

_WINDOW = FetchWindow.from_kst_date(date(2026, 6, 18))


def _mock_client(
    *,
    tff_body: bytes = b"[]",
    disagg_body: bytes = b"[]",
    captured: list[httpx.Request] | None = None,
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        body = tff_body if request.url.path.endswith("/gpe5-46if.json") else disagg_body
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _tff_row(
    *,
    code: str = "13874A",
    label: str = "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
    report_date: str = "2026-06-09T00:00:00.000",
) -> str:
    return (
        "{"
        f'"market_and_exchange_names":"{label}",'
        f'"report_date_as_yyyy_mm_dd":"{report_date}",'
        '"contract_market_name":"E-MINI S&P 500",'
        f'"cftc_contract_market_code":"{code}",'
        '"open_interest_all":"2203164",'
        '"lev_money_positions_long":"168247",'
        '"lev_money_positions_short":"619833",'
        '"lev_money_positions_spread":"91726",'
        '"contract_units":"($50 X S&P 500 INDEX)"'
        "}"
    )


def _disagg_row(
    *,
    code: str = "067651",
    label: str = "WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE",
    report_date: str = "2026-06-09T00:00:00.000",
) -> str:
    return (
        "{"
        f'"market_and_exchange_names":"{label}",'
        f'"report_date_as_yyyy_mm_dd":"{report_date}",'
        f'"cftc_contract_market_code":"{code}",'
        '"open_interest_all":"2006635",'
        '"m_money_positions_long_all":"213483",'
        '"m_money_positions_short_all":"118758",'
        '"m_money_positions_spread":"272004",'
        '"contract_units":"(CONTRACTS OF 1,000 BARRELS)"'
        "}"
    )


async def test_fetch_returns_allowlisted_tff_and_disaggregated_positioning() -> None:
    adapter = CftcCotPositioningAdapter()
    captured: list[httpx.Request] = []

    async with _mock_client(
        tff_body=f"[{_tff_row()}]".encode(),
        disagg_body=f"[{_disagg_row()}]".encode(),
        captured=captured,
    ) as client:
        items = await adapter.fetch(client, _WINDOW)

    by_code = {item.raw_metadata["contract_code"]: item for item in items}
    assert set(by_code) == {"13874A", "067651"}
    assert len(captured) == 2
    assert "cftc_contract_market_code in(" in captured[0].url.params["$where"]
    spx = by_code["13874A"]
    assert spx.source_name == "cftc-cot-positioning"
    assert spx.category == "macro"
    assert spx.published_at == datetime(2026, 6, 12, 19, 30, tzinfo=UTC)
    assert spx.raw_metadata["report_kind"] == "tff"
    assert spx.raw_metadata["contract_label"] == "E-mini S&P 500"
    assert spx.raw_metadata["trader_category"] == "leveraged_money"
    assert spx.raw_metadata["as_of_date"] == "2026-06-09"
    assert spx.raw_metadata["release_date"] == "2026-06-12"
    assert spx.raw_metadata["net_contracts"] == "-451586"
    assert spx.raw_metadata["net_pct_open_interest"] == "-20.50"
    assert spx.raw_metadata["source_lag_days"] == "9"
    assert spx.raw_metadata["release_lag_days"] == "6"
    assert spx.raw_metadata["delayed_data_label"] == (
        "weekly CFTC report, Tuesday positions released Friday"
    )
    assert "not intraday flow" in spx.summary
    wti = by_code["067651"]
    assert wti.raw_metadata["report_kind"] == "disaggregated"
    assert wti.raw_metadata["trader_category"] == "managed_money"
    assert wti.raw_metadata["net_contracts"] == "94725"


async def test_unmapped_contracts_are_ignored() -> None:
    adapter = CftcCotPositioningAdapter()

    async with _mock_client(
        tff_body=f"[{_tff_row(code='999999', label='UNMAPPED - TEST')} ]".encode(),
    ) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert items == []


async def test_report_is_not_emitted_before_cftc_release_date() -> None:
    adapter = CftcCotPositioningAdapter()
    pre_release = FetchWindow.from_kst_date(date(2026, 6, 11))

    async with _mock_client(tff_body=f"[{_tff_row()}]".encode()) as client:
        items = await adapter.fetch(client, pre_release)

    assert items == []


async def test_report_is_not_emitted_before_release_time_on_release_day() -> None:
    adapter = CftcCotPositioningAdapter()
    before_release_time = FetchWindow(
        start_utc=datetime(2026, 6, 12, 0, 0, tzinfo=UTC),
        end_utc=datetime(2026, 6, 12, 19, 0, tzinfo=UTC),
        target_date=date(2026, 6, 12),
    )

    async with _mock_client(tff_body=f"[{_tff_row()}]".encode()) as client:
        items = await adapter.fetch(client, before_release_time)

    assert items == []


def test_release_date_estimate_handles_friday_holiday_delay() -> None:
    assert _estimated_release_date(date(2026, 6, 30)) == date(2026, 7, 6)


async def test_malformed_rows_are_dropped() -> None:
    adapter = CftcCotPositioningAdapter()

    async with _mock_client(tff_body=b'[{"cftc_contract_market_code":"13874A"}]') as client:
        items = await adapter.fetch(client, _WINDOW)

    assert items == []


async def test_source_error_payload_raises_fetch_error() -> None:
    adapter = CftcCotPositioningAdapter()

    async with _mock_client(tff_body=b'{"error":"bad"}') as client:
        with pytest.raises(SourceFetchError):
            await adapter.fetch(client, _WINDOW)


def test_source_config_excludes_paid_liquidation_and_netflow_providers() -> None:
    from investo.sources import cftc_cot_positioning

    text = "\n".join(
        [
            cftc_cot_positioning.__file__ or "",
            repr(cftc_cot_positioning._CONTRACTS),
            cftc_cot_positioning._TFF_ENDPOINT,
            cftc_cot_positioning._DISAGG_ENDPOINT,
        ]
    ).lower()
    for forbidden in ("coinglass", "cryptoquant", "glassnode", "liquidation", "netflow"):
        assert forbidden not in text
