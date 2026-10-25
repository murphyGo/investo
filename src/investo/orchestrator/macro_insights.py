"""Bind reviewed numeric recipes without source parsing or additional I/O."""

from __future__ import annotations

from collections.abc import Callable
from decimal import DecimalException

from pydantic import ValidationError

from investo.models.insights import SourceInsightEnvelope, SourceInsightMetric
from investo.models.insights_macro import (
    MACRO_BY_ID,
    SPREAD_RECIPES,
    difference_exact,
    valid_macro_metric,
)
from investo.orchestrator.insights import InsightCapture


def bind_macro_capture(
    captured: InsightCapture, *, allowed: Callable[[SourceInsightMetric], bool]
) -> tuple[InsightCapture, frozenset[str]]:
    rows: dict[str, list[tuple[SourceInsightMetric, str | None]]] = {}
    count = 0
    for envelope in captured.envelopes:
        for row in envelope.metrics:
            if row.module != "macro":
                continue
            count += 1
            if count > 32:
                return captured, frozenset()  # The common cap rejects the module.
            rows.setdefault(row.metric_id, []).append((row, envelope.origin_adapter_name))
    added = []
    rejected = set()
    for spread_id, left_id, right_id in SPREAD_RECIPES:
        left, right = rows.get(left_id, []), rows.get(right_id, [])
        if len(left) != 1 or len(right) != 1:
            if spread_id in rows:
                rejected.add(spread_id)
            continue
        a, origin = left[0]
        b, other_origin = right[0]
        if (
            not valid_macro_metric(a)
            or not valid_macro_metric(b)
            or not allowed(a)
            or not allowed(b)
            or a.time != b.time
            or a.time.precision != "date"
            or a.unit != b.unit
            or a.unit != "percent"
            or a.source_name != b.source_name
            or a.provider != b.provider
            or origin != other_origin
        ):
            if spread_id in rows:
                rejected.add(spread_id)
            continue
        try:
            value = difference_exact(a.value, b.value, scale=100)
            metric = MACRO_BY_ID[spread_id].metric(value, a.time)
        except (DecimalException, ValidationError):
            rejected.add(spread_id)
            continue
        if spread_id in rows:
            if any(row.value != value or row.time != a.time for row, _ in rows[spread_id]):
                rejected.add(spread_id)
        else:
            added.append(
                SourceInsightEnvelope(
                    source_name=metric.source_name, origin_adapter_name=origin, metrics=(metric,)
                )
            )
    return InsightCapture((*captured.envelopes, *added), captured.outcomes), frozenset(rejected)
