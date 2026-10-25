"""Synthetic domain cases for date precision, conservative identity and source isolation."""

from datetime import UTC, date, datetime, timedelta

import pytest

from investo.models.insights import InsightTime, canonical_bytes
from investo.models.insights_events import (
    AUCTION_RECIPE,
    BEA_RECIPES,
    FED_RECIPES,
    FRED_RECIPES,
    in_range,
    range_anchor,
)
from tests._helpers.upcoming_insights import (
    NOW,
    events,
    exact,
    local,
    module,
    qualifications,
)


def test_range_and_kind_are_preserved_without_midnight_instants():
    result = module()
    assert len(result.events) == 8
    meeting = next(e for e in result.events if e.details.kind == "fomc_meeting")
    assert (meeting.time.start_date, meeting.time.end_date) == (
        date(2026, 10, 27),
        date(2026, 10, 28),
    )
    assert meeting.time.exact_at is None
    assert len({e.event_id for e in result.events if e.source_name == "fomc-calendar"}) == 4
    assert result.calendar_coverage.selected_count == 8


def test_local_day_window_and_kst_window_have_distinct_anchors():
    now = datetime(2026, 10, 25, 0, tzinfo=UTC)  # KST25, New York24
    row = FRED_RECIPES["10"].event(local(date(2026, 10, 24)), "fred:10")
    assert range_anchor(row, now) == date(2026, 10, 24)
    assert module((row,), now=now).events
    exact_row = BEA_RECIPES["pce"].event(exact(datetime(2026, 10, 24, 23, tzinfo=UTC)), "bea:pce")
    assert range_anchor(exact_row, now) == date(2026, 10, 25)
    assert in_range(exact_row, range_anchor(exact_row, now), 7)


def test_fred_inferred_period_is_never_promoted_or_joined_to_verified_bea_period():
    bea = events()[4]
    fred = FRED_RECIPES["53"].event(local(date(2026, 10, 29)), "fred:53")
    result = module((bea, fred))
    assert len(result.events) == 2
    assert (
        next(
            e for e in result.events if e.source_name == "fred-economic-calendar"
        ).details.target_period
        is None
    )


def test_reviewed_family_with_equal_null_period_merges_refs_and_keeps_exact_clock():
    bea = BEA_RECIPES["gdp"].event(exact(datetime(2026, 10, 29, 12, 30, tzinfo=UTC)), "bea:gdp")
    fred = FRED_RECIPES["53"].event(local(date(2026, 10, 29)), "fred:53")
    result = module((fred, bea))
    assert len(result.events) == 1 and len(result.events[0].references) == 1
    assert result.events[0].source_name == "us-economic-calendar"
    assert result.events[0].time.precision == "exact"
    assert module((bea, fred)).snapshot_id == result.snapshot_id


def test_similar_labels_without_reviewed_family_never_merge():
    a = FRED_RECIPES["10"].event(local(date(2026, 10, 29)), "fred:10")
    b = FRED_RECIPES["46"].event(local(date(2026, 10, 29)), "fred:46")
    assert len(module((a, b)).events) == 2


def test_conflicting_same_occurrence_is_removed_and_counted():
    a = BEA_RECIPES["gdp"].event(exact(datetime(2026, 10, 29, 12, 30, tzinfo=UTC)), "bea:gdp")
    b = BEA_RECIPES["gdp"].event(exact(datetime(2026, 10, 29, 13, 30, tzinfo=UTC)), "bea:gdp")
    assert a.event_id == b.event_id
    result = module((a, b, events()[-1]))
    assert len(result.events) == 1
    assert result.calendar_coverage.conflict_count == 1
    assert "definition_conflict" in result.reasons


@pytest.mark.parametrize(
    "clock",
    [
        InsightTime(basis="schedule", precision="unknown"),
        local(date(2026, 10, 26), date(2026, 11, 5)),
        InsightTime(
            basis="effective_date",
            precision="date",
            local_date=date(2026, 10, 29),
            source_timezone="America/New_York",
        ),
    ],
)
def test_invalid_precision_or_long_range_does_not_remove_siblings(clock):
    row = events()[0].model_copy(update={"time": clock})
    result = module((row, events()[-1]))
    assert len(result.events) == 1 and result.events[0].source_name == "treasury-auctions"
    assert result.calendar_coverage.invalid_count == 1


def test_expired_or_removed_schedule_does_not_assert_actual_or_cancellation():
    old = module()
    later = module(
        (), now=NOW + timedelta(days=40), previous=old, statuses={"fomc-calendar": "failed"}
    )
    assert not later.events
    assert "actual" not in canonical_bytes(later).decode()
    replacement = module((), previous=old)
    assert not replacement.events


def test_last_good_keeps_original_collection_clock_and_rights_are_rechecked():
    old = module()
    now = NOW + timedelta(hours=40)
    current = module(
        (),
        now=now,
        previous=old,
        statuses={
            n: "failed"
            for n in (
                "fomc-calendar",
                "us-economic-calendar",
                "fred-economic-calendar",
                "treasury-auctions",
            )
        },
    )
    assert current.events and all(
        e.last_good and e.freshness == "stale" and e.collection_completed_at == NOW
        for e in current.events
    )
    revoked = [
        q.model_copy(update={"revoked": True}) if q.source_name == "fomc-calendar" else q
        for q in qualifications()
    ]
    current = module(
        (), now=now, previous=old, statuses={"fomc-calendar": "failed"}, rights=revoked
    )
    assert not any(e.source_name == "fomc-calendar" for e in current.events)
    assert "rights_revoked" in current.reasons


def test_revoked_merged_primary_can_fall_back_to_qualified_secondary():
    bea = BEA_RECIPES["gdp"].event(exact(datetime(2026, 10, 29, 12, 30, tzinfo=UTC)), "bea:gdp")
    fred = FRED_RECIPES["53"].event(local(date(2026, 10, 29)), "fred:53")
    old = module((bea, fred))
    revoked = [
        q.model_copy(update={"revoked": True}) if q.source_name == "us-economic-calendar" else q
        for q in qualifications()
    ]
    result = module(
        (),
        previous=old,
        rights=revoked,
        statuses={"us-economic-calendar": "failed", "fred-economic-calendar": "failed"},
    )
    assert len(result.events) == 1 and result.events[0].source_name == "fred-economic-calendar"
    assert not result.events[0].references


def test_deterministic_128_selection_reports_excluded_events():
    rows = tuple(
        FED_RECIPES["speech"].event(local(date(2026, 10, 26)), f"fed:{i:03}") for i in range(140)
    )
    result = module(rows)
    assert len(result.events) == 128 and result.calendar_coverage.excluded_count == 12
    assert result.availability == "limited"
    assert module(tuple(reversed(rows))).snapshot_id == result.snapshot_id


def test_publication_permissions_and_unavailable_source_are_not_empty_calendar():
    rights = [
        q.model_copy(update={"public_git_history_allowed": False})
        if q.source_name == "fred-economic-calendar"
        else q
        for q in qualifications()
    ]
    result = module(rights=rights, statuses={"fomc-calendar": "failed"})
    assert not any(
        e.source_name in {"fomc-calendar", "fred-economic-calendar"} for e in result.events
    )
    status = {s.source_name: s for s in result.calendar_coverage.sources}
    assert status["fomc-calendar"].latest_attempt == "failed"
    assert status["fred-economic-calendar"].rights == "blocked"


def test_auction_identity_includes_reopening_and_missing_cusip_own_key():
    clock = local(date(2026, 10, 28))
    rows = [AUCTION_RECIPE.event(clock, "treasury:912345678", reopening=x) for x in ("yes", "no")]
    rows.append(AUCTION_RECIPE.event(clock, "treasury:own:other"))
    assert len(module(rows).events) == 3


def test_legacy_v1_numeric_snapshot_roundtrip_omits_new_calendar_fields():
    from investo.models.insights import ValidatedInsightModule
    from tests._helpers.macro_insights import module as macro_module

    value = macro_module()
    encoded = canonical_bytes(value)
    assert b"calendar_coverage" not in encoded
    assert ValidatedInsightModule.model_validate_json(encoded) == value
