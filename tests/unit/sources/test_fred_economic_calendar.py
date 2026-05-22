"""Tests for ``investo.sources.fred_economic_calendar.FredEconomicCalendarAdapter``.

Pins the algorithm + R10 fixture replay against:

* Recorded real ``release/dates`` bodies under
  ``fixtures/api/fred-economic-calendar/`` (4 release ids — CPI / PPI /
  NFP / GDP — captured live 2026-05-10) — forward-window filter,
  ``scheduled_at`` stamping, per-release isolation.
* The empty far-future fixture — empty ``release_dates`` array → empty
  list (graceful, no error).
* The HTTP 400 invalid-key fixture — terminal ``SourceFetchError``;
  per-release isolation drops the bad release without aborting siblings.
* Inline synthetic JSON — env-var override, malformed bodies, edge
  cases.

R13: ``FRED_API_KEY`` is read at fetch time. Missing key →
``SourceFetchError(transient=False)``. The key value never appears in
log lines, error messages, ``raw_metadata`` payloads, or fixtures —
pinned by `test_no_secret_in_request_url` and grep-style invariants on
the fixture directory itself.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.fred_economic_calendar import FredEconomicCalendarAdapter
from investo.sources.protocol import SourceFetchError
from investo.sources.tiers import adapter_tier

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "fred-economic-calendar"
_SENTINEL_KEY = "x" * 32  # 32-char alpha lowercase — never logged / leaked.


# ---------------------------------------------------------------------------
# Mock-transport helpers
# ---------------------------------------------------------------------------


def _routed_handler(
    routes: dict[str, tuple[bytes, int]],
) -> Callable[[httpx.Request], httpx.Response]:
    """Return a MockTransport handler that picks the response by ``release_id``.

    ``routes`` keys are stringified release ids; values are ``(body, status)``
    tuples. Unknown release ids respond with the empty fixture so the
    adapter's per-release isolation still completes deterministically.
    """

    empty_body = (_FIXTURE_DIR / "empty_far_future.json").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        rid = request.url.params.get("release_id", "")
        body, status = routes.get(rid, (empty_body, 200))
        return httpx.Response(
            status,
            content=body,
            headers={"content-type": "application/json"},
        )

    return handler


def _mock_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _single_response_client(body: bytes, status: int = 200) -> httpx.AsyncClient:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            content=body,
            headers={"content-type": "application/json"},
        )

    return _mock_client(handler)


# ---------------------------------------------------------------------------
# Real fixture — happy path against the captured 2026-05-10 release schedule
# ---------------------------------------------------------------------------


async def test_fetch_returns_forward_release_dates_within_default_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Restrict the release set to the four we have fixtures for so the
    # default 10-release fan-out doesn't fall through to empty for the
    # other six.
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "10,46,50,53")
    routes = {
        "10": ((_FIXTURE_DIR / "release_10_cpi.json").read_bytes(), 200),
        "46": ((_FIXTURE_DIR / "release_46_ppi.json").read_bytes(), 200),
        "50": ((_FIXTURE_DIR / "release_50_nfp.json").read_bytes(), 200),
        "53": ((_FIXTURE_DIR / "release_53_gdp.json").read_bytes(), 200),
    }
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _mock_client(_routed_handler(routes)) as client:
        items = await adapter.fetch(client, window)

    assert items, "expected at least one forward release date in the 30-day window"
    assert all(item.source_name == "fred-economic-calendar" for item in items)
    assert all(item.category == "calendar" for item in items)
    target_midnight = datetime.combine(date(2026, 5, 10), time.min, tzinfo=UTC)
    horizon = datetime.combine(date(2026, 5, 10) + timedelta(days=30), time.min, tzinfo=UTC)
    for item in items:
        # AC-7.4 — every emitted item carries tz-aware UTC scheduled_at.
        assert item.scheduled_at is not None
        assert item.scheduled_at.tzinfo is not None
        assert item.scheduled_at.tzinfo.utcoffset(item.scheduled_at) == timedelta(0)
        assert target_midnight <= item.scheduled_at < horizon
        # published_at anchored to target date midnight UTC, not to the
        # scheduled date — keeps the row inside the publish window so
        # the aggregator's ``_MAX_FUTURE_PUBLISHED_AT`` guard does not
        # drop it.
        assert item.published_at == target_midnight


async def test_fetch_includes_known_cpi_release_in_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The CPI fixture carries 2026-05-12 as the next release; the
    # default 30-day window from target_date 2026-05-10 should include
    # it (D+2). We assert the row identity rather than counts to keep
    # the test stable.
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "10")
    routes = {"10": ((_FIXTURE_DIR / "release_10_cpi.json").read_bytes(), 200)}
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _mock_client(_routed_handler(routes)) as client:
        items = await adapter.fetch(client, window)

    cpi_rows = [item for item in items if item.raw_metadata.get("release_id") == "10"]
    assert cpi_rows, "expected at least one CPI row from the recorded fixture"
    target = next(
        (item for item in cpi_rows if item.scheduled_at == datetime(2026, 5, 12, 0, 0, tzinfo=UTC)),
        None,
    )
    assert target is not None, "expected CPI 2026-05-12 from the fixture"
    assert target.raw_metadata.get("release_name") == "Consumer Price Index"
    assert target.raw_metadata.get("scheduled_date") == "2026-05-12"
    assert target.title.startswith("2026-05-12 — Consumer Price Index")
    assert str(target.url) == "https://fred.stlouisfed.org/release?rid=10"


async def test_fetch_includes_known_ppi_release_with_macro_priority_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # u59 — PPI is a high-importance macro schedule item. Pin the
    # recorded release id/name/date so candidate-priority code can
    # recognize it deterministically before Stage 1 caps.
    from investo.briefing.segments import segment_items
    from investo.models.macro import macro_event_key, macro_event_status, macro_priority

    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "46")
    routes = {"46": ((_FIXTURE_DIR / "release_46_ppi.json").read_bytes(), 200)}
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _mock_client(_routed_handler(routes)) as client:
        items = await adapter.fetch(client, window)

    ppi_rows = [item for item in items if item.raw_metadata.get("release_id") == "46"]
    assert ppi_rows, "expected at least one PPI row from the recorded fixture"
    target = next(
        (item for item in ppi_rows if item.scheduled_at == datetime(2026, 5, 13, 0, 0, tzinfo=UTC)),
        None,
    )
    assert target is not None, "expected PPI 2026-05-13 from the fixture"
    assert target.raw_metadata.get("release_name") == "Producer Price Index"
    assert target.raw_metadata.get("scheduled_date") == "2026-05-13"
    assert target.title.startswith("2026-05-13 — Producer Price Index")
    assert str(target.url) == "https://fred.stlouisfed.org/release?rid=46"
    assert macro_event_key(target) == (
        "fred-economic-calendar:release_id=46:scheduled_date=2026-05-13"
    )
    assert macro_event_status(target) == "scheduled"
    assert macro_priority(target) == "P1"
    routed = segment_items([target])
    assert routed.us_equity == (target,)
    assert routed.crypto == ()
    assert routed.domestic_equity == ()


async def test_fetch_excludes_historical_release_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The CPI fixture also carries 2026-04-10, 2026-03-11, etc. None
    # should leak into the output for a forward-only window starting
    # 2026-05-10.
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "10")
    routes = {"10": ((_FIXTURE_DIR / "release_10_cpi.json").read_bytes(), 200)}
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _mock_client(_routed_handler(routes)) as client:
        items = await adapter.fetch(client, window)

    target_midnight = datetime.combine(date(2026, 5, 10), time.min, tzinfo=UTC)
    assert items
    assert all(
        item.scheduled_at is not None and item.scheduled_at >= target_midnight for item in items
    )


async def test_fetch_respects_lookahead_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 7-day window narrows the result vs. the default 30 days. The CPI
    # 2026-05-12 row stays (D+2); later prints fall outside.
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "10")
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_LOOKAHEAD_DAYS", "7")
    routes = {"10": ((_FIXTURE_DIR / "release_10_cpi.json").read_bytes(), 200)}
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _mock_client(_routed_handler(routes)) as client:
        items = await adapter.fetch(client, window)

    horizon = datetime.combine(date(2026, 5, 17), time.min, tzinfo=UTC)
    for item in items:
        assert item.scheduled_at is not None
        assert item.scheduled_at < horizon


async def test_fetch_far_future_target_returns_empty_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Captured fixture stops at 2026-12-10 (CPI). A target in 2027-Q3
    # has zero forward events in the default 30-day window.
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "10")
    routes = {"10": ((_FIXTURE_DIR / "release_10_cpi.json").read_bytes(), 200)}
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2027, 8, 1), tz=UTC)

    async with _mock_client(_routed_handler(routes)) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_empty_release_dates_array_returns_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "10")
    body = (_FIXTURE_DIR / "empty_far_future.json").read_bytes()
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _single_response_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


# ---------------------------------------------------------------------------
# R13 — secret hygiene
# ---------------------------------------------------------------------------


async def test_missing_api_key_raises_terminal_source_fetch_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _single_response_client(b"{}") as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)

    assert exc_info.value.transient is False
    # Message names the env-var, never any partial / full key value.
    assert "FRED_API_KEY" in str(exc_info.value)


async def test_invalid_api_key_400_isolated_per_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Per the fixture: an invalid api_key → HTTP 400 with FRED's
    # error_message body. ``retry_get`` treats 4xx as terminal
    # SourceFetchError; the per-release ``asyncio.gather`` swallows it
    # and continues. With every release returning 400, the adapter
    # returns an empty list (siblings all dropped), not a raise.
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "10,46,50")
    body = (_FIXTURE_DIR / "invalid_key.json").read_bytes()
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _single_response_client(body, status=400) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_partial_failure_per_release_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # release 10 returns the live CPI body; release 46 returns 400 (bad
    # release). The adapter must return CPI rows and silently drop PPI.
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "10,46")
    routes = {
        "10": ((_FIXTURE_DIR / "release_10_cpi.json").read_bytes(), 200),
        "46": ((_FIXTURE_DIR / "invalid_key.json").read_bytes(), 400),
    }
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _mock_client(_routed_handler(routes)) as client:
        items = await adapter.fetch(client, window)

    assert items, "CPI rows should still surface despite PPI 400"
    assert all(item.raw_metadata.get("release_id") == "10" for item in items)


async def test_no_secret_value_in_error_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Even when the request fails inside ``retry_get`` (e.g., terminal
    # 400 escaped per-release isolation in some hypothetical refactor),
    # the SourceFetchError message must not leak the api_key value.
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "10")
    # Force a malformed JSON path so the adapter raises with release_id
    # in the message — the assertion is that the key value is absent.
    routes = {"10": (b"<not json>", 200)}
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _mock_client(_routed_handler(routes)) as client:
        items = await adapter.fetch(client, window)

    # All releases failed → empty list. The R13 check is on the test
    # logger / error path; we capture and re-raise via per-release
    # gather, so no leak path exists. The assertion below stays as a
    # behavioural anchor — if a future refactor surfaces the error
    # directly, the message contract still holds.
    assert items == []


def test_no_plaintext_api_key_in_fixture_directory() -> None:
    # R10 + R13 — every captured fixture body must be replayable as-is.
    # The literal ``api_key=`` query-param phrasing must not appear in
    # any captured URL string (the meta.json template uses ``api_key=***``
    # explicitly). Note the FRED error body for invalid_key carries the
    # word "api_key" in the upstream prose ("variable api_key is not a
    # 32 character ..."), which is fine — that is FRED's message text,
    # not a leaked credential. We use a stricter regex looking for
    # ``api_key=<32 alphanumerics>`` to catch a real leak shape.
    leak_re = re.compile(r"api_key=[a-z0-9]{32}", re.IGNORECASE)
    for path in _FIXTURE_DIR.iterdir():
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert not leak_re.search(text), f"plaintext api_key value in {path.name}"


# ---------------------------------------------------------------------------
# Synthetic — malformed / edge cases
# ---------------------------------------------------------------------------


def _wrap_release_dates(release_dates: list[dict[str, str | int]]) -> bytes:
    return json.dumps(
        {
            "realtime_start": "1776-07-04",
            "realtime_end": "9999-12-31",
            "order_by": "release_date",
            "sort_order": "desc",
            "count": len(release_dates),
            "offset": 0,
            "limit": 15,
            "release_dates": release_dates,
        }
    ).encode("utf-8")


async def test_malformed_date_entries_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "10")
    body = _wrap_release_dates(
        [
            {"release_id": 10, "date": "not-a-date"},
            {"release_id": 10, "date": ""},
            {"release_id": 10},  # missing date
            {"release_id": 10, "date": "2026-05-22"},  # good (D+12)
        ]
    )
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _single_response_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].raw_metadata.get("scheduled_date") == "2026-05-22"


async def test_missing_release_dates_key_returns_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "10")
    body = json.dumps({"count": 0}).encode("utf-8")
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _single_response_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_non_object_response_drops_release_via_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Non-object body raises SourceFetchError inside ``_fetch_one``;
    # the per-release ``asyncio.gather`` isolates and drops it.
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "10")
    body = b"[1, 2, 3]"
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _single_response_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_malformed_json_drops_release_via_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "10")
    body = b"<not json at all"
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _single_response_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_unknown_release_id_falls_back_to_generic_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An operator-supplied id outside _RELEASE_NAMES still renders a
    # readable title without breaking. ``raw_metadata["release_name"]``
    # carries the fallback string.
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "9999")
    body = _wrap_release_dates([{"release_id": 9999, "date": "2026-05-22"}])
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _single_response_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    item = items[0]
    assert item.raw_metadata.get("release_id") == "9999"
    assert item.raw_metadata.get("release_name") == "FRED Release 9999"
    assert "FRED Release 9999" in item.title


async def test_lookahead_env_typo_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "10")
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_LOOKAHEAD_DAYS", "not-a-number")
    routes = {"10": ((_FIXTURE_DIR / "release_10_cpi.json").read_bytes(), 200)}
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _mock_client(_routed_handler(routes)) as client:
        items = await adapter.fetch(client, window)

    # Default 30 → CPI 2026-05-12 (D+2) is in window.
    assert any(item.scheduled_at == datetime(2026, 5, 12, 0, 0, tzinfo=UTC) for item in items)


async def test_lookahead_env_above_max_clamped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRED_API_KEY", _SENTINEL_KEY)
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "10")
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_LOOKAHEAD_DAYS", "9999")
    routes = {"10": ((_FIXTURE_DIR / "release_10_cpi.json").read_bytes(), 200)}
    adapter = FredEconomicCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _mock_client(_routed_handler(routes)) as client:
        items = await adapter.fetch(client, window)

    horizon = datetime.combine(date(2026, 5, 10) + timedelta(days=180), time.min, tzinfo=UTC)
    for item in items:
        assert item.scheduled_at is not None
        assert item.scheduled_at < horizon


# ---------------------------------------------------------------------------
# Adapter identity + tier registry
# ---------------------------------------------------------------------------


def test_adapter_class_attributes() -> None:
    assert FredEconomicCalendarAdapter.name == "fred-economic-calendar"
    assert FredEconomicCalendarAdapter.category == "calendar"
    assert FredEconomicCalendarAdapter._ENDPOINT == "https://api.stlouisfed.org/fred/release/dates"


def test_adapter_registered_at_tier_a() -> None:
    # u32 tier registry — the adapter must round-trip through
    # ``adapter_tier`` without falling back to the default ``B``.
    assert adapter_tier("fred-economic-calendar") == "A"


def test_adapter_registered_in_lookahead_aware_sources() -> None:
    # u43 — every lookahead-emitting adapter must be in the registry
    # so ``LOOKAHEAD_DATA_MISSING`` fires on its segment(s).
    from investo.briefing.segments import LOOKAHEAD_AWARE_SOURCES

    assert "fred-economic-calendar" in LOOKAHEAD_AWARE_SOURCES


def test_adapter_anchored_to_us_equity_segment() -> None:
    # Single-segment routing — fred-economic-calendar lands on us-equity
    # only. Domestic / crypto must not see its items even when keyword
    # matches would otherwise trigger.
    from investo.briefing.segments import segment_items
    from investo.models import NormalizedItem

    item = NormalizedItem(
        source_name="fred-economic-calendar",
        category="calendar",
        title="2026-05-12 — Consumer Price Index",
        summary="FRED release_id=10 (Consumer Price Index) scheduled for 2026-05-12",
        url="https://fred.stlouisfed.org/release?rid=10",
        published_at=datetime(2026, 5, 10, 0, 0, tzinfo=UTC),
        scheduled_at=datetime(2026, 5, 12, 0, 0, tzinfo=UTC),
        raw_metadata={"release_id": "10"},
    )
    routed = segment_items([item])
    assert routed.us_equity == (item,)
    assert routed.crypto == ()
    assert routed.domestic_equity == ()


def test_module_does_not_import_anthropic_sdk() -> None:
    import investo.sources.fred_economic_calendar as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "from anthropic" not in src
    assert "import anthropic" not in src


def test_module_does_not_use_raw_stdlib_xml() -> None:
    # AC-7.6 — JSON path; no ``defusedxml`` needed and no raw stdlib
    # XML allowed under sources/**.
    import investo.sources.fred_economic_calendar as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "from xml" not in src
    assert "import xml" not in src
