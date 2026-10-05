"""Qualified collection composed with the canonical, recoverable public pair store."""

from __future__ import annotations

import math
import time
from datetime import date
from pathlib import Path
from typing import Literal

import httpx
from pydantic import Field

from investo.models.sector import SectorCoverageStatus
from investo.models.sector_public import (
    FreshnessState,
    PublicBuildIssueCode,
    PublicDiagnosticCode,
    PublicFailureCode,
    PublicSectorBuildOutcome,
    PublicSectorBuildStatus,
    PublicSourceIssueCode,
)
from investo.sector_dashboard.public_metrics import (
    build_public_series_bundle,
    compute_public_sector_snapshot,
)
from investo.sector_dashboard.public_render import (
    PublicProjectionError,
    render_public_sector_projection,
)
from investo.sector_dashboard.public_store import (
    PublicSectorStoreError,
    hold_public_sector_last_good,
    promote_public_sector_projection,
)
from investo.sector_dashboard.yahoo_data import YahooRequestBudget, collect_public_bars


class PublicBuildReport(PublicSectorBuildOutcome):
    """Bounded operational evidence; no raw bars, provider text or credentials."""

    mode: Literal["public_build"] = "public_build"
    source_id: Literal["yahoo-chart-daily-v2"] = "yahoo-chart-daily-v2"
    target_date: date
    candidate_freshness: FreshnessState = FreshnessState.UNKNOWN
    coverage: SectorCoverageStatus = SectorCoverageStatus.INSUFFICIENT
    available_sector_count: int = Field(default=0, ge=0, le=11)
    comparable_sector_count: int = Field(default=0, ge=0, le=11)
    request_count: int = Field(default=0, ge=0, le=36)
    successful_response_count: int = Field(default=0, ge=0, le=36)
    failed_request_count: int = Field(default=0, ge=0, le=36)
    source_issue_codes: tuple[PublicSourceIssueCode, ...] = ()
    collection_duration_ms: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    cpu_ms: int = Field(default=0, ge=0)

    @property
    def exit_code(self) -> int:
        return (
            0
            if self.status in {PublicSectorBuildStatus.PROMOTED, PublicSectorBuildStatus.UNCHANGED}
            and self.coverage is SectorCoverageStatus.NORMAL
            else 2
        )


def hold_failed_public_build(
    repository_root: Path, reasons: tuple[PublicFailureCode, ...]
) -> PublicSectorBuildOutcome:
    """Report a failed attempt against a verified prior pair, or block if none is usable."""
    try:
        return hold_public_sector_last_good(repository_root, failure_codes=reasons)
    except (PublicSectorStoreError, OSError):
        # A damaged or inaccessible prior pair cannot be reported as usable last-good.
        return PublicSectorBuildOutcome(
            status=PublicSectorBuildStatus.BLOCKED,
            failure_codes=(*reasons, PublicBuildIssueCode.STORE),
        )


async def build_public_sector(
    client: httpx.AsyncClient, *, repository_root: Path, target_date: date
) -> PublicBuildReport:
    """Promote only fresh normal/partial output, otherwise preserve last-good bytes."""
    started = time.monotonic()
    cpu_started = time.process_time()
    budget = YahooRequestBudget()
    collected_ms = 0
    freshness = FreshnessState.UNKNOWN
    coverage = SectorCoverageStatus.INSUFFICIENT
    available = comparable = 0
    source_issues: tuple[PublicSourceIssueCode, ...] = ()
    try:
        parsed = await collect_public_bars(client, target_date=target_date, budget=budget)
        collected_ms = math.ceil((time.monotonic() - started) * 1000)
        bundle = build_public_series_bundle(parsed, target_date=target_date)
        source_issues = tuple(sorted({failure.issue_code for failure in bundle.failures}, key=str))
        snapshot = compute_public_sector_snapshot(bundle)
        freshness, coverage = snapshot.freshness, snapshot.coverage.status
        available = snapshot.coverage.available_sector_count
        comparable = sum(record.relative_rank.score is not None for record in snapshot.records)
        reasons: set[PublicFailureCode] = set()
        if freshness is not FreshnessState.FRESH or snapshot.as_of_date != target_date:
            reasons.add(PublicSourceIssueCode.FRESHNESS)
        if coverage not in {SectorCoverageStatus.NORMAL, SectorCoverageStatus.PARTIAL}:
            reasons.add(PublicDiagnosticCode.INSUFFICIENT_HISTORY)
        projection = render_public_sector_projection(snapshot)
        if collected_ms > 120_000 or (time.process_time() - cpu_started) > 30:
            reasons.add(PublicBuildIssueCode.RESOURCE)
        if reasons:
            outcome = hold_failed_public_build(
                repository_root, tuple(sorted(reasons | set(source_issues), key=str))
            )
        else:
            outcome = promote_public_sector_projection(repository_root, projection)
    except Exception as exc:
        # Never stringify transport, validation, projection or filesystem exceptions.
        reason = (
            PublicBuildIssueCode.STORE
            if isinstance(exc, (PublicSectorStoreError, OSError))
            else PublicBuildIssueCode.PROJECTION
            if isinstance(exc, PublicProjectionError)
            else PublicBuildIssueCode.INTERNAL
        )
        outcome = hold_failed_public_build(repository_root, (*source_issues, reason))
    return PublicBuildReport(
        **outcome.model_dump(),
        target_date=target_date,
        candidate_freshness=freshness,
        coverage=coverage,
        available_sector_count=available,
        comparable_sector_count=comparable,
        request_count=budget.request_count,
        successful_response_count=budget.successful_response_count,
        failed_request_count=budget.request_count - budget.successful_response_count,
        source_issue_codes=source_issues,
        collection_duration_ms=collected_ms,
        duration_ms=math.ceil((time.monotonic() - started) * 1000),
        cpu_ms=math.ceil((time.process_time() - cpu_started) * 1000),
    )
