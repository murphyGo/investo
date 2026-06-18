"""Tests for ``investo.sources.eia_petroleum_weekly``."""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest

from investo._internal.redaction import SECRET_ENV_VARS, RedactionPolicy, redact_text
from investo.sources._window import FetchWindow
from investo.sources.eia_petroleum_weekly import (
    EiaPetroleumWeeklyAdapter,
    _estimated_wpsr_release_date,
)

_WINDOW = FetchWindow.from_kst_date(date(2026, 6, 18))
_SENTINEL_KEY = "EIA_SECRET_VALUE_DO_NOT_LEAK"


def _mock_client(
    fixtures: dict[str, bytes],
    captured: list[httpx.Request] | None = None,
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        series = request.url.params.get("facets[series][]", "")
        body = fixtures.get(series, b'{"response":{"data":[]}}')
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _payload(
    series: str,
    description: str,
    value: str,
    units: str,
    *,
    period: str = "2026-06-12",
) -> bytes:
    return (
        '{"response":{"data":[{'
        f'"period":"{period}",'
        f'"series":"{series}",'
        f'"series-description":"{description}",'
        f'"value":"{value}",'
        f'"units":"{units}"'
        "}]}}"
    ).encode()


async def test_fetch_returns_weekly_petroleum_facts_with_lag_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EIA_API_KEY", _SENTINEL_KEY)
    captured: list[httpx.Request] = []
    adapter = EiaPetroleumWeeklyAdapter()

    async with _mock_client(
        {
            "WCESTUS1": _payload(
                "WCESTUS1",
                "U.S. Ending Stocks excluding SPR of Crude Oil (Thousand Barrels)",
                "418222",
                "MBBL",
            ),
            "WPULEUS3": _payload(
                "WPULEUS3",
                "U.S. Percent Utilization of Refinery Operable Capacity",
                "96.7",
                "PCT",
            ),
        },
        captured=captured,
    ) as client:
        items = await adapter.fetch(client, _WINDOW)

    by_series = {item.raw_metadata["series_id"]: item for item in items}
    assert set(by_series) == {"WCESTUS1", "WPULEUS3"}
    crude = by_series["WCESTUS1"]
    assert captured[0].url.params["api_key"] == _SENTINEL_KEY
    assert _SENTINEL_KEY not in str(crude.raw_metadata)
    assert crude.source_name == "eia-petroleum-weekly"
    assert crude.category == "macro"
    assert crude.published_at == datetime(2026, 6, 17, 14, 30, tzinfo=UTC)
    assert crude.raw_metadata["release_date"] == "2026-06-17"
    assert crude.raw_metadata["as_of_date"] == "2026-06-12"
    assert crude.raw_metadata["value"] == "418222.000000"
    assert crude.raw_metadata["units"] == "MBBL"
    assert crude.raw_metadata["source_lag_days"] == "6"
    assert crude.raw_metadata["release_lag_days"] == "1"
    assert crude.raw_metadata["data_frequency"] == "weekly"
    assert crude.raw_metadata["api_key_mode"] == "EIA_API_KEY"
    assert (
        crude.raw_metadata["delayed_data_label"] == "weekly EIA petroleum status data, not intraday"
    )
    assert "not current-session data" in crude.summary


async def test_missing_key_uses_official_demo_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    captured: list[httpx.Request] = []
    adapter = EiaPetroleumWeeklyAdapter()

    async with _mock_client(
        {"WCESTUS1": _payload("WCESTUS1", "Crude stocks", "418222", "MBBL")},
        captured=captured,
    ) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert captured[0].url.params["api_key"] == "DEMO_KEY"
    assert items[0].raw_metadata["api_key_mode"] == "DEMO_KEY"


async def test_week_ending_row_is_not_emitted_before_wpsr_release_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    adapter = EiaPetroleumWeeklyAdapter()
    pre_release_window = FetchWindow.from_kst_date(date(2026, 6, 16))

    async with _mock_client(
        {"WCESTUS1": _payload("WCESTUS1", "Crude stocks", "418222", "MBBL")}
    ) as client:
        items = await adapter.fetch(client, pre_release_window)

    assert items == []


def test_wpsr_release_estimate_handles_monday_holiday_delay() -> None:
    # Week ending 2026-05-22 is followed by Memorial Day on Monday
    # 2026-05-25, so Wednesday 2026-05-27 is not a safe public date.
    assert _estimated_wpsr_release_date(date(2026, 5, 22)) == date(2026, 5, 28)


async def test_eia_error_payload_is_isolated() -> None:
    adapter = EiaPetroleumWeeklyAdapter()

    async with _mock_client(
        {"WCESTUS1": b'{"error":{"code":"API_KEY_MISSING","message":"missing"}}'}
    ) as client:
        items = await adapter.fetch(client, _WINDOW)

    assert items == []


def test_eia_key_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EIA_API_KEY", _SENTINEL_KEY)

    assert "EIA_API_KEY" in SECRET_ENV_VARS
    assert _SENTINEL_KEY not in redact_text(
        f"failed with key {_SENTINEL_KEY}",
        policy=RedactionPolicy.STRICT,
    )


def test_default_series_exclude_restricted_fred_ice_bofa_series() -> None:
    from investo.sources import eia_petroleum_weekly

    text = "\n".join(
        [
            eia_petroleum_weekly.__file__ or "",
            repr(eia_petroleum_weekly._SERIES_CONFIGS),
        ]
    )
    assert "BAML" not in text
    assert "ICE BofA" not in text
