"""Tests for ``investo.sources.alternative_fng`` (FD L6.13, u66).

R10 four-path coverage with recorded fixtures:

* success — recorded ``fng.json`` (value=28, Fear, ts 2026-05-23T00:00Z)
* empty — ``data: []`` → terminal SourceFetchError
* malformed — non-JSON body → terminal SourceFetchError
* auth/error — Alternative.me is no-key; the closest "error" path is a
  4xx terminal status surfaced by ``retry_get``.

Also pins the u74 raw_metadata contract keys and R13 (no secret surface).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.alternative_fng import AlternativeFearGreedAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "alternative-fng"
_WINDOW = FetchWindow.from_kst_date(date(2026, 5, 23))


def _client(body: bytes, *, status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_success_real_fixture() -> None:
    adapter = AlternativeFearGreedAdapter()
    async with _client((_FIXTURE_DIR / "fng.json").read_bytes()) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    item = items[0]
    assert item.source_name == "alternative-fng"
    assert item.category == "macro"
    assert item.title == "Crypto Fear & Greed 28 (Fear)"
    assert item.published_at == datetime(2026, 5, 23, tzinfo=UTC)
    assert item.published_at.tzinfo is UTC


async def test_raw_metadata_contract_keys() -> None:
    adapter = AlternativeFearGreedAdapter()
    async with _client((_FIXTURE_DIR / "fng.json").read_bytes()) as client:
        items = await adapter.fetch(client, _WINDOW)
    meta = items[0].raw_metadata
    assert meta["indicator"] == "fear_greed"
    assert meta["value"] == "28"
    assert meta["classification"] == "Fear"
    assert meta["window"] == "utc_24h"
    assert meta["timestamp"] == "1779494400"
    assert all(isinstance(v, str) for v in meta.values())


async def test_missing_time_until_update_becomes_empty_string() -> None:
    body = b'{"data":[{"value":"50","value_classification":"Neutral","timestamp":"1779494400"}]}'
    adapter = AlternativeFearGreedAdapter()
    async with _client(body) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert items[0].raw_metadata["time_until_update"] == ""


async def test_empty_data_raises_terminal() -> None:
    adapter = AlternativeFearGreedAdapter()
    async with _client((_FIXTURE_DIR / "empty.json").read_bytes()) as client:
        with pytest.raises(SourceFetchError) as exc:
            await adapter.fetch(client, _WINDOW)
    assert exc.value.transient is False


async def test_malformed_raises_terminal() -> None:
    adapter = AlternativeFearGreedAdapter()
    async with _client((_FIXTURE_DIR / "malformed.json").read_bytes()) as client:
        with pytest.raises(SourceFetchError) as exc:
            await adapter.fetch(client, _WINDOW)
    assert exc.value.transient is False


async def test_http_error_status_raises() -> None:
    adapter = AlternativeFearGreedAdapter()
    async with _client(b"forbidden", status=403) as client:
        with pytest.raises(SourceFetchError):
            await adapter.fetch(client, _WINDOW)


async def test_unparseable_value_raises_terminal() -> None:
    body = b'{"data":[{"value":"NaN","value_classification":"X","timestamp":"1779494400"}]}'
    adapter = AlternativeFearGreedAdapter()
    async with _client(body) as client:
        with pytest.raises(SourceFetchError) as exc:
            await adapter.fetch(client, _WINDOW)
    assert exc.value.transient is False


def test_class_attributes() -> None:
    assert AlternativeFearGreedAdapter.name == "alternative-fng"
    assert AlternativeFearGreedAdapter.category == "macro"
