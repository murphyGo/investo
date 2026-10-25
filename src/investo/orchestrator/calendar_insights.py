"""u182 source-neutral occurrence validation, conservative joins and bounded selection."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Literal, cast

from pydantic import ValidationError

from investo.models.insights import (
    MAX_INPUT_BYTES,
    CalendarModuleCoverage,
    CalendarSourceStatus,
    InsightEventReference,
    InsightSourceQualification,
    Reason,
    SourceInsightEvent,
    SourceScheduleCoverage,
    ValidatedInsightEvent,
    ValidatedInsightModule,
    canonical_bytes,
)
from investo.models.insights_events import (
    CALENDAR_SOURCES,
    display_dates,
    in_range,
    local_dates,
    range_anchor,
    valid_event,
)
from investo.orchestrator.insights import InsightCapture


def project_calendar(
    capture: InsightCapture,
    qualifications: Sequence[InsightSourceQualification],
    *,
    run_started_at: datetime,
    collection_completed_at: datetime,
    evaluated_at: datetime,
    previous: ValidatedInsightModule | None,
    retain_previous_schedule: bool,
    denied: Callable[[SourceInsightEvent], Reason | None],
    qualification: Callable[[SourceInsightEvent], InsightSourceQualification | None],
) -> ValidatedInsightModule:
    statuses = {o.source_name: o.status for o in capture.outcomes}
    queries: dict[str, SourceScheduleCoverage] = {}
    reasons: set[Reason] = set()
    candidates: dict[tuple[str, str], InsightEventReference] = {}
    conflicts: set[tuple[str, str]] = set()
    input_bytes = invalid = 0

    def accept(reference: InsightEventReference) -> None:
        nonlocal invalid
        row = reference.event
        reason = denied(row)
        if reason:
            reasons.add(reason)
            return
        if (
            not valid_event(row)
            or row.time.basis != "schedule"
            or row.time.precision not in {"exact", "date"}
        ):
            invalid += 1
            reasons.add("invalid_value")
            return
        start, end = local_dates(row.time)
        if start is None or end is None or not timedelta(0) <= end - start <= timedelta(days=7):
            invalid += 1
            reasons.add("invalid_value")
            return
        if (
            row.time.source_updated_at is not None
            and row.time.source_updated_at > reference.collection_completed_at
        ):
            invalid += 1
            reasons.add("time_unknown")
            return
        key = (row.source_name, row.event_id)
        old = candidates.get(key)
        if old is not None and old.event != row:
            conflicts.add(key)
        else:
            candidates[key] = reference

    for envelope in capture.envelopes:
        if not envelope.events:
            continue
        input_bytes += len(canonical_bytes(envelope))
        if input_bytes > MAX_INPUT_BYTES:
            candidates.clear()
            reasons.add("invalid_value")
            invalid += 1
            break
        source = envelope.source_name
        if envelope.origin_adapter_name != source:
            reasons.add("definition_conflict")
            continue
        attempt = statuses.get(source)
        if attempt != "ok":
            reasons.add(cast("Reason", "source_" + attempt) if attempt else "missing_input")
            continue
        if envelope.schedule_coverage is not None:
            query = envelope.schedule_coverage
            old_query = queries.get(source)
            if old_query is None:
                queries[source] = query
            elif old_query != query:
                # Multiple release queries may reach different caps. Never claim full coverage.
                queries[source] = SourceScheduleCoverage(
                    start_date=max(old_query.start_date, query.start_date),
                    end_date=min(old_query.end_date, query.end_date),
                    upstream_cap=old_query.upstream_cap,
                    cap_reached=old_query.cap_reached or query.cap_reached,
                )
        for row in envelope.events:
            if row.source_name != source:
                reasons.add("definition_conflict")
                continue
            q = qualification(row)
            if q is None:
                reasons.add("rights_unverified")
                continue
            reason = denied(row)
            if reason:
                reasons.add(reason)
                continue
            accept(
                InsightEventReference(
                    event=row,
                    origin_adapter_name=source,
                    collection_completed_at=collection_completed_at,
                    latest_attempt="ok",
                    attribution=q.attribution,
                )
            )

    if previous is not None and previous.module == "calendar" and input_bytes <= MAX_INPUT_BYTES:
        for old in previous.events:
            primary = SourceInsightEvent.model_validate(
                {k: v for k, v in old.model_dump().items() if k in SourceInsightEvent.model_fields}
            )
            references = (
                InsightEventReference(
                    event=primary,
                    origin_adapter_name=old.origin_adapter_name,
                    collection_completed_at=old.collection_completed_at,
                    latest_attempt=old.latest_attempt,
                    last_good=old.last_good,
                    attribution=old.attribution,
                ),
                *old.references,
            )
            for ref in references:
                attempt = statuses.get(ref.origin_adapter_name)
                # A successful fresh snapshot replaces that source's old schedule.
                # Absence is not reported as cancellation or completed publication.
                if attempt not in {"zero", "failed", "skipped"} and not (
                    retain_previous_schedule and attempt == "ok"
                ):
                    continue
                q = qualification(ref.event)
                if q is None:
                    reasons.add("rights_unverified")
                    continue
                accept(
                    ref.model_copy(
                        update={
                            "latest_attempt": attempt,
                            "last_good": True,
                            "attribution": q.attribution,
                        }
                    )
                )

    for key in conflicts:
        candidates.pop(key, None)
    if conflicts:
        reasons.add("definition_conflict")
    if invalid:
        reasons.add("invalid_value")

    events = _merge_events(tuple(candidates.values()), evaluated_at)
    selected = sorted(
        (e for e in events if in_range(e, range_anchor(e, evaluated_at), 30)), key=_sort_key
    )
    excluded = max(0, len(selected) - 128)
    selected = selected[:128]
    sources = []
    for name in CALENDAR_SOURCES:
        source_attempt = statuses.get(name) or "missing"
        qs = [
            q
            for q in qualifications
            if q.source_name == name and any(d.module == "calendar" for d in q.definitions)
        ]
        allowed = [q.display_allowed and q.public_git_history_allowed and not q.revoked for q in qs]
        rights: Literal["allowed", "blocked", "mixed", "unverified"] = (
            "unverified"
            if not qs
            else "allowed"
            if all(allowed)
            else "mixed"
            if any(allowed)
            else "blocked"
        )
        sources.append(
            CalendarSourceStatus(
                source_name=name,
                latest_attempt=source_attempt,
                rights=rights,
                query=queries.get(name),
            )
        )
        if source_attempt != "ok":
            reasons.add(
                "missing_input"
                if source_attempt == "missing"
                else cast("Reason", "source_" + source_attempt)
            )
        if rights != "allowed":
            reasons.add("rights_unverified")
    if not selected:
        reasons.add("missing_input")
    coverage = CalendarModuleCoverage(
        sources=tuple(sources),
        selected_count=len(selected),
        excluded_count=excluded,
        conflict_count=len(conflicts),
        invalid_count=invalid,
    )
    limited = (
        bool(reasons)
        or bool(excluded)
        or any(e.last_good or e.freshness != "fresh" for e in selected)
    )
    payload = dict(
        module="calendar",
        run_started_at=run_started_at,
        collection_completed_at=collection_completed_at,
        evaluated_at=evaluated_at,
        availability="unavailable" if not selected else "limited" if limited else "available",
        reasons=tuple(sorted(reasons)),
        events=tuple(selected),
        calendar_coverage=coverage,
    )
    try:
        return ValidatedInsightModule.model_validate(payload)
    except ValidationError as exc:
        if not any("cap exceeded" in str(e.get("msg", "")) for e in exc.errors()):
            raise
        payload.update(
            events=(),
            availability="unavailable",
            reasons=("invalid_value",),
            calendar_coverage=coverage.model_copy(update={"selected_count": 0}),
        )
        return ValidatedInsightModule.model_validate(payload)


def _sort_key(row: ValidatedInsightEvent) -> tuple[str, str, str, str]:
    start, _ = display_dates(row)
    return str(start), row.details.kind if row.details else "", row.source_name, row.event_id


def _merge_events(
    references: tuple[InsightEventReference, ...], now: datetime
) -> list[ValidatedInsightEvent]:
    groups: dict[tuple[str, ...], list[InsightEventReference]] = {}
    for ref in references:
        row = ref.event
        details = row.details
        start, end = local_dates(row.time)
        # This reviewed family map permits only BEA <-> FRED schedule references.
        # Period-null and verified-period are different keys; no title/metadata inference.
        cross = (
            details is not None
            and details.family in {"us.gdp", "us.personal_income_outlays", "us.trade"}
            and row.source_name in {"us-economic-calendar", "fred-economic-calendar"}
        )
        key = (
            (details.kind, details.family, str(start), str(end), details.target_period or "")
            if cross and details
            else (row.source_name, row.event_id)
        )
        groups.setdefault(key, []).append(ref)
    result = []
    for group in groups.values():
        # More than one occurrence per source is ambiguous and stays separate.
        merge = len(group) == 2 and {r.event.source_name for r in group} == {
            "us-economic-calendar",
            "fred-economic-calendar",
        }
        choices = [group] if merge else [[ref] for ref in group]
        for choice in choices:
            ordered = sorted(
                choice,
                key=lambda r: (
                    r.event.time.precision != "exact",
                    r.last_good,
                    r.event.source_name,
                    r.event.event_id,
                ),
            )
            primary, *others = ordered
            result.append(
                ValidatedInsightEvent(
                    **primary.event.model_dump(),
                    origin_adapter_name=primary.origin_adapter_name,
                    collection_completed_at=primary.collection_completed_at,
                    latest_attempt=primary.latest_attempt,
                    attribution=primary.attribution,
                    last_good=primary.last_good,
                    freshness="fresh"
                    if now - primary.collection_completed_at <= timedelta(hours=36)
                    else "stale",
                    references=tuple(others),
                )
            )
    return result
