"""Explicitly synthetic u182 schedules and permissions; no operational evidence."""

from datetime import UTC, date, datetime, timedelta

from investo.models.coverage import SourceOutcome
from investo.models.insights import (
    InsightSourceQualification,
    InsightTime,
    SourceInsightEnvelope,
    SourceScheduleCoverage,
)
from investo.models.insights_events import (
    AUCTION_RECIPE,
    BEA_RECIPES,
    CALENDAR_SOURCES,
    EVENT_RECIPES,
    FED_RECIPES,
    FRED_RECIPES,
)
from investo.orchestrator.insights import InsightCapture
from investo.orchestrator.insights_projection import project_module

NOW = datetime(2026, 10, 25, tzinfo=UTC)


def local(day, end=None):
    return InsightTime(
        basis="schedule",
        precision="date",
        source_timezone="America/New_York",
        **({"local_date": day} if end is None else {"start_date": day, "end_date": end}),
    )


def exact(at):
    return InsightTime(
        basis="schedule", precision="exact", exact_at=at, source_timezone="America/New_York"
    )


def events():
    return (
        FED_RECIPES["meeting"].event(local(date(2026, 10, 27), date(2026, 10, 28)), "fed:meeting"),
        FED_RECIPES["press_conference"].event(local(date(2026, 10, 28)), "fed:press"),
        FED_RECIPES["statement"].event(local(date(2026, 10, 28)), "fed:statement"),
        FED_RECIPES["minutes"].event(local(date(2026, 11, 18)), "fed:minutes"),
        BEA_RECIPES["gdp"].event(
            exact(datetime(2026, 10, 29, 12, 30, tzinfo=UTC)), "bea:gdp", target_period="2026-Q3"
        ),
        BEA_RECIPES["pce"].event(
            exact(datetime(2026, 10, 29, 12, 30, tzinfo=UTC)), "bea:pce", target_period="2026-09"
        ),
        FRED_RECIPES["10"].event(local(date(2026, 11, 10)), "fred:10"),
        AUCTION_RECIPE.event(
            local(date(2026, 10, 28)),
            "treasury:912345678",
            instrument="10-Year Note",
            reopening="yes",
        ),
    )


def qualifications():
    return tuple(
        InsightSourceQualification(
            source_name=r.source_name,
            endpoint=r.endpoint,
            field_scope=r.field_scope,
            definition_ids=(r.definition_id,),
            definitions=(r.definition(),),
            display_allowed=True,
            public_git_history_allowed=True,
            retention_allowed=False,
            evidence_hrefs=("https://example.invalid/synthetic-permission",),
            checked_on=NOW.date(),
            attribution="Synthetic permission fixture only",
            allowed_hrefs=(r.endpoint, r.href),
        )
        for r in EVENT_RECIPES
    )


def capture(rows=None, statuses=None):
    rows = events() if rows is None else rows
    statuses = statuses or {}
    return InsightCapture(
        tuple(
            SourceInsightEnvelope(
                source_name=r.source_name,
                origin_adapter_name=r.source_name,
                events=(r,),
                schedule_coverage=SourceScheduleCoverage(
                    start_date=NOW.date(), end_date=NOW.date() + timedelta(days=30)
                ),
            )
            for r in rows
        ),
        tuple(
            SourceOutcome(
                source_name=name,
                category="calendar",
                status=statuses.get(name, "ok"),
                # A synthetic legacy-only item may lack a typed envelope.
                item_count=max(1, sum(r.source_name == name for r in rows))
                if statuses.get(name, "ok") == "ok"
                else 0,
                failure_reason="Synthetic source failure"
                if statuses.get(name) == "failed"
                else None,
                transient=True if statuses.get(name) == "failed" else None,
                skip_reason="operator_disabled" if statuses.get(name) == "skipped" else None,
            )
            for name in CALENDAR_SOURCES
        ),
    )


def module(rows=None, *, now=NOW, previous=None, rights=None, statuses=None, captured=None):
    return project_module(
        "calendar",
        captured or capture(rows, statuses),
        qualifications() if rights is None else rights,
        run_started_at=now,
        collection_completed_at=now,
        evaluated_at=now,
        previous=previous,
    )
