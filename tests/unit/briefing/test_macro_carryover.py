"""u59 macro lifecycle JSONL persistence + transition tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from investo.briefing.macro_carryover import (
    advance_macro_lifecycle,
    load_macro_lifecycle_events,
    upsert_macro_lifecycle_snapshot,
)
from investo.models import MacroLifecycleEvent, NormalizedItem

_PPI_KEY = "fred-economic-calendar:release_id=46:scheduled_date=2026-05-13"
_PPI_ACTUAL_KEY = "fred-macro:series_id=PPIFID:release_date=2026-05-13"


def _event(
    event_key: str = _PPI_KEY,
) -> MacroLifecycleEvent:
    return MacroLifecycleEvent(
        event_key=event_key,
        label="Producer Price Index",
        source_name="fred-economic-calendar",
        segment="us-equity",
        status="scheduled",
        scheduled_date=date(2026, 5, 13),
    )


def _schedule_item(
    scheduled: date = date(2026, 5, 13),
    *,
    event_key: str | None = None,
) -> NormalizedItem:
    metadata: dict[str, str] = {
        "release_id": "46",
        "release_name": "Producer Price Index",
        "scheduled_date": scheduled.isoformat(),
    }
    if event_key is not None:
        metadata["macro_event_key"] = event_key
    return NormalizedItem(
        source_name="fred-economic-calendar",
        category="calendar",
        title="Producer Price Index",
        published_at=datetime(2026, 5, 1, tzinfo=UTC),
        scheduled_at=datetime(scheduled.year, scheduled.month, scheduled.day, 12, tzinfo=UTC),
        raw_metadata=metadata,
    )


def _actual_item(
    release: date = date(2026, 5, 13),
    *,
    event_key: str | None = None,
) -> NormalizedItem:
    metadata: dict[str, str] = {
        "series_id": "PPIFID",
        "release_date": release.isoformat(),
        "macro_event_label": "Producer Price Index",
        "value": "144.2",
    }
    if event_key is not None:
        metadata["macro_event_key"] = event_key
        metadata["macro_event_status"] = "actual"
    return NormalizedItem(
        source_name="fred-macro",
        category="macro",
        title="Producer Price Index by Commodity: Final Demand",
        published_at=datetime(release.year, release.month, release.day, 13, tzinfo=UTC),
        raw_metadata=metadata,
    )


def test_upsert_macro_lifecycle_snapshot_replaces_same_day_rows(tmp_path: Path) -> None:
    path = tmp_path / "macro_event_carryover.jsonl"
    upsert_macro_lifecycle_snapshot(date(2026, 5, 13), [_event("old")], path=path)
    upsert_macro_lifecycle_snapshot(date(2026, 5, 13), [_event("new")], path=path)

    events = load_macro_lifecycle_events(path)

    assert [event.event_key for event in events] == ["new"]


def test_load_macro_lifecycle_events_skips_corrupt_rows(tmp_path: Path) -> None:
    path = tmp_path / "macro_event_carryover.jsonl"
    upsert_macro_lifecycle_snapshot(date(2026, 5, 13), [_event()], path=path)
    path.write_text("{broken\n" + path.read_text(encoding="utf-8"), encoding="utf-8")

    events = load_macro_lifecycle_events(path)

    assert len(events) == 1
    assert events[0].event_key.startswith("fred-economic-calendar:")


_SHARED = "us:PPI:2026-05"


def test_new_future_event_is_scheduled() -> None:
    events = advance_macro_lifecycle(
        (),
        [_schedule_item(date(2026, 5, 13), event_key=_SHARED)],
        date(2026, 5, 10),
    )

    assert [(e.event_key, e.status) for e in events] == [(_SHARED, "scheduled")]
    assert events[0].scheduled_date == date(2026, 5, 13)


def test_release_day_without_actual_is_unresolved_and_carries() -> None:
    prior = advance_macro_lifecycle(
        (), [_schedule_item(date(2026, 5, 13), event_key=_SHARED)], date(2026, 5, 10)
    )

    # Release day arrives; the schedule item is still collected but no actual.
    on_day = advance_macro_lifecycle(
        prior, [_schedule_item(date(2026, 5, 13), event_key=_SHARED)], date(2026, 5, 13)
    )
    assert [(e.event_key, e.status) for e in on_day] == [(_SHARED, "unresolved")]

    # Next run with the event no longer collected: it still carries forward.
    carried = advance_macro_lifecycle(on_day, [], date(2026, 5, 14))
    assert [(e.event_key, e.status) for e in carried] == [(_SHARED, "unresolved")]


def test_actual_confirms_by_event_key_and_sets_follow_up() -> None:
    prior = advance_macro_lifecycle(
        (), [_schedule_item(date(2026, 5, 13), event_key=_SHARED)], date(2026, 5, 10)
    )

    confirmed = advance_macro_lifecycle(
        prior,
        [_actual_item(date(2026, 5, 13), event_key=_SHARED)],
        date(2026, 5, 13),
    )

    assert [(e.event_key, e.status) for e in confirmed] == [(_SHARED, "confirmed")]
    event = confirmed[0]
    assert event.confirmed_date == date(2026, 5, 13)
    assert event.follow_up_until == date(2026, 5, 14)


def test_confirmed_event_drops_after_follow_up_day() -> None:
    confirmed = advance_macro_lifecycle(
        (), [_actual_item(date(2026, 5, 13), event_key=_SHARED)], date(2026, 5, 13)
    )
    assert confirmed[0].follow_up_until == date(2026, 5, 14)

    # Follow-up day: still kept even when not re-collected.
    follow_up = advance_macro_lifecycle(confirmed, [], date(2026, 5, 14))
    assert [(e.event_key, e.status) for e in follow_up] == [(_SHARED, "confirmed")]

    # Day after follow_up_until: dropped.
    dropped = advance_macro_lifecycle(follow_up, [], date(2026, 5, 15))
    assert dropped == ()


def test_unresolved_event_goes_stale_past_confirmation_window() -> None:
    # scheduled 5/13; window = release day + 1 grace day (through 5/14).
    on_day = advance_macro_lifecycle(
        (), [_schedule_item(date(2026, 5, 13), event_key=_SHARED)], date(2026, 5, 13)
    )
    assert on_day[0].status == "unresolved"

    grace = advance_macro_lifecycle(on_day, [], date(2026, 5, 14))
    assert grace[0].status == "unresolved"

    stale = advance_macro_lifecycle(grace, [], date(2026, 5, 15))
    assert [(e.event_key, e.status) for e in stale] == [(_SHARED, "stale")]


def test_confirmation_is_by_event_key_not_substring() -> None:
    # A scheduled event keyed differently from an unrelated actual print
    # with a similar label must NOT be confirmed by it.
    scheduled = advance_macro_lifecycle(
        (), [_schedule_item(date(2026, 5, 13), event_key="us:PPI:2026-05")], date(2026, 5, 10)
    )

    # An actual whose label also says "Producer Price Index" but with a
    # different event_key (different release period).
    other_actual = _actual_item(date(2026, 5, 13), event_key="us:PPI:2026-04")
    result = advance_macro_lifecycle(scheduled, [other_actual], date(2026, 5, 13))

    by_key = {e.event_key: e.status for e in result}
    # The May schedule stays unresolved (its key was not confirmed)...
    assert by_key["us:PPI:2026-05"] == "unresolved"
    # ...and the April actual is tracked separately as confirmed.
    assert by_key["us:PPI:2026-04"] == "confirmed"


def test_distinct_inferred_keys_for_calendar_and_fred_macro() -> None:
    # Without explicit keys, calendar schedule and fred-macro actual carry
    # different inferred event keys (current event-identity model).
    result = advance_macro_lifecycle(
        (),
        [_schedule_item(date(2026, 5, 13)), _actual_item(date(2026, 5, 13))],
        date(2026, 5, 13),
    )
    by_key = {e.event_key: e.status for e in result}
    assert by_key[_PPI_KEY] == "unresolved"
    assert by_key[_PPI_ACTUAL_KEY] == "confirmed"


def test_transition_output_is_deterministically_sorted() -> None:
    items = [
        _actual_item(date(2026, 5, 13), event_key="zzz"),
        _schedule_item(date(2026, 5, 20), event_key="aaa"),
    ]
    result = advance_macro_lifecycle((), items, date(2026, 5, 13))
    assert [e.event_key for e in result] == ["aaa", "zzz"]
