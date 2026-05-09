"""Tests for ``investo.sources.fomc_calendar.FomcCalendarAdapter``.

Pins the algorithm + R10 fixture replay against:

* The recorded real ``calendar.json`` body
  (``fixtures/api/fomc-calendar/upcoming.json`` — 528 KB live recording
  from 2026-05-10) — forward window filter, ``scheduled_at`` stamping,
  type whitelist, multi-day handling.
* Inline synthetic JSON — empty events, malformed bodies, env-var
  override, edge cases.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import httpx
import pytest

from investo.sources._window import FetchWindow
from investo.sources.fomc_calendar import FomcCalendarAdapter
from investo.sources.protocol import SourceFetchError

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "api" / "fomc-calendar"
_REAL_FIXTURE = _FIXTURE_DIR / "upcoming.json"


def _mock_client(body: bytes, status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            content=body,
            headers={"content-type": "application/json"},
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# Real fixture — happy path against the captured 2026-05-10 schedule
# ---------------------------------------------------------------------------


async def test_fetch_returns_forward_events_within_default_window() -> None:
    # The captured fixture has FOMC + Speech + Stat events through
    # 2026-12-30. With target_date 2026-05-10 + default 30-day
    # window we expect FOMC Minutes 2026-05-20 plus several Speech /
    # Stat / Other rows. We don't pin an exact count (the fixture's
    # forward density is real and may surprise), but we pin the shape.
    body = _REAL_FIXTURE.read_bytes()
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items, "expected at least one forward event in the 30-day window"
    assert all(item.source_name == "fomc-calendar" for item in items)
    assert all(item.category == "calendar" for item in items)
    # AC-7.4 — every emitted item carries tz-aware UTC scheduled_at.
    for item in items:
        assert item.scheduled_at is not None
        assert item.scheduled_at.tzinfo is not None
        assert item.scheduled_at.tzinfo.utcoffset(item.scheduled_at) == timedelta(0)
        # published_at anchored to target date midnight UTC, not to
        # the scheduled date — keeps the row inside the publish window
        # so the aggregator's ``_MAX_FUTURE_PUBLISHED_AT`` guard does
        # not drop it.
        assert item.published_at == datetime.combine(date(2026, 5, 10), time.min, tzinfo=UTC)


async def test_fetch_includes_known_fomc_minutes_event() -> None:
    # The recorded fixture carries "FOMC Minutes" on 2026-05-20 (10
    # days after the target). It should appear with type FOMC and
    # scheduled_at = 2026-05-20 UTC midnight.
    body = _REAL_FIXTURE.read_bytes()
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    minutes = [
        item
        for item in items
        if "FOMC Minutes" in item.title
        and item.scheduled_at == datetime(2026, 5, 20, 0, 0, tzinfo=UTC)
    ]
    assert minutes, f"expected FOMC Minutes 2026-05-20 in items; got {[i.title for i in items[:5]]}"
    # raw_metadata carries event_type + scheduled_date, no secrets.
    minute = minutes[0]
    assert minute.raw_metadata.get("event_type") == "FOMC"
    assert minute.raw_metadata.get("scheduled_date") == "2026-05-20"


async def test_fetch_excludes_events_before_target_date() -> None:
    # Fixture has thousands of historical events. None should leak
    # into the output for a target_date in 2026-05.
    body = _REAL_FIXTURE.read_bytes()
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items
    target_midnight = datetime.combine(date(2026, 5, 10), time.min, tzinfo=UTC)
    assert all(
        item.scheduled_at is not None and item.scheduled_at >= target_midnight for item in items
    )


async def test_fetch_respects_lookahead_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    # 7-day window — should narrow the result vs. the default 30 days.
    monkeypatch.setenv("INVESTO_FOMC_LOOKAHEAD_DAYS", "7")
    body = _REAL_FIXTURE.read_bytes()
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    horizon = datetime.combine(date(2026, 5, 17), time.min, tzinfo=UTC)
    for item in items:
        assert item.scheduled_at is not None
        assert item.scheduled_at < horizon


async def test_fetch_far_future_target_returns_empty_set() -> None:
    # Fixture stops at 2026-12-30; a target in 2027-Q3 has zero events
    # in the default 30-day window.
    body = _REAL_FIXTURE.read_bytes()
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2027, 8, 1), tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


# ---------------------------------------------------------------------------
# Synthetic — type whitelist, malformed entries, edge cases
# ---------------------------------------------------------------------------


def _wrap_events(events: list[dict[str, str]]) -> bytes:
    # The live endpoint serves UTF-8 with a BOM. The test stays in
    # plain UTF-8 — the adapter accepts both via ``utf-8-sig``.
    return json.dumps({"events": events, "announcement": ""}).encode("utf-8")


async def test_event_type_outside_whitelist_dropped() -> None:
    body = _wrap_events(
        [
            {
                "type": "Conferences",
                "title": "BIS Annual Conference",
                "month": "2026-06",
                "days": "20",
                "time": "9:00 a.m.",
                "description": "",
                "location": "Basel",
            },
            {
                "type": "Speeches",
                "title": "Speech - Governor Cook",
                "month": "2026-06",
                "days": "20",
                "time": "9:00 a.m.",
                "description": "Monetary Policy",
                "location": "BIS",
            },
        ]
    )
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 6, 1), tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert items[0].raw_metadata.get("event_type") == "Speeches"


async def test_multi_day_event_uses_first_day() -> None:
    body = _wrap_events(
        [
            {
                "type": "FOMC",
                "title": "FOMC Meeting",
                "month": "2026-06",
                "days": "16, 17",
                "time": "2:00 p.m.",
                "description": "Two-day rate decision meeting",
                "location": "Washington",
            }
        ]
    )
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 6, 1), tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    item = items[0]
    assert item.scheduled_at == datetime(2026, 6, 16, 0, 0, tzinfo=UTC)
    assert item.title.startswith("2026-06-16 — FOMC Meeting")


async def test_malformed_month_or_days_dropped() -> None:
    body = _wrap_events(
        [
            {"type": "FOMC", "title": "Bad month", "month": "not-a-date", "days": "5"},
            {"type": "FOMC", "title": "Bad day", "month": "2026-06", "days": "thirty"},
            {"type": "FOMC", "title": "Empty days", "month": "2026-06", "days": ""},
            {
                "type": "FOMC",
                "title": "Good entry",
                "month": "2026-06",
                "days": "10",
                "time": "2:00 p.m.",
            },
        ]
    )
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 6, 1), tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert "Good entry" in items[0].title


async def test_empty_events_array_returns_empty_list() -> None:
    body = _wrap_events([])
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 6, 1), tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_missing_events_key_returns_empty_list() -> None:
    # Endpoint historically returned ``{"announcement": ""}`` with no
    # ``events`` field on slow days. Treat as zero items, not error.
    body = json.dumps({"announcement": ""}).encode("utf-8")
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 6, 1), tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert items == []


async def test_non_object_response_raises_terminal_source_fetch_error() -> None:
    body = b"[1, 2, 3]"
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 6, 1), tz=UTC)

    async with _mock_client(body) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)

    assert exc_info.value.transient is False
    assert "expected object" in str(exc_info.value)


async def test_malformed_json_raises_terminal_source_fetch_error() -> None:
    body = b"<not json at all"
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 6, 1), tz=UTC)

    async with _mock_client(body) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)

    assert exc_info.value.transient is False
    assert "malformed JSON" in str(exc_info.value)


async def test_terminal_4xx_raises_source_fetch_error() -> None:
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 6, 1), tz=UTC)

    async with _mock_client(b"forbidden", status=403) as client:
        with pytest.raises(SourceFetchError) as exc_info:
            await adapter.fetch(client, window)

    assert exc_info.value.transient is False


async def test_utf8_bom_in_body_accepted() -> None:
    # The live endpoint serves bodies prefixed with ``\xef\xbb\xbf``.
    # The adapter strips the BOM via ``utf-8-sig`` — without that the
    # stdlib ``json.loads`` raises on the leading char.
    body = b"\xef\xbb\xbf" + json.dumps(
        {
            "events": [
                {
                    "type": "FOMC",
                    "title": "FOMC Press Conference",
                    "month": "2026-06",
                    "days": "17",
                    "time": "2:30 p.m.",
                    "description": "",
                    "location": "Washington",
                }
            ]
        }
    ).encode("utf-8")
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 6, 1), tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert "FOMC Press Conference" in items[0].title


async def test_link_field_resolved_to_absolute_url() -> None:
    body = _wrap_events(
        [
            {
                "type": "Speeches",
                "title": "Speech - Governor Bowman",
                "month": "2026-06",
                "days": "5",
                "time": "12:30 p.m.",
                "description": "Banking",
                "location": "Oxford",
                "link": "/newsevents/speech/bowman20260605a.htm",
            }
        ]
    )
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 6, 1), tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert len(items) == 1
    assert (
        str(items[0].url) == "https://www.federalreserve.gov/newsevents/speech/bowman20260605a.htm"
    )


async def test_lookahead_env_typo_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Non-numeric values fall back to default 30 (with a warning, not
    # an error). We assert via behavior — a 30-day window includes
    # the 2026-05-20 FOMC Minutes row.
    monkeypatch.setenv("INVESTO_FOMC_LOOKAHEAD_DAYS", "not-a-number")
    body = _REAL_FIXTURE.read_bytes()
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    assert any(item.scheduled_at == datetime(2026, 5, 20, 0, 0, tzinfo=UTC) for item in items)


async def test_lookahead_env_above_max_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    # 9999 → clamped to 180. Effect: every forward event in the
    # captured fixture (which stops at 2026-12-30, ~234 days from
    # 2026-05-10) is windowed to the first ~180 days.
    monkeypatch.setenv("INVESTO_FOMC_LOOKAHEAD_DAYS", "9999")
    body = _REAL_FIXTURE.read_bytes()
    adapter = FomcCalendarAdapter()
    window = FetchWindow.from_local_date(date(2026, 5, 10), tz=UTC)

    async with _mock_client(body) as client:
        items = await adapter.fetch(client, window)

    horizon = datetime.combine(date(2026, 5, 10) + timedelta(days=180), time.min, tzinfo=UTC)
    for item in items:
        assert item.scheduled_at is not None
        assert item.scheduled_at < horizon


# ---------------------------------------------------------------------------
# Adapter identity (ClassVar attributes)
# ---------------------------------------------------------------------------


def test_adapter_class_attributes() -> None:
    assert FomcCalendarAdapter.name == "fomc-calendar"
    assert FomcCalendarAdapter.category == "calendar"
    assert FomcCalendarAdapter._ENDPOINT == "https://www.federalreserve.gov/json/calendar.json"


def test_no_api_key_in_endpoint() -> None:
    # R13 — fomc-calendar uses a key-less public endpoint. The URL
    # must not encode any query parameter resembling a credential.
    assert "api_key" not in FomcCalendarAdapter._ENDPOINT.lower()
    assert "token" not in FomcCalendarAdapter._ENDPOINT.lower()


def test_module_does_not_import_anthropic_sdk() -> None:
    # Project-rule preservation: no Anthropic SDK in the adapter.
    import investo.sources.fomc_calendar as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "from anthropic" not in src
    assert "import anthropic" not in src


def test_no_real_secret_left_in_environment() -> None:
    # Sanity: the lookahead env knob must not be set globally as a
    # side effect of some other test. Adapter relies on monkeypatch
    # for any per-test override.
    assert (
        os.environ.get("INVESTO_FOMC_LOOKAHEAD_DAYS") is None
        or os.environ.get("INVESTO_FOMC_LOOKAHEAD_DAYS") == ""
    )
