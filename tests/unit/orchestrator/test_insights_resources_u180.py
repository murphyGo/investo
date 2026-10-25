"""Synthetic maximum cardinalities/caps; no source recording or runtime activation."""

from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from investo.models.coverage import SourceOutcome
from investo.models.insights import (
    InsightHistory,
    InsightHistoryRow,
    InsightTime,
    SourceInsightEnvelope,
    canonical_bytes,
    digest,
)
from investo.orchestrator.insights import InsightCapture
from investo.orchestrator.insights_projection import project_module, update_history
from tests._helpers.insights import NOW, capture, metric, module, qualification


def maximum_capture():
    metrics = tuple(
        metric(metric_id=f"m{i}", definition_id=f"d{i}", field_scope=f"v{i}") for i in range(32)
    )
    envelopes = tuple(
        SourceInsightEnvelope(
            source_name=metrics[0].source_name,
            origin_adapter_name=metrics[0].source_name,
            metrics=metrics[i : i + 16],
        )
        for i in (0, 16)
    )
    return InsightCapture(envelopes, capture().outcomes), tuple(
        qualification(row) for row in metrics
    )


def maximum_module():
    captured, qualified = maximum_capture()
    return project_module(
        "crypto",
        captured,
        qualified,
        run_started_at=NOW,
        collection_completed_at=NOW,
        evaluated_at=NOW,
    ), qualified


def test_32_metrics_supported_and_33_suppressed():
    current, qualified = maximum_module()
    assert len(current.metrics) == 32
    captured, _ = maximum_capture()
    extra = metric(metric_id="m32", definition_id="d32", field_scope="v32")
    envelope = SourceInsightEnvelope(
        source_name=extra.source_name, origin_adapter_name=extra.source_name, metrics=(extra,)
    )
    overloaded = InsightCapture((*captured.envelopes, envelope), captured.outcomes)
    result = module(captured=overloaded, qualifications=(*qualified, qualification(extra)))
    assert not result.metrics and "invalid_value" in result.reasons


def test_history_max_366_then_bounded_retention():
    current = module()
    initial = update_history(current, None, (qualification(),))
    key = initial.definitions[0].key
    rows = []
    for offset in range(366):
        stamp = NOW - timedelta(days=offset)
        clock = InsightTime(basis="source_response", precision="exact", exact_at=stamp)
        value = Decimal(offset)
        rows.append(
            InsightHistoryRow(
                definition_key=key,
                observation_key=stamp.date().isoformat(),
                value=value,
                time=clock,
                record_hash=digest(
                    canonical_bytes({"value": str(value), "time": clock.model_dump(mode="json")})
                ),
            )
        )
    history = InsightHistory(module="crypto", definitions=initial.definitions, rows=tuple(rows))
    next_current = module(
        metric(
            time=InsightTime(
                basis="source_response", precision="exact", exact_at=NOW + timedelta(days=1)
            )
        ),
        now=NOW + timedelta(days=1),
    )
    updated = update_history(next_current, history, (qualification(),))
    assert len(updated.rows) == 366
    assert min(row.observation_key for row in updated.rows) > min(
        row.observation_key for row in history.rows
    )
    with pytest.raises(ValidationError):
        InsightHistory(
            module="crypto", definitions=initial.definitions, rows=(*history.rows, updated.rows[-1])
        )


def test_private_aggregate_cap_suppresses_without_last_good():
    row = metric(label="x" * 160, endpoint="https://example.invalid/" + "x" * 900)
    envelope = SourceInsightEnvelope(
        source_name=row.source_name, origin_adapter_name=row.source_name, metrics=(row,)
    )
    too_large = InsightCapture((envelope,) * 400, capture().outcomes)
    result = module(captured=too_large, previous=module())
    assert result.metrics == ()
    assert "invalid_value" in result.reasons


def test_failed_other_module_does_not_degrade_healthy_sibling():
    healthy = capture()
    macro = metric(module="macro", source_name="fred-api")
    failed = SourceInsightEnvelope(
        source_name="fred-api", origin_adapter_name="fred-api", metrics=(macro,)
    )
    mixed = InsightCapture(
        (*healthy.envelopes, failed),
        (
            *healthy.outcomes,
            SourceOutcome(
                source_name="fred-api",
                category="macro",
                status="failed",
                failure_reason="fixture",
                transient=False,
            ),
        ),
    )
    crypto = module(captured=mixed)
    assert crypto.availability == "available" and not crypto.reasons
    unavailable = project_module(
        "macro",
        mixed,
        (qualification(),),
        run_started_at=NOW,
        collection_completed_at=NOW,
        evaluated_at=NOW,
    )
    assert unavailable.availability == "unavailable"
    assert "source_failed" in unavailable.reasons
