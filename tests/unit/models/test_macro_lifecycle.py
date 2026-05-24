"""u59 macro lifecycle model tests."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from investo.models import MacroLifecycleEvent


def test_scheduled_macro_lifecycle_requires_scheduled_date() -> None:
    with pytest.raises(ValidationError):
        MacroLifecycleEvent(
            event_key="fred-economic-calendar:release_id=46:scheduled_date=2026-05-13",
            label="Producer Price Index",
            source_name="fred-economic-calendar",
            segment="us-equity",
            status="scheduled",
        )


def test_confirmed_macro_lifecycle_requires_confirmed_date() -> None:
    with pytest.raises(ValidationError):
        MacroLifecycleEvent(
            event_key="fred-macro:series_id=PPIFID:release_date=2026-05-13",
            label="Producer Price Index",
            source_name="fred-macro",
            segment="us-equity",
            status="confirmed",
        )


def test_macro_lifecycle_event_accepts_confirmed_follow_up_window() -> None:
    event = MacroLifecycleEvent(
        event_key="fred-macro:series_id=PPIFID:release_date=2026-05-13",
        label="Producer Price Index",
        source_name="fred-macro",
        segment="us-equity",
        status="confirmed",
        confirmed_date=date(2026, 5, 13),
        follow_up_until=date(2026, 5, 14),
    )

    assert event.follow_up_until == date(2026, 5, 14)
