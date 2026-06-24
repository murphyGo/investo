"""u59 macro metadata helper tests."""

from __future__ import annotations

from datetime import UTC, datetime

from investo.models import NormalizedItem
from investo.models.macro import (
    MacroMetadataIssue,
    is_required_macro_actual,
    macro_event_date,
    macro_event_key,
    macro_event_status,
    macro_metadata_view,
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
    view = macro_metadata_view(item)
    assert view.event_key == "us:PPI:2026-05"
    assert view.status == "actual"
    assert view.priority == "P0"
    assert view.label == "Producer Price Index"
    assert view.actual == "+1.4%"
    assert view.prior == "+0.2%"
    assert view.release_period == "2026-04"
    assert view.required_sections == (0, 2, 4)
    assert view.issues == (
        MacroMetadataIssue(
            code="invalid_required_section",
            key="required_sections",
            value="bogus",
        ),
    )


def test_macro_metadata_view_converts_numeric_primitives_to_strings() -> None:
    item = _item(
        source_name="custom-official-macro",
        category="macro",
        raw_metadata={
            "macro_event_key": "us:CPI:2026-05",
            "macro_event_status": "actual",
            "macro_priority": "P1",
            "macro_actual": 3.2,  # type: ignore[dict-item]
            "macro_prior": 3,  # type: ignore[dict-item]
        },
    )

    view = macro_metadata_view(item)
    assert view.actual == "3.2"
    assert view.prior == "3"
    assert macro_prompt_payload(item) == {
        "event_key": "us:CPI:2026-05",
        "priority": "P1",
        "status": "actual",
        "actual": "3.2",
        "prior": "3",
    }


def test_invalid_macro_enum_values_do_not_fall_back_to_inference() -> None:
    item = _item(
        source_name="fred-macro",
        category="macro",
        raw_metadata={
            "series_id": "CPIAUCSL",
            "release_date": "2026-05-12",
            "macro_event_status": "done",
            "macro_priority": "critical",
        },
    )

    view = macro_metadata_view(item)
    assert view.event_key == "fred-macro:series_id=CPIAUCSL:release_date=2026-05-12"
    assert view.status is None
    assert view.priority is None
    assert is_required_macro_actual(item) is False
    assert macro_prompt_payload(item) == {
        "event_key": "fred-macro:series_id=CPIAUCSL:release_date=2026-05-12",
        "release_period": "2026-05-12",
    }
    assert view.issues == (
        MacroMetadataIssue(
            code="invalid_macro_event_status",
            key="macro_event_status",
            value="done",
        ),
        MacroMetadataIssue(
            code="invalid_macro_priority",
            key="macro_priority",
            value="critical",
        ),
    )


def test_macro_metadata_view_reports_malformed_dates_and_falls_back() -> None:
    item = _item(
        source_name="fred-economic-calendar",
        raw_metadata={
            "release_id": "46",
            "scheduled_date": "2026-99-99",
        },
        scheduled_at=datetime(2026, 5, 13, tzinfo=UTC),
    )

    view = macro_metadata_view(item)
    assert view.event_date is None
    assert macro_event_date(item).isoformat() == "2026-05-13"
    assert view.issues == (
        MacroMetadataIssue(
            code="invalid_macro_event_date",
            key="scheduled_date",
            value="2026-99-99",
        ),
    )


def test_macro_metadata_view_keeps_release_period_strings_out_of_date_issues() -> None:
    item = _item(
        source_name="bea-macro-actuals",
        category="macro",
        raw_metadata={
            "macro_event_key": "us:GDP:period=2026Q1",
            "macro_event_status": "actual",
            "macro_priority": "P1",
            "release_period": "2026Q1",
        },
    )

    view = macro_metadata_view(item)
    assert view.release_period == "2026Q1"
    assert view.event_date is None
    assert view.issues == ()
    assert macro_event_date(item).isoformat() == "2026-05-13"


def test_explicit_required_macro_actual_gets_default_required_sections() -> None:
    item = _item(
        source_name="custom-official-macro",
        category="macro",
        raw_metadata={
            "macro_event_key": "us:CPI:period=2026-05",
            "macro_event_status": "actual",
            "macro_priority": "P1",
            "required_macro_actual": "true",
        },
    )

    assert is_required_macro_actual(item) is True
    assert macro_required_sections(item) == (0, 2, 4)
    assert macro_prompt_payload(item) == {
        "event_key": "us:CPI:period=2026-05",
        "priority": "P1",
        "status": "actual",
        "required_sections": "0,2,4",
    }


def test_macro_metadata_view_reports_invalid_required_sections() -> None:
    item = _item(
        source_name="custom-official-macro",
        category="macro",
        raw_metadata={
            "macro_event_key": "us:CPI:2026-05",
            "macro_event_status": "actual",
            "macro_priority": "P0",
            "required_sections": "0, 1, 2, nope, 6",
        },
    )

    view = macro_metadata_view(item)
    assert view.required_sections == (0, 2, 6)
    assert view.issues == (
        MacroMetadataIssue(
            code="invalid_required_section",
            key="required_sections",
            value="1",
        ),
        MacroMetadataIssue(
            code="invalid_required_section",
            key="required_sections",
            value="nope",
        ),
    )


def test_non_macro_item_has_no_macro_prompt_payload() -> None:
    item = _item(source_name="yahoo-finance-news", category="news", title="ordinary market news")
    assert macro_event_key(item) is None
    assert macro_event_status(item) is None
    assert macro_priority(item) is None
    assert macro_prompt_payload(item) is None
