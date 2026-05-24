"""u59 macro lifecycle JSONL persistence tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from investo.briefing.macro_carryover import (
    load_macro_lifecycle_events,
    upsert_macro_lifecycle_snapshot,
)
from investo.models import MacroLifecycleEvent


def _event(
    event_key: str = "fred-economic-calendar:release_id=46:scheduled_date=2026-05-13",
) -> MacroLifecycleEvent:
    return MacroLifecycleEvent(
        event_key=event_key,
        label="Producer Price Index",
        source_name="fred-economic-calendar",
        segment="us-equity",
        status="scheduled",
        scheduled_date=date(2026, 5, 13),
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
