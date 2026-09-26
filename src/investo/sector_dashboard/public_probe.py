"""Read-only production-adapter qualification; no public store or publisher access."""

from __future__ import annotations

import math
import time
from collections.abc import Mapping
from datetime import date, datetime
from datetime import time as wall_time
from enum import StrEnum
from typing import Final, Literal, Self
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from investo.models.market_calendar import is_trading_day, previous_trading_day
from investo.models.sector import SectorCoverageStatus
from investo.models.sector_public import (
    FreshnessState,
    PublicSourceIssueCode,
)
from investo.sector_dashboard.hf_data import HFRequestBudget, collect_public_bars
from investo.sector_dashboard.public_metrics import (
    build_public_series_bundle,
    compute_public_sector_snapshot,
)
from investo.sector_dashboard.public_render import (
    PublicProjectionError,
    render_public_sector_projection,
)

# NYSE official 2026 cash-equity early closes, verified 2026-09-27:
# https://www.nyse.com/trade/hours-calendars (13:00 ET, Nov 27 and Dec 24).
_EARLY_CLOSES_2026: Final = frozenset({date(2026, 11, 27), date(2026, 12, 24)})


class ProbeIssueCode(StrEnum):
    COVERAGE = "probe.coverage"
    PROJECTION = "probe.projection"
    INTERNAL = "probe.internal"
    RESOURCE = "probe.resource"


class PublicProbeEvidence(BaseModel):
    """Closed aggregate evidence; raw bars, URLs and provider text have no fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    mode: Literal["production_adapter_probe"] = "production_adapter_probe"
    source_id: Literal["hf-data-library-iex-daily-v1"] = "hf-data-library-iex-daily-v1"
    status: Literal["qualified", "blocked"]
    target_date: date
    as_of_date: date | None = None
    freshness: FreshnessState = FreshnessState.UNKNOWN
    coverage: SectorCoverageStatus = SectorCoverageStatus.INSUFFICIENT
    requested_symbol_count: Literal[11] = 11
    successful_symbol_count: int = Field(default=0, ge=0, le=11)
    failed_symbol_count: int = Field(default=11, ge=0, le=11)
    available_sector_count: int = Field(default=0, ge=0, le=10)
    comparable_sector_count: int = Field(default=0, ge=0, le=10)
    request_count: int = Field(default=0, ge=0, le=66)
    successful_response_count: int = Field(default=0, ge=0, le=66)
    failed_request_count: int = Field(default=0, ge=0, le=66)
    duration_ms: int = Field(default=0, ge=0)
    collection_duration_ms: int = Field(default=0, ge=0)
    cpu_ms: int = Field(default=0, ge=0)
    snapshot_id: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    reason_codes: tuple[PublicSourceIssueCode | ProbeIssueCode, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.successful_symbol_count + self.failed_symbol_count != 11:
            raise ValueError("symbol counts must partition the fixed request set")
        if self.successful_response_count + self.failed_request_count != self.request_count:
            raise ValueError("request counts must partition attempts")
        if self.status == "qualified":
            if (
                self.reason_codes
                or self.freshness is not FreshnessState.FRESH
                or self.coverage not in {SectorCoverageStatus.NORMAL, SectorCoverageStatus.PARTIAL}
                or self.snapshot_id is None
                or self.as_of_date != self.target_date
                or self.successful_symbol_count != 11
                or self.available_sector_count != 10
                or self.comparable_sector_count != 10
                or self.successful_response_count < 22
                or self.collection_duration_ms > 120_000
                or self.cpu_ms > 30_000
            ):
                raise ValueError("qualification requires the complete fresh supported universe")
        elif not self.reason_codes:
            raise ValueError("blocked evidence requires closed reasons")
        return self


def resolve_probe_target_date(now: datetime) -> date:
    """Resolve the latest completed session with versioned NYSE close times.

    Regular closes are 16:00 ET; the two pinned early closes are 13:00 ET.
    Unknown calendar years fail before any request instead of guessing.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware timestamp required")
    local = now.astimezone(ZoneInfo("America/New_York"))
    if local.year != 2026:
        raise ValueError("calendar version unavailable")
    day = local.date()
    close_time = wall_time(13) if day in _EARLY_CLOSES_2026 else wall_time(16)
    if not is_trading_day("us-equity", day) or local.time() < close_time:
        day = previous_trading_day("us-equity", day)
    if day.year != 2026:
        raise ValueError("calendar version unavailable")
    return day


async def probe_public_sector(
    client: httpx.AsyncClient,
    *,
    environ: Mapping[str, str],
    target_date: date,
) -> PublicProbeEvidence:
    """Collect, calculate and verify in memory, returning only bounded evidence.

    A promotable partial (eight or nine sectors) is still a failed qualification
    run: five-run qualification requires all eleven supported symbols. No raw
    input or rendered pair is written to disk, logs, caches or artifacts.
    """
    started = time.monotonic()
    cpu_started = time.process_time()
    budget = HFRequestBudget()
    collected_ms = 0
    successful = 0
    try:
        parsed = await collect_public_bars(
            client, environ=environ, target_date=target_date, budget=budget
        )
        collected_ms = math.ceil((time.monotonic() - started) * 1000)
        successful = len(parsed.sectors) + int(parsed.benchmark is not None)
        bundle = build_public_series_bundle(parsed, target_date=target_date)
        snapshot = compute_public_sector_snapshot(bundle)
        reasons: set[PublicSourceIssueCode | ProbeIssueCode] = {
            failure.issue_code for failure in bundle.failures
        }
        if snapshot.freshness is not FreshnessState.FRESH:
            reasons.add(PublicSourceIssueCode.FRESHNESS)
        comparable = sum(record.relative_rank.score is not None for record in snapshot.records)
        if successful != 11 or comparable != 10:
            reasons.add(ProbeIssueCode.COVERAGE)
        projection = render_public_sector_projection(snapshot)
        cpu_ms = math.ceil((time.process_time() - cpu_started) * 1000)
        # asyncio.timeout cannot preempt a synchronous decoder. Measured
        # overruns must remain operationally red even if every task returned.
        if collected_ms > 120_000 or cpu_ms > 30_000:
            reasons.add(ProbeIssueCode.RESOURCE)
        return PublicProbeEvidence(
            status="blocked" if reasons else "qualified",
            target_date=target_date,
            as_of_date=snapshot.as_of_date,
            freshness=snapshot.freshness,
            coverage=snapshot.coverage.status,
            successful_symbol_count=successful,
            failed_symbol_count=11 - successful,
            available_sector_count=snapshot.coverage.available_sector_count,
            comparable_sector_count=comparable,
            request_count=budget.request_count,
            successful_response_count=budget.successful_response_count,
            failed_request_count=budget.request_count - budget.successful_response_count,
            collection_duration_ms=collected_ms,
            cpu_ms=cpu_ms,
            duration_ms=math.ceil((time.monotonic() - started) * 1000),
            snapshot_id=projection.snapshot_id,
            reason_codes=tuple(sorted(reasons, key=str)),
        )
    except Exception as exc:
        # Never stringify provider, parser, validation or injected transport errors.
        return PublicProbeEvidence(
            status="blocked",
            target_date=target_date,
            successful_symbol_count=successful,
            failed_symbol_count=11 - successful,
            request_count=budget.request_count,
            successful_response_count=budget.successful_response_count,
            failed_request_count=budget.request_count - budget.successful_response_count,
            collection_duration_ms=collected_ms,
            cpu_ms=math.ceil((time.process_time() - cpu_started) * 1000),
            duration_ms=math.ceil((time.monotonic() - started) * 1000),
            reason_codes=(
                ProbeIssueCode.PROJECTION
                if isinstance(exc, PublicProjectionError)
                else ProbeIssueCode.INTERNAL,
            ),
        )
