"""u183 source-neutral snapshot selection. No HTTP, source parsers or market score."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import cast

from investo.models.insights import (
    MAX_INPUT_BYTES,
    CryptoModuleCoverage,
    CryptoSlotStatus,
    CryptoSourceStatus,
    InsightSourceQualification,
    Reason,
    SourceInsightEnvelope,
    SourceInsightMetric,
    ValidatedInsightModule,
    canonical_bytes,
)
from investo.models.insights_crypto import (
    CRYPTO_RECIPES,
    CRYPTO_SLOTS,
    CRYPTO_SOURCES,
    valid_crypto_metric,
)
from investo.orchestrator.insights import InsightCapture


def _stamp(row: SourceInsightMetric) -> datetime | None:
    return row.time.source_updated_at or row.time.window_end or row.time.exact_at


def select_crypto_capture(
    capture: InsightCapture,
    *,
    now: datetime,
    denied: Callable[[SourceInsightMetric], Reason | None],
) -> tuple[InsightCapture, dict[str, set[Reason]], frozenset[tuple[str, str]]]:
    reasons: dict[str, set[Reason]] = {mid: set() for mid in CRYPTO_SLOTS}
    statuses = {o.source_name: o.status for o in capture.outcomes}
    candidates: dict[tuple[str, str], list[tuple[SourceInsightMetric, str]]] = {}
    generic = []
    input_bytes = 0
    for bundle in capture.envelopes:
        rows = tuple(row for row in bundle.metrics if row.module == "crypto")
        input_bytes += (
            len(canonical_bytes({"rows": [r.model_dump(mode="json") for r in rows]})) if rows else 0
        )
        if input_bytes > MAX_INPUT_BYTES:
            return capture, {mid: {"invalid_value"} for mid in CRYPTO_SLOTS}, frozenset()
        untouched = tuple(
            r for r in bundle.metrics if r.module != "crypto" or r.metric_id not in CRYPTO_SLOTS
        )
        if untouched or bundle.events:
            generic.append(bundle.model_copy(update={"metrics": untouched}))
        for row in rows:
            if row.metric_id not in CRYPTO_SLOTS:
                continue
            errors = reasons[row.metric_id]
            origin = bundle.origin_adapter_name
            if (
                origin is None
                or (
                    bundle.source_name != origin
                    and (bundle.source_name, origin) != ("okx-derivatives", "bybit-derivatives")
                )
                or row.source_name != bundle.source_name
            ):
                errors.add("definition_conflict")
                continue
            attempt = statuses.get(origin)
            if attempt != "ok":
                errors.add(cast("Reason", "source_" + attempt) if attempt else "missing_input")
                continue
            rights = denied(row)
            if rights:
                errors.add(rights)
                continue
            if not valid_crypto_metric(row):
                errors.add("invalid_value")
                continue
            observed = _stamp(row)
            if observed is None or observed > now or row.time.precision == "unknown":
                errors.add("time_unknown")
                continue
            if now - observed > timedelta(hours=36):
                errors.add("stale")
                continue
            candidates.setdefault((row.metric_id, row.provider), []).append((row, origin))
    by_slot: dict[str, list[tuple[SourceInsightMetric, str]]] = {}
    conflicts = set()
    for (mid, provider), values in candidates.items():
        latest = max(stamp for row, _ in values if (stamp := _stamp(row)) is not None)
        current = [(row, origin) for row, origin in values if _stamp(row) == latest]
        # Origin is operational provenance, not a second market observation.
        unique = {canonical_bytes(row) for row, _ in current}
        if len(unique) != 1:
            conflicts.add((mid, provider))
            reasons[mid].add("definition_conflict")
            continue
        selected = min(current, key=lambda pair: (pair[1] != pair[0].source_name, pair[1]))
        by_slot.setdefault(mid, []).append(selected)
    chosen = []
    for values in by_slot.values():
        row, origin = min(
            values, key=lambda pair: (0 if pair[0].provider == "Bybit" else 1, pair[0].source_name)
        )
        chosen.append(
            SourceInsightEnvelope(
                source_name=row.source_name, origin_adapter_name=origin, metrics=(row,)
            )
        )
    return (
        InsightCapture(tuple((*generic, *chosen)), capture.outcomes),
        reasons,
        frozenset(conflicts),
    )


def crypto_coverage(
    module: ValidatedInsightModule,
    capture: InsightCapture,
    qualifications: Sequence[InsightSourceQualification],
    rejections: dict[str, set[Reason]],
) -> ValidatedInsightModule:
    if not any(
        d.module == "crypto" and d.definition_id.startswith("crypto.")
        for q in qualifications
        for d in q.definitions
    ):
        return module  # Preserve u180's generic resource/contract fixtures.
    statuses = {o.source_name: o.status for o in capture.outcomes}
    current = {r.metric_id: r for r in module.metrics}
    slots = []
    for mid in CRYPTO_SLOTS:
        row = current.get(mid)
        if row:
            slots.append(
                CryptoSlotStatus(
                    metric_id=mid,
                    availability=row.availability,
                    selected_source=row.source_name,
                    reasons=row.reasons,
                )
            )
            continue
        reasons = set(rejections[mid])
        recipes = [r for r in CRYPTO_RECIPES if r.metric_id == mid]
        source_names = {r.source_name for r in recipes}
        qs = [
            q
            for q in qualifications
            if q.source_name in source_names
            and any(d.module == "crypto" and d.public_id == mid for d in q.definitions)
        ]
        if not any(
            q.display_allowed and q.public_git_history_allowed and not q.revoked for q in qs
        ):
            reasons.add("rights_revoked" if any(q.revoked for q in qs) else "rights_unverified")
        for name in source_names:
            attempt = statuses.get(name)
            if attempt != "ok":
                reasons.add(cast("Reason", "source_" + attempt) if attempt else "missing_input")
        slots.append(
            CryptoSlotStatus(
                metric_id=mid,
                availability="unavailable",
                reasons=tuple(sorted(reasons or {"missing_input"})),
            )
        )
    sources = []
    for source in CRYPTO_SOURCES:
        qs = [
            q
            for q in qualifications
            if q.source_name == source and any(d.module == "crypto" for d in q.definitions)
        ]
        allowed = [q.display_allowed and q.public_git_history_allowed and not q.revoked for q in qs]
        rights = (
            "unverified"
            if not allowed
            else "allowed"
            if all(allowed)
            else "mixed"
            if any(allowed)
            else "blocked"
        )
        sources.append(
            CryptoSourceStatus.model_validate(
                dict(
                    source_name=source,
                    latest_attempt=statuses.get(source) or "missing",
                    rights=rights,
                )
            )
        )
    payload = module.model_dump()
    payload.update(
        snapshot_id="",
        crypto_coverage=CryptoModuleCoverage(slots=tuple(slots), sources=tuple(sources)),
    )
    if module.metrics and any(slot.availability != "available" for slot in slots):
        payload["availability"] = "limited"
    return ValidatedInsightModule.model_validate(payload)
