"""Synthetic domain fixtures, never live source or licensing evidence."""

from datetime import UTC, datetime
from decimal import Decimal

from investo.models.coverage import SourceOutcome
from investo.models.insights import (
    InsightDefinitionQualification,
    InsightSourceQualification,
    InsightTime,
    SourceInsightEnvelope,
    SourceInsightMetric,
)
from investo.orchestrator.insights import InsightCapture
from investo.orchestrator.insights_projection import project_module

NOW = datetime(2026, 10, 9, 23, tzinfo=UTC)
HREF = "https://example.invalid/observations"


def metric(**updates):
    payload = dict(
        module="crypto",
        metric_id="synthetic",
        definition_id="fixture-v1",
        source_name="bybit-derivatives",
        provider="fixture",
        scope_id="venue",
        methodology_id="fixture-method",
        sample_policy="utc-day-last-confirmed",
        unit="percent",
        label="합성 관찰",
        value=Decimal("2.5"),
        time=InsightTime(basis="source_response", precision="exact", exact_at=NOW),
        endpoint=HREF,
        field_scope="value",
        source_href=HREF,
        cadence="snapshot",
    )
    payload.update(updates)
    return SourceInsightMetric(**payload)


def qualification(row=None, **updates):
    row = row or metric()
    payload = dict(
        source_name=row.source_name,
        endpoint=row.endpoint,
        field_scope=row.field_scope,
        definition_ids=(row.definition_id,),
        definitions=(
            InsightDefinitionQualification(
                definition_id=row.definition_id,
                module=row.module,
                public_id=row.metric_id,
                unit=row.unit,
                provider=row.provider,
                scope_id=row.scope_id,
                methodology_id=row.methodology_id,
                sample_policy=row.sample_policy,
                cadence=row.cadence,
                calendar_policy=row.calendar_policy,
            ),
        ),
        display_allowed=True,
        public_git_history_allowed=True,
        retention_allowed=True,
        evidence_hrefs=("https://example.invalid/terms",),
        checked_on=NOW.date(),
        attribution="Synthetic permission fixture",
        allowed_hrefs=(HREF,),
        runtime_probe_state="ok",
    )
    payload.update(updates)
    return InsightSourceQualification(**payload)


def capture(row=None, *, status="ok", origin=None):
    row = row or metric()
    origin = origin or row.source_name
    envelope = SourceInsightEnvelope(
        source_name=row.source_name, origin_adapter_name=origin, metrics=(row,)
    )
    outcome = (
        SourceOutcome.ok(origin, "macro", 1)
        if status == "ok"
        else SourceOutcome.zero(origin, "macro")
    )
    return InsightCapture((envelope,), (outcome,))


def module(row=None, *, qualifications=None, previous=None, now=NOW, captured=None):
    row = row or metric()
    return project_module(
        row.module,
        captured or capture(row),
        qualifications if qualifications is not None else (qualification(row),),
        run_started_at=now,
        collection_completed_at=now,
        evaluated_at=now,
        previous=previous,
    )
