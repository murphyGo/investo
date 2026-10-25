"""Explicit synthetic u181 fixtures; never production source/permission evidence."""

from datetime import UTC, datetime

from investo.models.coverage import SourceOutcome
from investo.models.insights import InsightSourceQualification, InsightTime, SourceInsightEnvelope
from investo.models.insights_calendar import expected_observation
from investo.models.insights_macro import MACRO_BY_ID, MACRO_RECIPES
from investo.orchestrator.insights import InsightCapture
from investo.orchestrator.insights_projection import project_module

NOW = datetime(2026, 10, 23, 23, tzinfo=UTC)
VALUES = dict(
    ust_3m="4.50",
    ust_2y="4.10",
    ust_10y="4.30",
    ust_30y="4.80",
    sofr="4.25",
    effr="4.10",
    usd_krw_h10="1390.25",
    cpi_sa_index="315.50",
    core_cpi_sa_index="330.10",
    unemployment_rate="4.20",
)


def qualifications():
    return tuple(
        InsightSourceQualification(
            source_name=r.source_name,
            endpoint=r.endpoint,
            field_scope=r.field_scope,
            definition_ids=(r.metric_id + ".v1",),
            definitions=(r.definition(),),
            display_allowed=True,
            public_git_history_allowed=True,
            retention_allowed=True,
            evidence_hrefs=("https://example.invalid/synthetic-permission",),
            checked_on=NOW.date(),
            attribution="Synthetic permission fixture; not a provider license",
            runtime_probe_state="ok",
            allowed_hrefs=(r.endpoint, r.href),
        )
        for r in MACRO_RECIPES
    )


def capture(overrides=None):
    values = {**VALUES, **(overrides or {})}
    envelopes = []
    for mid, value in values.items():
        r = MACRO_BY_ID[mid]
        clock = (
            InsightTime(
                basis="period",
                precision="month",
                period="2026-09",
                source_timezone="America/New_York",
            )
            if r.cadence == "monthly"
            else InsightTime(
                basis="effective_date",
                precision="date",
                local_date=expected_observation(NOW, r.calendar_policy),
                source_timezone="America/New_York",
            )
        )
        envelopes.append(
            SourceInsightEnvelope(
                source_name=r.source_name,
                origin_adapter_name=r.source_name,
                metrics=(r.metric(value, clock),),
            )
        )
    return InsightCapture(
        tuple(envelopes),
        tuple(
            SourceOutcome.ok(name, "macro", 1)
            for name in sorted({r.source_name for r in MACRO_RECIPES})
        ),
    )


def module(captured=None, rights=None):
    return project_module(
        "macro",
        captured or capture(),
        qualifications() if rights is None else rights,
        run_started_at=NOW,
        collection_completed_at=NOW,
        evaluated_at=NOW,
    )
