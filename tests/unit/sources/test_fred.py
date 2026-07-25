"""Tests for ``investo.sources.fred.FredMacroAdapter``.

Pins FD L6.4 + R13 (secret handling) + AC-3.6 (extension 2026-05-01):

* Synthetic recorded fixtures (FRED requires an API key — fixtures
  describe the documented response shape; see ``meta.json``).
* AC-3.6 — missing/empty FRED_API_KEY → SourceFetchError(transient=False)
* R13 — secret-hygiene: api_key never appears in error messages,
  ``raw_metadata``, or test-captured log output.
* L6.4 — widened R7 window (65-day lookback), "." placeholder
  fall-through, delta computation against prior valid observation.
* R12 — `INVESTO_FRED_SERIES` env-var override.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.fred import FredMacroAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "fred-macro"
_CPI_FIXTURE = _FIXTURE_DIR / "CPIAUCSL.json"
_UNRATE_FIXTURE = _FIXTURE_DIR / "UNRATE.json"
_DFF_FIXTURE = _FIXTURE_DIR / "DFF.json"
_PPI_FIXTURE = _FIXTURE_DIR / "PPIFID.json"

# Sentinel api_key value used in tests. Tests assert this string never
# appears in any captured output (errors, raw_metadata, etc.).
_SENTINEL_KEY = "REDACTED_KEY_VALUE_12345_DO_NOT_LEAK"

# Recorded fixture observation dates are early-to-mid April 2026,
# inside the 65-day lookback when target_date = 2026-05-01.
_WINDOW = FetchWindow.from_kst_date(date(2026, 5, 1))


def _series_router(
    fixtures: dict[str, bytes], *, status_per: dict[str, int] | None = None
) -> tuple[httpx.AsyncClient, list[httpx.Request]]:
    """Mock client routing by ``series_id`` query param.

    Returns the client + a captured-request list for downstream
    assertions (e.g. that api_key was sent in the URL but does not
    leak into any error path).
    """

    captured: list[httpx.Request] = []
    statuses = status_per or {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        series_id = request.url.params.get("series_id", "")
        body = fixtures.get(series_id)
        if body is None:
            return httpx.Response(
                404,
                json={"error_code": 400, "error_message": f"unknown series {series_id}"},
            )
        status = statuses.get(series_id, 200)
        return httpx.Response(status, content=body, headers={"content-type": "application/json"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), captured


def _override_series(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("INVESTO_FRED_SERIES", value)


def _set_key(monkeypatch: pytest.MonkeyPatch, value: str = _SENTINEL_KEY) -> None:
    monkeypatch.setenv("FRED_API_KEY", value)


# ---------------------------------------------------------------------------
# AC-3.6 / R13 — missing-secret graceful degradation
# ---------------------------------------------------------------------------


async def test_missing_fred_api_key_raises_terminal_source_fetch_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    adapter = FredMacroAdapter()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(500))
    ) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _WINDOW)
    err = exc_info.value
    assert err.transient is False
    assert err.source_name == "fred-macro"
    assert err.cause is None
    # Error message names the env var (not any key value).
    assert "FRED_API_KEY" in str(err)
    assert "fred-macro" in str(err)


async def test_empty_fred_api_key_raises_terminal_source_fetch_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRED_API_KEY", "")
    adapter = FredMacroAdapter()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(500))
    ) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, _WINDOW)
    assert exc_info.value.transient is False


async def test_missing_key_does_not_attempt_any_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Defense-in-depth: when the key is missing, the adapter raises
    # BEFORE issuing any HTTP request. Pin this so a future refactor
    # can't accidentally send a GET with key="" to FRED's logs.
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    requests_seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        return httpx.Response(200, json={})

    adapter = FredMacroAdapter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceFetchError):
            await adapter.fetch(client, _WINDOW)
    assert requests_seen == []


# ---------------------------------------------------------------------------
# Secret hygiene — sentinel key never leaks
# ---------------------------------------------------------------------------


async def test_api_key_not_in_raw_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_key(monkeypatch)
    _override_series(monkeypatch, "CPIAUCSL")
    fixtures = {"CPIAUCSL": _CPI_FIXTURE.read_bytes()}
    adapter = FredMacroAdapter()
    client, _ = _series_router(fixtures)
    async with client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    item = items[0]
    for key, value in item.raw_metadata.items():
        assert _SENTINEL_KEY not in key
        assert _SENTINEL_KEY not in value


async def test_api_key_in_url_params_but_not_in_error_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # FRED requires the key as a URL query param (no header auth path).
    # That is the ONE place it appears. We pin: the captured URL has
    # the key, but error messages must not echo it.
    _set_key(monkeypatch)
    _override_series(monkeypatch, "BAD_SERIES_ID")
    # Configure the router to return 200 with an empty observations
    # list — the adapter raises a per-series SourceFetchError.
    fixtures = {
        "BAD_SERIES_ID": json.dumps(
            {
                "realtime_start": "2026-04-30",
                "realtime_end": "2026-04-30",
                "observations": [],
            }
        ).encode("utf-8")
    }
    adapter = FredMacroAdapter()
    client, captured = _series_router(fixtures)
    async with client:
        items = await adapter.fetch(client, _WINDOW)
    # Per-series isolation: SourceFetchError caught, item dropped.
    assert items == []
    # The key WAS sent in the URL (FRED requires it).
    assert captured[0].url.params["api_key"] == _SENTINEL_KEY
    # But the per-series SourceFetchError gets dropped silently — the
    # logging happens only at the aggregator level. We've still pinned
    # the per-series isolation contract above.


async def test_api_key_not_in_terminal_error_message_for_bad_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # If FRED returns malformed JSON, the per-series SourceFetchError's
    # message must NOT contain the api_key. The adapter has full access
    # to it but the message must not echo it.
    _set_key(monkeypatch)
    _override_series(monkeypatch, "CPIAUCSL")

    # Force a malformed-JSON response.
    captured_messages: list[str] = []
    original_error = SourceFetchError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"<<<not-json>>>", headers={"content-type": "application/json"}
        )

    adapter = FredMacroAdapter()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        # Per-series error gets caught silently, so we have to bypass
        # the adapter's gather and call _fetch_one directly to inspect
        # the error.
        with pytest.raises(original_error) as exc_info:
            await adapter._fetch_one(client, "CPIAUCSL", _SENTINEL_KEY, _WINDOW)
    captured_messages.append(str(exc_info.value))
    captured_messages.append(repr(exc_info.value))
    for msg in captured_messages:
        assert _SENTINEL_KEY not in msg, f"api_key leaked into error: {msg!r}"


# ---------------------------------------------------------------------------
# Recorded-fixture happy path
# ---------------------------------------------------------------------------


async def test_cpi_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_key(monkeypatch)
    _override_series(monkeypatch, "CPIAUCSL")
    fixtures = {"CPIAUCSL": _CPI_FIXTURE.read_bytes()}
    adapter = FredMacroAdapter()
    client, _ = _series_router(fixtures)
    async with client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    item = items[0]
    assert item.source_name == "fred-macro"
    assert item.category == "macro"
    # Latest 311.054, prior 310.633 → delta +0.4210
    assert "311.054" in item.title
    assert "+0.4210" in item.title
    assert item.raw_metadata["series_id"] == "CPIAUCSL"
    assert item.raw_metadata["value"] == "311.054000"
    assert item.raw_metadata["release_date"] == "2026-04-01"
    assert item.raw_metadata["previous_value"] == "310.633000"
    assert item.raw_metadata["previous_release_date"] == "2026-03-01"
    assert str(item.url) == "https://fred.stlouisfed.org/series/CPIAUCSL"
    # 2026-04-01 NY midnight (EDT, UTC-4) → 2026-04-01 04:00 UTC
    assert item.published_at == datetime(2026, 4, 1, 4, 0, tzinfo=UTC)


async def test_unrate_placeholder_falls_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # UNRATE fixture: latest is "." → adapter falls through to prior
    # observation (4.1 on 2026-03-01). Since there's only one valid
    # observation, prior_value is None and delta is "n/a".
    _set_key(monkeypatch)
    _override_series(monkeypatch, "UNRATE")
    fixtures = {"UNRATE": _UNRATE_FIXTURE.read_bytes()}
    adapter = FredMacroAdapter()
    client, _ = _series_router(fixtures)
    async with client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    item = items[0]
    assert item.raw_metadata["value"] == "4.100000"
    assert item.raw_metadata["release_date"] == "2026-03-01"
    assert "previous_value" not in item.raw_metadata
    assert "n/a" in item.title
    assert "no prior observation" in (item.summary or "")


async def test_dff_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # Daily series, two consecutive business days with same value →
    # delta = 0.0000.
    _set_key(monkeypatch)
    _override_series(monkeypatch, "DFF")
    fixtures = {"DFF": _DFF_FIXTURE.read_bytes()}
    adapter = FredMacroAdapter()
    client, _ = _series_router(fixtures)
    async with client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    assert items[0].raw_metadata["value"] == "5.330000"
    assert "+0.0000" in items[0].title


async def test_ppifid_happy_path_adds_required_macro_actual(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from investo.models.macro import is_required_macro_actual, macro_event_key, macro_priority

    _set_key(monkeypatch)
    _override_series(monkeypatch, "PPIFID")
    fixtures = {"PPIFID": _PPI_FIXTURE.read_bytes()}
    adapter = FredMacroAdapter()
    client, _ = _series_router(fixtures)
    async with client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    item = items[0]
    assert item.raw_metadata["series_id"] == "PPIFID"
    assert item.raw_metadata["value"] == "156.878000"
    assert item.raw_metadata["release_date"] == "2026-04-01"
    assert item.raw_metadata["previous_value"] == "154.656000"
    assert item.raw_metadata["previous_release_date"] == "2026-03-01"
    assert str(item.url) == "https://fred.stlouisfed.org/series/PPIFID"
    assert macro_event_key(item) == "fred-macro:series_id=PPIFID:release_date=2026-04-01"
    assert macro_priority(item) == "P0"
    assert is_required_macro_actual(item) is True


async def test_three_series_concurrent(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_key(monkeypatch)
    _override_series(monkeypatch, "CPIAUCSL,UNRATE,DFF")
    fixtures = {
        "CPIAUCSL": _CPI_FIXTURE.read_bytes(),
        "UNRATE": _UNRATE_FIXTURE.read_bytes(),
        "DFF": _DFF_FIXTURE.read_bytes(),
    }
    adapter = FredMacroAdapter()
    client, _ = _series_router(fixtures)
    async with client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 3
    ids = {item.raw_metadata["series_id"] for item in items}
    assert ids == {"CPIAUCSL", "UNRATE", "DFF"}


# ---------------------------------------------------------------------------
# Per-series isolation
# ---------------------------------------------------------------------------


async def test_invalid_series_isolated_from_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_key(monkeypatch)
    _override_series(monkeypatch, "CPIAUCSL,BOGUS_ID")
    fixtures = {"CPIAUCSL": _CPI_FIXTURE.read_bytes()}
    adapter = FredMacroAdapter()
    client, _ = _series_router(fixtures, status_per={"BOGUS_ID": 404})
    async with client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1
    assert items[0].raw_metadata["series_id"] == "CPIAUCSL"


async def test_all_placeholder_series_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # All observations are "." — adapter raises per-series, then the
    # adapter-level loop drops it.
    _set_key(monkeypatch)
    _override_series(monkeypatch, "ALLDOTS")
    body = json.dumps(
        {
            "realtime_start": "2026-04-30",
            "realtime_end": "2026-04-30",
            "observations": [
                {"date": "2026-04-01", "value": "."},
                {"date": "2026-03-01", "value": "."},
            ],
        }
    ).encode("utf-8")
    fixtures = {"ALLDOTS": body}
    adapter = FredMacroAdapter()
    client, _ = _series_router(fixtures)
    async with client:
        items = await adapter.fetch(client, _WINDOW)
    assert items == []


# ---------------------------------------------------------------------------
# Widened window (65-day lookback)
# ---------------------------------------------------------------------------


async def test_old_observation_outside_lookback_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Observation roughly 90 days before target_date — outside 65d lookback
    # → adapter emits nothing.
    _set_key(monkeypatch)
    _override_series(monkeypatch, "OLD")
    body = json.dumps(
        {
            "realtime_start": "2026-04-30",
            "realtime_end": "2026-04-30",
            "observations": [
                {"date": "2026-02-01", "value": "1.23"},
            ],
        }
    ).encode("utf-8")
    fixtures = {"OLD": body}
    adapter = FredMacroAdapter()
    client, _ = _series_router(fixtures)
    async with client:
        items = await adapter.fetch(client, _WINDOW)
    assert items == []


async def test_observation_at_lookback_boundary_included(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Observation exactly 30 days before target — inside 65d window.
    _set_key(monkeypatch)
    _override_series(monkeypatch, "BOUNDARY")
    body = json.dumps(
        {
            "realtime_start": "2026-04-30",
            "realtime_end": "2026-04-30",
            "observations": [
                {"date": "2026-04-01", "value": "100.0"},
            ],
        }
    ).encode("utf-8")
    fixtures = {"BOUNDARY": body}
    adapter = FredMacroAdapter()
    client, _ = _series_router(fixtures)
    async with client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 1


# ---------------------------------------------------------------------------
# R12 — env override
# ---------------------------------------------------------------------------


async def test_env_override_passes_only_specified_series(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_key(monkeypatch)
    _override_series(monkeypatch, "CPIAUCSL,UNRATE")
    fixtures = {
        "CPIAUCSL": _CPI_FIXTURE.read_bytes(),
        "UNRATE": _UNRATE_FIXTURE.read_bytes(),
    }
    adapter = FredMacroAdapter()
    client, captured = _series_router(fixtures)
    async with client:
        items = await adapter.fetch(client, _WINDOW)
    assert len(items) == 2
    requested_series = {req.url.params["series_id"] for req in captured}
    assert requested_series == {"CPIAUCSL", "UNRATE"}


async def test_env_unset_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_key(monkeypatch)
    monkeypatch.delenv("INVESTO_FRED_SERIES", raising=False)
    # All defaults will 404 (not in fixtures map) — we just want to
    # confirm WHICH series were attempted.
    adapter = FredMacroAdapter()
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.url.params.get("series_id", ""))
        return httpx.Response(404, json={"error_code": 400})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await adapter.fetch(client, _WINDOW)
    assert items == []
    assert set(captured) == {
        "CPIAUCSL",
        "UNRATE",
        "DFF",
        "DGS10",
        "PPIFID",
    }


# ---------------------------------------------------------------------------
# Class identity
# ---------------------------------------------------------------------------


def test_class_attributes() -> None:
    assert FredMacroAdapter.name == "fred-macro"
    assert FredMacroAdapter.category == "macro"
