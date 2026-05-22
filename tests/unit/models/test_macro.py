"""u59 macro metadata helper tests."""

from __future__ import annotations

from datetime import UTC, datetime

from investo.models import NormalizedItem
from investo.models.macro import (
    is_required_macro_actual,
    macro_event_date,
    macro_event_key,
    macro_event_status,
    macro_priority,
    macro_prompt_payload,
    macro_required_sections,
)


def _item(
    *,
    source_name: str,
    category: str = "calendar",
    title: str = "macro item",
    raw_metadata: dict[str, str] | None = None,
    scheduled_at: datetime | None = None,
) -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name,
        category=category,  # type: ignore[arg-type]
        title=title,
        published_at=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
        scheduled_at=scheduled_at,
        raw_metadata=raw_metadata or {},
    )


def test_fred_calendar_ppi_infers_p1_scheduled_event_key() -> None:
    item = _item(
        source_name="fred-economic-calendar",
        raw_metadata={
            "release_id": "46",
            "release_name": "Producer Price Index",
            "scheduled_date": "2026-05-13",
        },
        scheduled_at=datetime(2026, 5, 13, tzinfo=UTC),
    )

    assert macro_event_key(item) == (
        "fred-economic-calendar:release_id=46:scheduled_date=2026-05-13"
    )
    assert macro_event_status(item) == "scheduled"
    assert macro_priority(item) == "P1"
    assert macro_event_date(item).isoformat() == "2026-05-13"


def test_fred_macro_cpi_infers_p0_required_actual() -> None:
    item = _item(
        source_name="fred-macro",
        category="macro",
        raw_metadata={
            "series_id": "CPIAUCSL",
            "value": "314.12",
            "previous_value": "313.55",
            "release_date": "2026-05-12",
        },
    )

    assert macro_event_key(item) == "fred-macro:series_id=CPIAUCSL:release_date=2026-05-12"
    assert macro_event_status(item) == "actual"
    assert macro_priority(item) == "P0"
    assert is_required_macro_actual(item) is True
    assert macro_required_sections(item) == (0, 2, 4)


def test_explicit_macro_metadata_overrides_inference_and_keeps_flat_sections() -> None:
    item = _item(
        source_name="custom-official-macro",
        category="macro",
        raw_metadata={
            "macro_event_key": "us:PPI:2026-05",
            "macro_event_status": "actual",
            "macro_priority": "p0",
            "macro_event_label": "Producer Price Index",
            "macro_actual": "+1.4%",
            "macro_prior": "+0.2%",
            "macro_release_period": "2026-04",
            "required_sections": "0, 2, 4, 2, bogus",
        },
    )

    assert macro_event_key(item) == "us:PPI:2026-05"
    assert macro_event_status(item) == "actual"
    assert macro_priority(item) == "P0"
    assert macro_required_sections(item) == (0, 2, 4)
    assert macro_prompt_payload(item) == {
        "event_key": "us:PPI:2026-05",
        "priority": "P0",
        "status": "actual",
        "label": "Producer Price Index",
        "actual": "+1.4%",
        "prior": "+0.2%",
        "release_period": "2026-04",
        "required_sections": "0,2,4",
    }


def test_non_macro_item_has_no_macro_prompt_payload() -> None:
    item = _item(source_name="yahoo-finance-news", category="news", title="ordinary market news")
    assert macro_event_key(item) is None
    assert macro_event_status(item) is None
    assert macro_priority(item) is None
    assert macro_prompt_payload(item) is None
