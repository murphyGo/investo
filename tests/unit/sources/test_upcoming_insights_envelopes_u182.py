"""Existing recordings are replayed; edge-case HTML/JSON below is explicitly synthetic."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from investo.models.insights import SourceScheduleCoverage
from investo.sources._window import FetchWindow
from investo.sources.fomc_calendar import FomcCalendarAdapter, _insight_event
from investo.sources.fred_economic_calendar import FredEconomicCalendarAdapter
from investo.sources.treasury_auctions import TreasuryAuctionsAdapter, _insight_auction
from investo.sources.us_economic_calendar import UsEconomicCalendarAdapter, _insight_release

FIXTURES = Path(__file__).parent / "fixtures/api"


@pytest.mark.parametrize(
    "adapter,path,day",
    [
        (FomcCalendarAdapter(), "fomc-calendar/upcoming.json", date(2026, 10, 24)),
        (
            FredEconomicCalendarAdapter(),
            "fred-economic-calendar/release_10_cpi.json",
            date(2026, 5, 10),
        ),
        (UsEconomicCalendarAdapter(), "us-economic-calendar/bea-schedule.html", date(2026, 5, 8)),
        (TreasuryAuctionsAdapter(), "treasury-auctions/upcoming.json", date(2026, 7, 19)),
    ],
)
async def test_opt_in_preserves_exact_legacy_json_and_request_count(
    adapter, path, day, monkeypatch
):
    monkeypatch.setenv("FRED_API_KEY", "SYNTHETIC_TEST_KEY")
    monkeypatch.setenv("INVESTO_FRED_CALENDAR_RELEASES", "10")
    body = (FIXTURES / path).read_bytes()
    requests = []

    def respond(request):
        requests.append((request.method, request.url))
        return httpx.Response(200, content=body)

    window = FetchWindow.from_kst_date(day)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        off = await adapter.fetch(client, window)
        first = tuple(requests)
        requests.clear()
        on = await adapter.fetch(client, replace(window, insights_enabled=True))
    assert [i.model_dump_json() for i in on] == [i.model_dump_json() for i in off]
    assert tuple(requests) == first and len(requests) == 1
    assert all(i.insight_envelope is None for i in off)
    if adapter.name == "us-economic-calendar":
        assert all(i.insight_envelope is None for i in on)  # old fixture has no declared year
    else:
        assert any(i.insight_envelope for i in on)
    if adapter.name == "fred-economic-calendar":
        rows = [e for i in on if i.insight_envelope for e in i.insight_envelope.events]
        assert rows and all(
            e.time.precision == "date"
            and e.time.exact_at is None
            and e.details.target_period is None
            for e in rows
        )
        assert all("?" not in e.endpoint and "?" not in e.source_href for e in rows)
        assert "SYNTHETIC_TEST_KEY" not in json.dumps([r.model_dump(mode="json") for r in rows])


@pytest.mark.parametrize(
    "days,accepted",
    [
        ("27, 28", True),
        ("27, bad", False),
        ("28, 27", False),
        ("27, 29", False),
        ("27 - 28", False),
    ],
)
def test_fed_range_is_all_or_nothing_and_never_becomes_a_decision_timestamp(days, accepted):
    coverage = SourceScheduleCoverage(start_date=date(2026, 10, 24), end_date=date(2026, 11, 23))
    row = dict(title="FOMC Meeting", type="FOMC", month="2026-10", days=days, time="2:00 p.m.")
    result = _insight_event(row, coverage)
    assert bool(result) == accepted
    if result:
        assert result.events[0].time.end_date == date(2026, 10, 28)
        assert result.events[0].time.exact_at is None


@pytest.mark.parametrize(
    "day,utc_hour,kst_hour",
    [
        (date(2026, 3, 6), 13, 22),
        (date(2026, 3, 9), 12, 21),
        (date(2026, 10, 30), 12, 21),
        (date(2026, 11, 2), 13, 22),
    ],
)
def test_bea_confirmed_et_clock_uses_dst_and_explicit_source_period(day, utc_hour, kst_hour):
    coverage = SourceScheduleCoverage(start_date=day, end_date=day + timedelta(days=30))
    row = [
        day.strftime("%B ") + str(day.day) + " 8:30 AM",
        "News",
        "Personal Income and Outlays, January 2026",
    ]
    result = _insight_release(
        row, day.year, datetime(day.year, day.month, day.day, utc_hour, 30, tzinfo=UTC), coverage
    )
    event = result.events[0]
    assert event.time.exact_at.hour == utc_hour
    from zoneinfo import ZoneInfo

    assert event.time.exact_at.astimezone(ZoneInfo("Asia/Seoul")).hour == kst_hour
    assert event.details.target_period == "2026-01"


@pytest.mark.parametrize("clock", ["8:30 XX", "13:30 PM", "2:30 AM"])
def test_ambiguous_or_nonexistent_bea_clock_stays_date_only(clock):
    day = date(2026, 3, 8)  # nonexistent 02:30 ET on DST transition
    result = _insight_release(
        ["March 8 " + clock, "News", "Personal Income and Outlays, January 2026"],
        2026,
        datetime(2026, 3, 8, 15, tzinfo=UTC),
        SourceScheduleCoverage(start_date=day, end_date=day),
    )
    assert result.events[0].time.precision == "date"
    assert result.events[0].time.exact_at is None


def test_bea_missing_or_mismatched_declared_year_has_no_public_envelope():
    day = date(2026, 10, 29)
    row = ["October 29 8:30 AM", "News", "Personal Income and Outlays, September 2026"]
    coverage = SourceScheduleCoverage(start_date=day, end_date=day)
    for year in (None, 2027):
        assert (
            _insight_release(row, year, datetime(2026, 10, 29, 12, 30, tzinfo=UTC), coverage)
            is None
        )


async def test_bea_page_declared_year_is_used_without_changing_legacy_bytes():
    body = (
        b"<table><tr><th>Year 2026</th></tr><tr><td>October 29 8:30 AM</td>"
        b"<td>News</td><td>Personal Income and Outlays, September 2026</td></tr></table>"
    )
    window = FetchWindow.from_kst_date(date(2026, 10, 25))
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))
    ) as client:
        old = await UsEconomicCalendarAdapter().fetch(client, window)
        new = await UsEconomicCalendarAdapter().fetch(
            client, replace(window, insights_enabled=True)
        )
    assert new[0].insight_envelope.events[0].details.target_period == "2026-09"
    assert new[0].model_dump_json() == old[0].model_dump_json()


async def test_recorded_distinct_same_speaker_fed_events_keep_separate_occurrences():
    # Existing R10 recording, not a fabricated schedule.
    body = (FIXTURES / "fomc-calendar/upcoming.json").read_bytes()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))
    ) as client:
        items = await FomcCalendarAdapter().fetch(
            client, replace(FetchWindow.from_kst_date(date(2026, 2, 8)), insights_enabled=True)
        )
    matches = [
        i
        for i in items
        if i.title.endswith("Discussion - Governor Stephen I. Miran")
        and i.raw_metadata["scheduled_date"] == "2026-02-09"
    ]
    assert len(matches) == 2
    rows = [i.insight_envelope.events[0] for i in matches]
    assert len({row.event_id for row in rows}) == 2
    assert all(row.time.precision == "date" and row.time.exact_at is None for row in rows)
    from tests._helpers.upcoming_insights import module

    assert len(module(rows, now=datetime(2026, 2, 9, tzinfo=UTC)).events) == 2


def test_auction_without_cusip_uses_source_local_identity_and_no_invented_clock():
    day = date(2026, 10, 28)
    coverage = SourceScheduleCoverage(start_date=day, end_date=day)
    a = _insight_auction(
        dict(security_type="Note", security_term="2-Year", reopening="No"), day, coverage
    ).events[0]
    b = _insight_auction(
        dict(security_type="Bond", security_term="30-Year", reopening="Yes"), day, coverage
    ).events[0]
    assert a.event_id != b.event_id
    assert a.details.official_id.startswith("treasury:own:")
    assert a.time.exact_at is None
