"""Pure, source-neutral qualification, freshness, last-good and history gates."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast

from pydantic import ValidationError

from investo.models.insights import (
    MAX_INPUT_BYTES,
    Attempt,
    Freshness,
    HistoryDefinition,
    InsightHistory,
    InsightHistoryRow,
    InsightHistoryTime,
    InsightSourceQualification,
    ModuleId,
    Reason,
    SourceInsightEvent,
    SourceInsightMetric,
    ValidatedInsightEvent,
    ValidatedInsightMetric,
    ValidatedInsightModule,
    canonical_bytes,
    digest,
    public_href,
)
from investo.models.insights_calendar import NY, business_lag, expected_observation
from investo.models.insights_crypto import SAMPLE_POLICY, valid_crypto_metric
from investo.models.insights_macro import MACRO_BY_ID, SPREAD_RECIPES, valid_macro_metric
from investo.orchestrator.calendar_insights import project_calendar
from investo.orchestrator.crypto_insights import crypto_coverage, select_crypto_capture
from investo.orchestrator.insights import InsightCapture
from investo.orchestrator.macro_insights import bind_macro_capture

# Explicit producing/origin ownership contract; never infer by flattening.
_ALLOWED_FALLBACKS = frozenset({("okx-derivatives", "bybit-derivatives")})


def qualification_for(
    row: SourceInsightMetric | SourceInsightEvent,
    qualifications: Sequence[InsightSourceQualification],
) -> InsightSourceQualification | None:
    return next(
        (
            q
            for q in qualifications
            if q.source_name == row.source_name
            and q.endpoint == row.endpoint
            and q.field_scope == row.field_scope
            and row.definition_id in q.definition_ids
        ),
        None,
    )


def retention_allowed(
    row: SourceInsightMetric, qualifications: Sequence[InsightSourceQualification]
) -> bool:
    q = qualification_for(row, qualifications)
    if q is None or not q.retention_allowed:
        return False
    parents = next((pair[1:] for pair in SPREAD_RECIPES if pair[0] == row.metric_id), ())
    return row.module != "macro" or all(
        retention_allowed(MACRO_BY_ID[mid].metric(0, row.time), qualifications) for mid in parents
    )


def rights_reason(
    row: SourceInsightMetric | SourceInsightEvent,
    qualifications: Sequence[InsightSourceQualification],
) -> Reason | None:
    q = qualification_for(row, qualifications)
    if q is not None and q.revoked:
        return "rights_revoked"
    if q is None or not q.display_allowed or not q.public_git_history_allowed:
        return "rights_unverified"
    try:
        public_href(row.source_href)
        public_href(row.endpoint)
    except ValueError:
        return "rights_unverified"
    definition = next((d for d in q.definitions if d.definition_id == row.definition_id), None)
    if definition is None or definition.module != row.module:
        return "definition_conflict"
    if isinstance(row, SourceInsightMetric):
        if definition.public_id != row.metric_id or any(
            getattr(definition, name) != getattr(row, name)
            for name in (
                "unit",
                "provider",
                "scope_id",
                "methodology_id",
                "sample_policy",
                "cadence",
                "calendar_policy",
            )
        ):
            return "definition_conflict"
    elif definition.public_id != row.definition_id:
        return "definition_conflict"
    if row.source_href not in q.allowed_hrefs or row.endpoint not in q.allowed_hrefs:
        return "rights_unverified"
    if isinstance(row, SourceInsightMetric) and row.module == "macro":
        parents = next((pair[1:] for pair in SPREAD_RECIPES if pair[0] == row.metric_id), ())
        for mid in parents:
            denied = rights_reason(MACRO_BY_ID[mid].metric(0, row.time), qualifications)
            if denied:
                return denied
    if isinstance(row, ValidatedInsightEvent):
        for reference in row.references:
            denied = rights_reason(reference.event, qualifications)
            if denied:
                return denied
    return None


def freshness(row: SourceInsightMetric, now: datetime) -> Freshness:
    clock = row.time
    if any(
        at is not None and at > now
        for at in (clock.exact_at, clock.source_updated_at, clock.window_end)
    ):
        return "unknown"
    if row.cadence in {"daily", "monthly"} and now.astimezone(NY).year != 2026:
        return "unknown"
    if row.cadence == "snapshot":
        observed = clock.source_updated_at or (
            clock.window_end if clock.basis == "collection_window" else clock.exact_at
        )
        if observed is None or observed > now:
            return "unknown"
        return "fresh" if now - observed <= timedelta(hours=36) else "stale"
    if row.cadence == "monthly":
        if clock.precision not in {"month", "quarter"} or row.next_release_at is None:
            return "unknown"
        if now < row.next_release_at:
            return "fresh"
        lag = business_lag(
            row.next_release_at.astimezone(NY).date(), now.astimezone(NY).date(), "federal"
        )
        return (
            "unknown" if lag is None else "stale" if lag > 2 else "delayed" if lag > 1 else "fresh"
        )
    if row.cadence == "daily":
        expected = expected_observation(now, row.calendar_policy)
        if clock.local_date is None or expected is None or clock.local_date > expected:
            return "unknown"
        lag = business_lag(clock.local_date, expected, row.calendar_policy)
        return "unknown" if lag is None else "stale" if lag > 2 else "delayed" if lag else "fresh"
    return "unknown"


def _known_month(row: SourceInsightMetric, now: datetime) -> bool:
    """C4: known monthly actual, unknown next release; never claim freshness/history."""
    if (
        row.module != "macro"
        or row.cadence != "monthly"
        or row.next_release_at is not None
        or row.time.precision != "month"
        or row.time.basis != "period"
        or row.time.period is None
        or now.astimezone(NY).year != 2026
        or any(
            t is not None and t > now
            for t in (row.time.exact_at, row.time.source_updated_at, row.time.window_end)
        )
    ):
        return False
    try:
        period = date.fromisoformat(row.time.period + "-01")
    except ValueError:
        return False
    current = now.astimezone(NY).date().replace(day=1)
    return (
        period < current
        and 1 <= (current.year - period.year) * 12 + current.month - period.month <= 3
    )


def _public_metric(
    row: SourceInsightMetric,
    *,
    origin: str,
    attempt: Attempt,
    qualifications: Sequence[InsightSourceQualification],
    now: datetime,
    last_good: bool = False,
) -> ValidatedInsightMetric:
    q = qualification_for(row, qualifications)
    assert q is not None
    fresh = freshness(row, now)
    reasons: tuple[Reason, ...] = (
        ("stale",) if fresh == "stale" else ("time_unknown",) if fresh == "unknown" else ()
    )
    if attempt != "ok":
        reasons += (cast("Reason", "source_" + attempt),)
    payload = row.model_dump()
    # Revalidate rather than trust model_copy/update from adapters or baseline.
    payload.update(
        origin_adapter_name=origin,
        freshness=fresh,
        latest_attempt=attempt,
        attribution=q.attribution,
        last_good=last_good,
        availability="limited" if last_good or fresh in {"unknown", "stale"} else "available",
        reasons=reasons,
    )
    return ValidatedInsightMetric.model_validate(payload)


def project_module(
    module: ModuleId,
    capture: InsightCapture,
    qualifications: Sequence[InsightSourceQualification],
    *,
    run_started_at: datetime,
    collection_completed_at: datetime,
    evaluated_at: datetime,
    previous: ValidatedInsightModule | None = None,
    retain_previous_schedule: bool = False,
) -> ValidatedInsightModule:
    selected = capture
    conflicts: frozenset[tuple[str, str]] = frozenset()
    rejections: dict[str, set[Reason]] = {}
    if module == "crypto":
        selected, rejections, conflicts = select_crypto_capture(
            capture, now=evaluated_at, denied=lambda row: rights_reason(row, qualifications)
        )
    result = _project_numeric_module(
        module,
        selected,
        qualifications,
        run_started_at=run_started_at,
        collection_completed_at=collection_completed_at,
        evaluated_at=evaluated_at,
        previous=previous,
        retain_previous_schedule=retain_previous_schedule,
        crypto_conflicts=conflicts,
    )
    return (
        crypto_coverage(result, capture, qualifications, rejections)
        if module == "crypto"
        else result
    )


def _project_numeric_module(
    module: ModuleId,
    capture: InsightCapture,
    qualifications: Sequence[InsightSourceQualification],
    *,
    run_started_at: datetime,
    collection_completed_at: datetime,
    evaluated_at: datetime,
    previous: ValidatedInsightModule | None = None,
    retain_previous_schedule: bool = False,
    crypto_conflicts: frozenset[tuple[str, str]] = frozenset(),
) -> ValidatedInsightModule:
    if module == "calendar":
        return project_calendar(
            capture,
            qualifications,
            run_started_at=run_started_at,
            collection_completed_at=collection_completed_at,
            evaluated_at=evaluated_at,
            previous=previous,
            retain_previous_schedule=retain_previous_schedule,
            denied=lambda row: rights_reason(row, qualifications),
            qualification=lambda row: qualification_for(row, qualifications),
        )
    rejected_spreads: frozenset[str] = frozenset()
    if module == "macro":
        capture, rejected_spreads = bind_macro_capture(
            capture, allowed=lambda row: rights_reason(row, qualifications) is None
        )
    statuses = {outcome.source_name: outcome.status for outcome in capture.outcomes}
    reasons: set[Reason] = set()
    metrics: dict[str, ValidatedInsightMetric] = {}
    events: dict[str, ValidatedInsightEvent] = {}
    conflicts: set[str] = set()
    input_bytes = 0
    for envelope in capture.envelopes:
        observations: tuple[SourceInsightMetric | SourceInsightEvent, ...] = (
            *envelope.metrics,
            *envelope.events,
        )
        rows = tuple(row for row in observations if row.module == module)
        if not rows:
            continue
        input_bytes += (
            len(canonical_bytes({"rows": [row.model_dump(mode="json") for row in rows]}))
            if rows
            else 0
        )
        if input_bytes > MAX_INPUT_BYTES or len(metrics) > 32 or len(events) > 128:
            reasons.add("invalid_value")
            metrics.clear()
            events.clear()
            break
        origin = envelope.origin_adapter_name
        if origin is None or (
            envelope.source_name != origin
            and (envelope.source_name, origin) not in _ALLOWED_FALLBACKS
        ):
            reasons.add("definition_conflict")
            continue
        attempt = statuses.get(origin)
        if attempt != "ok":
            reasons.add(cast("Reason", "source_" + attempt) if attempt else "missing_input")
            continue
        for row in rows:
            rights = rights_reason(row, qualifications)
            if rights:
                reasons.add(rights)
                continue
            if row.time.precision == "unknown":
                reasons.add("time_unknown")
                continue
            q = qualification_for(row, qualifications)
            assert q is not None
            try:
                if isinstance(row, SourceInsightMetric):
                    if module == "crypto" and not valid_crypto_metric(row):
                        reasons.add("invalid_value")
                        continue
                    if module == "macro" and (
                        not valid_macro_metric(row) or row.metric_id in rejected_spreads
                    ):
                        reasons.add("invalid_value")
                        continue
                    fresh = freshness(row, evaluated_at)
                    if fresh == "stale" or (
                        fresh == "unknown" and not _known_month(row, evaluated_at)
                    ):
                        reasons.add("time_unknown" if fresh == "unknown" else "stale")
                        continue
                    value = _public_metric(
                        row,
                        origin=origin,
                        attempt="ok",
                        qualifications=qualifications,
                        now=evaluated_at,
                    )
                    key = row.metric_id
                    if key in metrics and metrics[key] != value:
                        conflicts.add(key)
                    metrics[key] = value
                else:
                    value_event = ValidatedInsightEvent(
                        **row.model_dump(),
                        origin_adapter_name=origin,
                        freshness="fresh"
                        if evaluated_at - collection_completed_at <= timedelta(hours=36)
                        else "stale",
                        latest_attempt="ok",
                        attribution=q.attribution,
                        collection_completed_at=collection_completed_at,
                    )
                    if row.event_id in events and events[row.event_id] != value_event:
                        conflicts.add(row.event_id)
                    events[row.event_id] = value_event
            except ValidationError:
                reasons.add("invalid_value")
    if len(metrics) > 32 or len(events) > 128:
        metrics.clear()
        events.clear()
        reasons.add("invalid_value")
    for key in conflicts:
        metrics.pop(key, None)
        events.pop(key, None)
    if conflicts:
        reasons.add("definition_conflict")
    if (
        previous is not None
        and previous.module == module
        and capture.outcomes
        and input_bytes <= MAX_INPUT_BYTES
    ):
        for old in previous.metrics:
            if module == "crypto" and (
                not valid_crypto_metric(old) or (old.metric_id, old.provider) in crypto_conflicts
            ):
                reasons.add("definition_conflict")
                continue
            if old.metric_id in metrics or old.metric_id in conflicts:
                continue
            denied = rights_reason(old, qualifications)
            if denied:
                reasons.add(denied)
                continue
            attempt = statuses.get(old.origin_adapter_name)
            if attempt is None:
                continue
            source = SourceInsightMetric.model_validate(
                {k: v for k, v in old.model_dump().items() if k in SourceInsightMetric.model_fields}
            )
            metrics[old.metric_id] = _public_metric(
                source,
                origin=old.origin_adapter_name,
                attempt=attempt,
                qualifications=qualifications,
                now=evaluated_at,
                last_good=True,
            )
        for old_event in previous.events:
            if old_event.event_id in events or old_event.event_id in conflicts:
                continue
            denied = rights_reason(old_event, qualifications)
            if denied:
                reasons.add(denied)
                continue
            attempt = statuses.get(old_event.origin_adapter_name)
            if attempt is None:
                continue
            event_fresh: Freshness = (
                "fresh"
                if evaluated_at - old_event.collection_completed_at <= timedelta(hours=36)
                else "stale"
            )
            events[old_event.event_id] = old_event.model_copy(
                update={"last_good": True, "latest_attempt": attempt, "freshness": event_fresh}
            )
    if not metrics and not events:
        reasons.add("missing_input")
    available = bool(metrics or events)
    limited = (
        bool(reasons)
        or any(m.availability == "limited" for m in metrics.values())
        or any(e.last_good or e.freshness != "fresh" for e in events.values())
    )
    try:
        return _build_module(
            module,
            run_started_at,
            collection_completed_at,
            evaluated_at,
            metrics,
            events,
            reasons,
            available,
            limited,
        )
    except ValidationError as exc:
        # The public cap is stricter than the private input cap: isolate this module.
        if any("cap exceeded" in str(error.get("msg", "")) for error in exc.errors()):
            return _build_module(
                module,
                run_started_at,
                collection_completed_at,
                evaluated_at,
                {},
                {},
                {"invalid_value"},
                False,
                False,
            )
        raise


def _build_module(
    module: ModuleId,
    run_started_at: datetime,
    collection_completed_at: datetime,
    evaluated_at: datetime,
    metrics: dict[str, ValidatedInsightMetric],
    events: dict[str, ValidatedInsightEvent],
    reasons: set[Reason],
    available: bool,
    limited: bool,
) -> ValidatedInsightModule:
    return ValidatedInsightModule(
        module=module,
        run_started_at=run_started_at,
        collection_completed_at=collection_completed_at,
        evaluated_at=evaluated_at,
        availability="limited"
        if available and limited
        else "available"
        if available
        else "unavailable",
        reasons=tuple(sorted(reasons)),
        metrics=tuple(metrics[k] for k in sorted(metrics)),
        events=tuple(events[k] for k in sorted(events)),
    )


def observation_key(
    row: SourceInsightMetric, *, collection_completed_at: datetime | None = None
) -> str | None:
    if row.module == "crypto" and row.sample_policy == SAMPLE_POLICY:
        return (
            collection_completed_at.astimezone(UTC).date().isoformat()
            if collection_completed_at
            else None
        )
    if row.module == "crypto":
        at = row.time.source_updated_at or row.time.window_end or row.time.exact_at
        return at.astimezone(UTC).date().isoformat() if at else None
    return str(row.time.local_date) if row.time.local_date else row.time.period


def update_history(
    module: ValidatedInsightModule,
    previous: InsightHistory | None,
    qualifications: Sequence[InsightSourceQualification],
) -> InsightHistory:
    if module.module == "calendar":
        raise ValueError("calendar does not have analytics history")
    current: dict[str, ValidatedInsightMetric] = {}
    for metric in module.metrics:
        q = qualification_for(metric, qualifications)
        if (
            q is not None
            and retention_allowed(metric, qualifications)
            and not rights_reason(metric, qualifications)
        ):
            current[metric.comparison_key()] = metric
    # Definition changes or rights withdrawal break old chains entirely.
    rows = (
        {
            (r.definition_key, r.observation_key): r
            for r in previous.rows
            if r.definition_key in current
        }
        if previous
        else {}
    )
    for key, metric in current.items():
        if metric.last_good or metric.freshness != "fresh":
            continue
        observed = observation_key(metric, collection_completed_at=module.collection_completed_at)
        if observed is None:
            continue
        record_hash = digest(
            canonical_bytes(
                {"value": str(metric.value), "time": metric.time.model_dump(mode="json")}
            )
        )
        old = rows.get((key, observed))
        replaced = bool(
            old
            and old.record_hash != record_hash
            and metric.module == "crypto"
            and metric.sample_policy == SAMPLE_POLICY
            and canonical_bytes(old.time) != canonical_bytes(metric.time)
        )
        rows[(key, observed)] = InsightHistoryRow(
            definition_key=key,
            observation_key=observed,
            value=metric.value,
            time=InsightHistoryTime.from_source(metric.time),
            record_hash=record_hash,
            revised_from=None
            if replaced
            else old.record_hash
            if old and old.record_hash != record_hash
            else old.revised_from
            if old
            else None,
            superseded_from=old.record_hash
            if replaced and old
            else old.superseded_from
            if old
            else None,
        )
    bounded = []
    for key, metric in current.items():
        selected = sorted(
            (r for r in rows.values() if r.definition_key == key), key=lambda r: r.observation_key
        )
        bounded.extend(selected[-(24 if metric.cadence == "monthly" else 366) :])
    definitions = tuple(
        HistoryDefinition(
            key=key,
            metric=SourceInsightMetric.model_validate(
                {
                    k: v
                    for k, v in metric.model_dump().items()
                    if k in SourceInsightMetric.model_fields
                }
            ),
            attribution=metric.attribution,
        )
        for key, metric in sorted(current.items())
        if any(r.definition_key == key for r in bounded)
    )
    return InsightHistory(module=module.module, definitions=definitions, rows=tuple(bounded))


def exact_change(
    metric: ValidatedInsightMetric, history: InsightHistory, *, baseline_observation_key: str
) -> Decimal | None:
    if metric.freshness != "fresh" or metric.last_good:
        return None
    key = metric.comparison_key()
    prior = next(
        (
            r
            for r in history.rows
            if r.definition_key == key and r.observation_key == baseline_observation_key
        ),
        None,
    )
    return metric.value - prior.value if prior else None
