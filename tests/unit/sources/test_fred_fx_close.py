"""Contract tests for the FRED DEXKOUS price adapter."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from investo.models.core_fact import core_fact_metadata_key
from investo.orchestrator.domestic_anchor_quarantine import (
    candidate_from_item,
    classify_domestic_anchor_candidate,
)
from investo.sources._window import FetchWindow
from investo.sources.fred_fx_close import FredFxCloseAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE = Path(__file__).parent / "fixtures" / "api" / "fred-fx-close" / "DEXKOUS.json"
_SENTINEL_KEY = "REDACTED_KEY_VALUE_12345"


def _payload() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


async def _fetch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    target_date: date,
    body: bytes | None = None,
    payload: Any | None = None,
) -> tuple[list, list[httpx.Request]]:
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if body is not None:
            return httpx.Response(200, content=body)
        return httpx.Response(200, json=_payload() if payload is None else payload)

    window = FetchWindow.from_kst_date(target_date)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await FredFxCloseAdapter().fetch(client, window)
    return items, requests


def test_class_attributes() -> None:
    assert FredFxCloseAdapter.name == "fred-fx-close"
    assert FredFxCloseAdapter.category == "price"


@pytest.mark.parametrize("value", [None, "", "   "])
async def test_missing_key_is_terminal_without_http_or_secret_leak(
    monkeypatch: pytest.MonkeyPatch,
    value: str | None,
) -> None:
    if value is None:
        monkeypatch.delenv("FRED_API_KEY", raising=False)
    else:
        monkeypatch.setenv("FRED_API_KEY", value)
    called = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    with pytest.raises(SourceFetchError) as exc_info:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await FredFxCloseAdapter().fetch(
                client,
                FetchWindow.from_kst_date(date(2026, 7, 10)),
            )

    assert called is False
    assert exc_info.value.source_name == "fred-fx-close"
    assert exc_info.value.transient is False
    assert "FRED_API_KEY" in str(exc_info.value)
    assert _SENTINEL_KEY not in str(exc_info.value)


async def test_recorded_observation_emits_krw_per_usd_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    items, requests = await _fetch(monkeypatch, target_date=date(2026, 7, 10))

    assert len(requests) == 1
    assert dict(requests[0].url.params) == {
        "series_id": "DEXKOUS",
        "api_key": _SENTINEL_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": "16",
    }
    assert len(items) == 1
    item = items[0]
    assert str(item.url) == "https://fred.stlouisfed.org/series/DEXKOUS"
    assert item.published_at == datetime(2026, 7, 10, 16, 0, tzinfo=UTC)
    assert item.raw_metadata == {
        "ticker": "KRW=X",
        "series_id": "DEXKOUS",
        "close": "1501.060000",
        "previous_close": "1508.760000",
        "source_date": "2026-07-10",
        "provenance": "fred-h10",
        core_fact_metadata_key("usd_krw"): "1501.060000",
    }
    assert _SENTINEL_KEY not in str(item.model_dump())


async def test_placeholder_falls_through_to_prior_valid_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "observations": [
            {"date": "2026-07-10", "value": "."},
            {"date": "2026-07-09", "value": "1508.76"},
            {"date": "2026-07-08", "value": "1510.10"},
        ]
    }

    items, _ = await _fetch(monkeypatch, target_date=date(2026, 7, 10), payload=payload)

    assert items[0].raw_metadata["source_date"] == "2026-07-09"
    assert items[0].raw_metadata["close"] == "1508.760000"
    assert items[0].raw_metadata["previous_close"] == "1510.100000"
    candidate = candidate_from_item(items[0])
    assert candidate is not None
    assert (
        classify_domestic_anchor_candidate(
            candidate,
            target_date=date(2026, 7, 10),
        )
        == "trusted"
    )


async def test_observation_older_than_seven_days_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    items, _ = await _fetch(monkeypatch, target_date=date(2026, 7, 18))

    assert items == []


async def test_future_observation_is_ignored_for_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "observations": [
            {"date": "2026-07-11", "value": "1600.00"},
            {"date": "2026-07-10", "value": "1501.06"},
        ]
    }

    items, _ = await _fetch(monkeypatch, target_date=date(2026, 7, 10), payload=payload)

    assert items[0].raw_metadata["close"] == "1501.060000"
    assert "previous_close" not in items[0].raw_metadata


async def test_non_finite_observation_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "observations": [
            {"date": "2026-07-10", "value": "NaN"},
            {"date": "2026-07-09", "value": "1508.76"},
        ]
    }

    items, _ = await _fetch(monkeypatch, target_date=date(2026, 7, 10), payload=payload)

    assert items[0].raw_metadata["source_date"] == "2026-07-09"
    assert items[0].raw_metadata["close"] == "1508.760000"


async def test_malformed_json_is_terminal_source_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(SourceFetchError) as exc_info:
        await _fetch(monkeypatch, target_date=date(2026, 7, 10), body=b"not-json")

    assert exc_info.value.source_name == "fred-fx-close"
    assert exc_info.value.transient is False
    assert "malformed JSON for DEXKOUS" in str(exc_info.value)
    assert _SENTINEL_KEY not in str(exc_info.value)
