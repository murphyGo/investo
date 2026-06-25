"""Orchestrator pipeline — stage runners + ``run_pipeline`` composer.

This module is built up incrementally across plan Steps 5-9:

* **Step 5** — :func:`_stage_collect`: wraps u1 ``fetch_all``; raises
  :class:`EmptyCollectError` on a zero-item return so ``run_pipeline``
  can route the failure through AC-003-2.
* **Step 6** — :func:`_stage_generate`: wraps u2
  :func:`investo.briefing.pipeline.generate_briefing`. The plan
  speculated an ``asyncio.to_thread`` wrap (per TS-2), but
  ``generate_briefing`` is already async-native — its sync
  ``subprocess.run`` calls are already bridged via
  ``asyncio.to_thread`` inside ``call_claude_code``. We therefore
  ``await`` directly. ``BriefingGenerationError`` is re-raised
  (caller routes per AC-003-3).
* **Step 7** — :func:`_stage_publish`: wraps u3's sync
  ``write_briefing`` (atomic markdown write w/ verify-first NFR-004
  disclaimer block) + ``commit_and_push`` (3-attempt retry with
  idempotent-commit detection). Both are sync, so this stage uses
  ``asyncio.to_thread`` per TS-2 to keep the orchestrator's async
  surface uniform without blocking the event loop.
  ``PublisherDisclaimerError``, ``PublisherIOError``, and
  ``PublisherGitError`` are re-raised unchanged (caller routes per
  AC-003-4 + AC-003-5).
* **Step 8** — :func:`_stage_notify_briefing`: composes the public-
  channel preview via u4's ``build_summary``, wraps it in a
  :class:`BriefingNotification` payload, and dispatches via the
  caller-injected :class:`BriefingPublisher`. **Non-raising** — u4's
  ``send`` already encodes HTTP failures as ``SendResult(ok=False)``.
  The orchestrator returns the ``SendResult`` so ``run_pipeline`` can
  decide PARTIAL (publish ok + notify fail) vs SUCCESS per AC-003-6
  + AC-003-8.
* **Step 9** (this commit) — :func:`run_pipeline`: Q9=B Error
  Policy router. Composes the four stage runners under a single
  wall-clock measurement. Records per-stage `stage_timings` (AC-001-1)
  + free-form `stages` diagnostic dict (existing
  :class:`PipelineResult` field). On any of the catalogued failures
  it routes to ``OperatorAlerter.alert(...)`` with the appropriate
  ``FailureContext`` and returns ``status=FAILED``. Notify failure
  alone → ``status=PARTIAL`` with NO operator alert (the PARTIAL
  status is the visibility signal per AC-003-6). Programmer errors
  propagate to ``main()`` per AC-003-7. **No** stage-level
  ``asyncio.wait_for`` (Q1=A — trust unit-level timeouts; AC-001-3),
  **no** ``asyncio.gather`` overlapping stages (Q5 — sequential;
  AC-001-5), **no** orchestrator-level retry around stage calls
  (Q4=A; AC-003-11). Operator-alert delivery itself gets a narrow
  retry in ``_safe_alert`` per product-level FR-007.

Each stage runner takes its callable dependency as a keyword-only
parameter so unit tests can inject a fake without monkeypatching
``investo.sources`` etc. The defaults wire to the real units;
``run_pipeline`` (Step 9) propagates injected callables through.

Logging follows AC-005-5: each stage entry emits an INFO line; per-
source degradation surfaces as a WARNING from the underlying unit
(u1 already logs at WARNING — we don't double-log here).

Reference:
    aidlc-docs/construction/u5-orchestrator/nfr-requirements/
    aidlc-docs/construction/plans/u5-orchestrator-code-generation-plan.md
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import json
import logging
import os
import re
import time
import traceback
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, cast

from pydantic import HttpUrl, TypeAdapter, ValidationError

from investo._internal.archive_layout import ArchiveLayout
from investo.briefing.claude_code import ClaudeRunner
from investo.briefing.context import (
    RecentBriefingsContext,
)
from investo.briefing.disclaimer import ensure_canonical_disclaimer
from investo.briefing.errors import BriefingGenerationError
from investo.briefing.fact_context import (
    VerifiedFactConflictError,
    append_fact_snapshot_jsonl,
    build_verified_fact_bundle,
    render_fact_context_block,
)
from investo.briefing.forecast_log import (
    ForecastLogError,
    append_forecast_entries,
    resolve_forecast_log_path,
)
from investo.briefing.lineage import MacroLineageTrace
from investo.briefing.macro_carryover import (
    MacroCarryoverError,
    advance_macro_lifecycle,
    load_macro_lifecycle_events,
    upsert_macro_lifecycle_snapshot,
)
from investo.briefing.market_anchor import (
    MarketAnchor,
    OHLCRow,
)
from investo.briefing.monthly_retrospective import (
    month_has_archive_days,
    render_monthly_retrospective,
)
from investo.briefing.numeric_self_check import extract_flaggable_numbers
from investo.briefing.numeric_verify import verify_core_facts
from investo.briefing.pipeline import GenerationInput, GenerationPolicy, GenerationResult
from investo.briefing.pipeline import generate_briefing as _u2_generate_briefing
from investo.briefing.pipeline import generate_briefing_from_input as _u2_generate_from_input
from investo.briefing.quality_history import (
    QualityHistoryError,
    QualitySnapshot,
    append_quality_snapshot,
    resolve_quality_history_path,
)
from investo.briefing.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    SEGMENT_LABELS,
    US_EQUITY,
    MarketSegment,
    SegmentCoverage,
    SegmentedItems,
    filter_lookahead_items,
    segment_items,
    segment_source_outcomes,
)
from investo.briefing.summary_quality import (
    SummaryQualityError,
    repair_first_viewport_summary,
)
from investo.briefing.watchlist import WatchlistConfig, load_watchlist, match_watchlist_items
from investo.models import (
    Briefing,
    BriefingCarryover,
    BriefingNotification,
    FailureContext,
    NormalizedItem,
    PipelineResult,
    PipelineStatus,
    SendResult,
    SourceOutcome,
)
from investo.models.bundle_context import BundleContext
from investo.models.facts import FactId, VerifiedFactBundle
from investo.models.results import TRACEBACK_EXCERPT_MAX
from investo.notifier import (
    BriefingPublisher,
    OperatorAlerter,
    build_segmented_summary,
    build_summary,
)
from investo.notifier.summary import resolve_enabled_segments
from investo.orchestrator import source_health
from investo.orchestrator.bundle_context import (
    compute_bundle_context,
    redecide_daily_thesis_for_successful_segments,
)
from investo.orchestrator.date_resolution import resolve_target_date, validate_target_date_sanity
from investo.orchestrator.domestic_anchor_quarantine import (
    domestic_anchor_verdicts,
    trusted_domestic_price_items,
)
from investo.orchestrator.errors import EmptyCollectError
from investo.orchestrator.stage_context import (
    SEGMENT_ORDER,
    _build_kr_anchors_from_items,
    _load_carryover_for_run,
    _load_market_anchors_for_run,
    _load_recent_context_for_run,
    _snapshot_close_by_ticker,
)
from investo.orchestrator.stages import (
    PipelineContext,
    Stage,
    StageAction,
    StageResult,
)
from investo.orchestrator.validators import build_publish_boundary_registry
from investo.publisher import (
    GitRunner,
    PublisherDisclaimerError,
    PublisherGitError,
    PublisherIOError,
    SurfaceQualityError,
    commit_and_push,
    publish_weekly_digest,
    update_weekly_index,
    weekly_digest_opt_in,
    write_briefing,
)
from investo.publisher import (
    archive_path as compute_archive_path,
)
from investo.publisher import site_index as _site_index_mod
from investo.publisher.anchor_assertion_gate import (
    NumericAnchorReconciliationError,
)
from investo.publisher.carryover import inject_carryover_block, render_carryover_block
from investo.publisher.chart_sidecar import write_chart_sidecar
from investo.publisher.charts import build_chart_artifacts, inject_chart_block
from investo.publisher.compliance_language import (
    ComplianceLanguageError,
)
from investo.publisher.entity_fact_guard import scan_entity_fact_claims
from investo.publisher.evidence_accounting import count_rendered_evidence, render_body_used_count
from investo.publisher.monthly_index import update_monthly_index
from investo.publisher.reader_format import (
    emit_first_viewport_disclaimer,
)
from investo.publisher.segment_reader_format import (
    apply_reader_format_to_segments as _apply_reader_format_to_segments,
)
from investo.publisher.site_index import (
    ACCURACY_PAGE_PATH,
    ARCHIVE_INDEX_PATH,
    SEGMENT_ARCHIVE_INDEX_PATHS,
    SITE_INDEX_PATH,
    update_accuracy_page,
    update_latest_index_pages,
    update_quality_page,
)
from investo.publisher.weekly_digest import (
    WEEKLY_INDEX_PATH,
)
from investo.publisher.weekly_digest import (
    weekly_path as compute_weekly_path,
)
from investo.sources import collect_sources as _default_collect_sources
from investo.visuals.assets import VisualAssetError, prepare_segment_visual_assets
from investo.visuals.calendar_heatmap import render_publish_heatmap, scan_publish_coverage
from investo.visuals.og_card import (
    OG_CARD_PNG_RELATIVE_PATH,
    OG_CARD_RELATIVE_PATH,
    write_og_card,
)
from investo.visuals.provenance import manifest_path_for

# Single ``HttpUrl`` adapter — pydantic v2 doesn't expose ``HttpUrl``
# as directly callable; the TypeAdapter avoids constructing a fresh
# adapter per pipeline run.
_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)

_logger = logging.getLogger("investo.orchestrator.pipeline")

# u31 Step 2 — operator-rehearsal env flag. ``INVESTO_DRY_RUN=1``
# short-circuits git push (write archive files locally, leave the
# working tree dirty) and Telegram dispatch (return ``ok=True`` without
# I/O). Read at each publish-stage entry so a caller flipping the env
# mid-run is honoured by the next stage.
_DRY_RUN_ENV: Final[str] = "INVESTO_DRY_RUN"
_SEGMENT_GENERATION_CONCURRENCY_ENV: Final[str] = "INVESTO_SEGMENT_GENERATION_CONCURRENCY"
_VISUAL_PREP_CONCURRENCY_ENV: Final[str] = "INVESTO_VISUAL_PREP_CONCURRENCY"
_SEGMENT_NAV_LINE_RE: Final[re.Pattern[str]] = re.compile(r"^\*\*세그먼트\*\*: .*$", re.MULTILINE)


def _is_dry_run() -> bool:
    return os.environ.get(_DRY_RUN_ENV, "").strip() == "1"


def _segment_generation_concurrency_from_env() -> int:
    raw = os.environ.get(_SEGMENT_GENERATION_CONCURRENCY_ENV)
    if raw is None:
        return 1
    raw = raw.strip()
    try:
        value = int(raw)
    except ValueError:
        _logger.warning(
            "[generate] invalid %s=%r; falling back to 1",
            _SEGMENT_GENERATION_CONCURRENCY_ENV,
            raw,
        )
        return 1
    if value in {1, 2, 3}:
        return value
    _logger.warning(
        "[generate] invalid %s=%r; expected 1, 2, or 3; falling back to 1",
        _SEGMENT_GENERATION_CONCURRENCY_ENV,
        raw,
    )
    return 1


def _visual_prep_concurrency_from_env() -> int:
    raw = os.environ.get(_VISUAL_PREP_CONCURRENCY_ENV)
    if raw is None:
        return 1
    raw = raw.strip()
    try:
        value = int(raw)
    except ValueError:
        _logger.warning(
            "[visual_assets] invalid %s=%r; falling back to 1",
            _VISUAL_PREP_CONCURRENCY_ENV,
            raw,
        )
        return 1
    if value in {1, 2, 3}:
        return value
    _logger.warning(
        "[visual_assets] invalid %s=%r; expected 1, 2, or 3; falling back to 1",
        _VISUAL_PREP_CONCURRENCY_ENV,
        raw,
    )
    return 1


_ALERT_DELIVERY_ATTEMPTS = 2


class NotifyDeliveryError(RuntimeError):
    """Public briefing notification failed after publish succeeded."""


# Type alias for the callable shape of u1's ``fetch_all``. Captures the
# surface ``run_pipeline`` and ``_stage_collect`` depend on without
# importing a class — u1's aggregator is module-level (not a class)
# per ``aidlc-docs/inception/application-design/component-methods.md``.
CollectCallable = Callable[[date], Awaitable[list[NormalizedItem]]]

# Callable shape used by ``_stage_generate`` for its ``generate=`` test
# seam. Positional 3-arg form ``(target_date, items, runner)`` so tests
# can inject a fake without juggling u2's keyword-only ``runner=`` /
# ``budget=`` parameters. The production binding
# (``_default_generate_briefing`` below) is a thin adapter that bridges
# this positional shape to u2's actual ``generate_briefing(...,
# runner=runner)`` keyword call.
GenerateCallable = Callable[
    [date, Sequence[NormalizedItem], ClaudeRunner | None],
    Awaitable[Briefing],
]
SegmentGenerateCallable = Callable[
    [
        date,
        Sequence[NormalizedItem],
        ClaudeRunner | None,
        MarketSegment,
        bool,
        Sequence[SourceOutcome],
        RecentBriefingsContext | None,
        Sequence[MarketAnchor],
        BriefingCarryover | None,
        BundleContext | None,
    ],
    Awaitable[Briefing],
]
SEGMENT_GENERATION_POLICIES: dict[MarketSegment, GenerationPolicy] = {
    # 2026-05-21 GHA postmortem — crypto Stage 2 exhausted the 15-minute
    # per-call synthesis ceiling on otherwise publishable runs. The workflow
    # job timeout is now 240 minutes, so each segment gets a 30-minute
    # per-call ceiling. 2026-06-13 postmortem — crypto twice returned
    # mid-section markdown without the required first header, so crypto keeps
    # the default third attempt while the two equity segments stay capped at
    # two attempts. Worst-case synthesis across all segments still fits the
    # cron budget with runner overhead.
    DOMESTIC_EQUITY: GenerationPolicy(timeout_s=1800.0, max_attempts=2, total_budget_s=3900.0),
    US_EQUITY: GenerationPolicy(timeout_s=1800.0, max_attempts=2, total_budget_s=3900.0),
    CRYPTO: GenerationPolicy(timeout_s=1800.0, max_attempts=3, total_budget_s=5700.0),
}


@dataclass(frozen=True, slots=True)
class _SegmentGenerationResult:
    segment: MarketSegment
    briefing: Briefing | None
    failure: BriefingGenerationError | None
    macro_lineage: tuple[MacroLineageTrace, ...]
    elapsed_s: float


@dataclass(frozen=True, slots=True)
class _VisualPrepResult:
    segment: MarketSegment
    briefing: Briefing
    asset_paths: tuple[Path, ...]


async def _default_generate_briefing(
    target_date: date,
    items: Sequence[NormalizedItem],
    runner: ClaudeRunner | None,
) -> Briefing:
    """Adapter — bridges :data:`GenerateCallable` to u2's keyword-only API.

    Lives here (vs as a ``functools.partial``) so its signature is
    obvious to type-checkers and to anyone reading the module: u2's
    ``runner`` is keyword-only, but the ``GenerateCallable`` Protocol
    used at the orchestrator boundary is positional for test
    convenience. ``budget`` is intentionally NOT exposed —
    orchestrator does not control u2's retry budget per Q4=A; u2's
    default ``RetryBudget()`` is the right one.
    """
    return await _u2_generate_briefing(
        target_date,
        items,
        runner=runner,
        watchlist_config=load_watchlist(),
    )


async def _default_generate_segment_briefing(
    target_date: date,
    items: Sequence[NormalizedItem],
    runner: ClaudeRunner | None,
    segment: MarketSegment,
    data_limited: bool,
    source_outcomes: Sequence[SourceOutcome],
    recent_context: RecentBriefingsContext | None,
    market_anchors: Sequence[MarketAnchor],
    carryover: BriefingCarryover | None,
    bundle_context: BundleContext | None,
    fact_context_block: str = "",
    *,
    macro_lineage_all_items: Sequence[NormalizedItem] | None = None,
    watchlist_config: WatchlistConfig | None = None,
) -> GenerationResult:
    """Adapter for u7 segmented generation."""
    # u68 — pass the archive root so the glossary callout can suppress
    # terms already glossed in this segment's recent archives. Deferred
    # import + call-time read keeps the ``monkeypatch.setattr(paths,
    # "ARCHIVE_ROOT", tmp)`` test seam working (same pattern as the u52
    # carryover loader below).
    from investo.publisher.paths import ARCHIVE_ROOT

    watchlist = load_watchlist() if watchlist_config is None else watchlist_config
    return await _u2_generate_from_input(
        GenerationInput(
            target_date=target_date,
            items=items,
            watchlist_config=watchlist,
            runner=runner,
            segment=segment,
            data_limited=data_limited,
            source_outcomes=source_outcomes,
            recent_context=recent_context,
            carryover=carryover,
            market_anchors=market_anchors,
            generation_policy=SEGMENT_GENERATION_POLICIES[segment],
            bundle_context=bundle_context,
            fact_context_block=fact_context_block,
            archive_root=ARCHIVE_ROOT,
            macro_lineage_all_items=macro_lineage_all_items,
        )
    )


async def _stage_collect(
    target_date: date,
    *,
    fetch: CollectCallable | None = None,
) -> tuple[list[NormalizedItem], tuple[SourceOutcome, ...]]:
    """Run u1's source aggregator and gate on a non-empty result.

    Parameters
    ----------
    target_date:
        Resolved by :func:`investo.orchestrator.date_resolution
        .resolve_target_date`. Passed through to the aggregator.
    fetch:
        Override hook for tests. When ``None`` (production), wires to
        :func:`investo.sources.collect_sources` so the pipeline gets
        per-adapter outcomes for u22 source-coverage transparency.
        Tests may inject either:

        * an items-only callable (legacy ``fetch_all`` shape) — outcomes
          will be empty for that run, which is the correct backward-
          compatible behavior;
        * a ``collect_sources`` shape callable (returning a
          :class:`investo.models.SourceCollectionReport`).

    Returns
    -------
    tuple[list[NormalizedItem], tuple[SourceOutcome, ...]]
        Non-empty union of items, plus one outcome per registered
        adapter (or ``()`` when the test seam returns items only).
        Per-source failures inside the aggregator are already swallowed
        with a WARNING — see ``aggregator.collect_sources`` docstring.

    Raises
    ------
    EmptyCollectError
        Every source returned zero items (or no adapters are
        registered). ``run_pipeline`` catches this and routes to
        ``OperatorAlerter.alert(stage="collect")`` per AC-003-2.
    """
    _logger.info("[collect] starting target_date=%s", target_date)
    if fetch is not None:
        items = await fetch(target_date)
        outcomes: tuple[SourceOutcome, ...] = ()
    else:
        report = await _default_collect_sources(target_date)
        items = list(report.items)
        outcomes = report.outcomes
    _logger.info("[collect] returned %d items outcomes=%d", len(items), len(outcomes))

    if not items:
        # Empty result is a hard failure — the briefing has nothing
        # to summarize. The error_message is intentionally terse;
        # ``run_pipeline`` formats the operator-alert text including
        # ``target_date`` at the catch site.
        raise EmptyCollectError(f"aggregator returned 0 items for target_date={target_date}")

    return items, outcomes


async def _stage_generate(
    target_date: date,
    items: Sequence[NormalizedItem],
    *,
    runner: ClaudeRunner | None = None,
    generate: GenerateCallable | None = None,
) -> Briefing:
    """Run u2's two-stage briefing generation.

    Parameters
    ----------
    target_date:
        Forwarded to :func:`investo.briefing.pipeline.generate_briefing`.
    items:
        Non-empty source items from :func:`_stage_collect`.
    runner:
        ``ClaudeRunner`` test seam forwarded to u2. Production passes
        ``None``; u2's ``call_claude_code`` then uses its real
        subprocess runner.
    generate:
        Override hook for tests that want to bypass u2's pipeline
        entirely (e.g., produce a fixed ``Briefing`` without invoking
        any LLM machinery). When ``None`` (production), wires to
        :func:`investo.briefing.pipeline.generate_briefing`. When set,
        the ``runner`` parameter is still forwarded so tests that fake
        only at the runner level work too.

    Returns
    -------
    Briefing
        Fully-validated briefing with disclaimer appended.

    Raises
    ------
    BriefingGenerationError
        Re-raised from u2 on LLM-traceable failure
        (``stage="classification" | "synthesis" | "post_validation"
        | "budget"``). ``run_pipeline`` catches and routes per
        AC-003-3. Programmer errors (KeyError, ValidationError, etc.)
        propagate unchanged.
    """
    runner_callable = generate if generate is not None else _default_generate_briefing

    _logger.info("[generate] starting target_date=%s items=%d", target_date, len(items))
    briefing = await runner_callable(target_date, items, runner)
    _logger.info("[generate] briefing built target_date=%s", target_date)
    return briefing


async def _generate_one_segment(
    *,
    target_date: date,
    all_items: Sequence[NormalizedItem],
    segment: MarketSegment,
    segment_source_items: Sequence[NormalizedItem],
    data_limited: bool,
    segment_outcomes: Sequence[SourceOutcome],
    runner: ClaudeRunner | None,
    runner_callable: SegmentGenerateCallable | None,
    use_default_generator: bool,
    recent_context: RecentBriefingsContext | None,
    segment_anchors: Sequence[MarketAnchor],
    segment_carryover: BriefingCarryover | None,
    bundle_context: BundleContext | None,
    fact_context_block: str,
    watchlist_config: WatchlistConfig | None,
) -> _SegmentGenerationResult:
    start = time.monotonic()
    _logger.info(
        "[generate] segment=%s items=%d data_limited=%s outcomes=%d",
        segment,
        len(segment_source_items),
        data_limited,
        len(segment_outcomes),
    )
    try:
        if use_default_generator:
            generation_result = await _default_generate_segment_briefing(
                target_date,
                segment_source_items,
                runner,
                segment,
                data_limited,
                segment_outcomes,
                recent_context,
                segment_anchors,
                segment_carryover,
                bundle_context,
                fact_context_block,
                macro_lineage_all_items=all_items,
                watchlist_config=watchlist_config,
            )
            briefing = generation_result.briefing
            macro_lineage = generation_result.macro_lineage
        else:
            assert runner_callable is not None
            briefing = await runner_callable(
                target_date,
                segment_source_items,
                runner,
                segment,
                data_limited,
                segment_outcomes,
                recent_context,
                segment_anchors,
                segment_carryover,
                bundle_context,
            )
            macro_lineage = ()
    except BriefingGenerationError as exc:
        _logger.warning(
            "[generate] segment failed segment=%s stage=%s attempts=%s; continuing",
            segment,
            exc.stage,
            exc.attempt_count,
        )
        return _SegmentGenerationResult(
            segment=segment,
            briefing=None,
            failure=exc,
            macro_lineage=(),
            elapsed_s=time.monotonic() - start,
        )
    return _SegmentGenerationResult(
        segment=segment,
        briefing=briefing,
        failure=None,
        macro_lineage=macro_lineage,
        elapsed_s=time.monotonic() - start,
    )


async def _stage_generate_segments(
    target_date: date,
    items: Sequence[NormalizedItem],
    *,
    runner: ClaudeRunner | None = None,
    generate_segment: SegmentGenerateCallable | None = None,
    source_outcomes: Sequence[SourceOutcome] = (),
    recent_context: RecentBriefingsContext | None = None,
    market_anchors_by_segment: Mapping[MarketSegment, Sequence[MarketAnchor]] | None = None,
    carryover_by_segment: Mapping[MarketSegment, BriefingCarryover] | None = None,
) -> tuple[
    dict[MarketSegment, Briefing],
    dict[MarketSegment, BriefingGenerationError],
    BundleContext | None,
    VerifiedFactBundle,
    dict[MarketSegment, tuple[MacroLineageTrace, ...]],
    dict[str, float],
]:
    """Generate all u7 market segments in fixed order.

    Segment-level :class:`BriefingGenerationError` is isolated to that
    segment. At least one successful segment is enough to continue to
    publish; an all-segment failure is re-raised so the pipeline can
    fail normally.

    ``source_outcomes`` (u22) is forwarded so each segment briefing can
    annotate its coverage badge with reason codes / per-source verdicts.
    Default ``()`` keeps legacy injected-fake call sites working.

    ``recent_context`` (u34) is the trailing-N-day archive context;
    threaded into each segment's Stage 2 prompt so the LLM can reflect
    continuity / divergence vs the recent publish history. ``None``
    disables the feature (matches the env-var ``=0`` setting and the
    pre-u34 behaviour).
    """
    routed = segment_items(items)
    watchlist_config = load_watchlist() if generate_segment is None else None
    briefings: dict[MarketSegment, Briefing] = {}
    failures: dict[MarketSegment, BriefingGenerationError] = {}
    macro_lineage_by_segment: dict[MarketSegment, tuple[MacroLineageTrace, ...]] = {}
    segment_timings: dict[str, float] = {}

    # u57 — compute BundleContext once per run (pre-Stage-2), shared by
    # all three segments. ``now_kst`` is derived from the target_date so
    # replay tests stay deterministic. The orchestrator's ``run_pipeline``
    # already uses the same convention for target_date resolution.
    routed_by_segment: dict[MarketSegment, Sequence[NormalizedItem]] = {
        seg: routed.for_segment(seg) for seg in SEGMENT_ORDER
    }
    bundle_context: BundleContext | None
    bundle_start = time.monotonic()
    try:
        bundle_context = compute_bundle_context(
            routed_by_segment,
            now_kst=datetime.combine(target_date, datetime.min.time(), tzinfo=UTC),
        )
    except Exception as exc:
        _logger.warning("[generate] bundle_context build failed err=%s; proceeding without", exc)
        bundle_context = None
    finally:
        segment_timings["generate:bundle_context"] = time.monotonic() - bundle_start

    fact_start = time.monotonic()
    fact_now_utc = datetime.now(UTC)
    try:
        fact_bundle = build_verified_fact_bundle(tuple(items), target_date, fact_now_utc)
        fact_context_block = render_fact_context_block(fact_bundle, fact_now_utc)
        if generate_segment is None:
            _persist_fact_snapshot_safely(
                target_date,
                fact_bundle=fact_bundle,
                observed_at=fact_now_utc,
            )
    except VerifiedFactConflictError as exc:
        fact_bundle = VerifiedFactBundle(target_date=target_date)
        fact_context_block = render_fact_context_block(fact_bundle, fact_now_utc)
        if generate_segment is None:
            _persist_fact_snapshot_safely(
                target_date,
                fact_bundle=fact_bundle,
                observed_at=fact_now_utc,
                conflict_fact_ids=(exc.fact_id,),
            )
        _logger.warning(
            "[facts] conflict fact_id=%s values=%s; proceeding unverified",
            exc.fact_id,
            exc.values,
        )
    finally:
        segment_timings["generate:fact_context"] = time.monotonic() - fact_start

    _logger.info("[generate] starting segmented target_date=%s items=%d", target_date, len(items))
    concurrency = _segment_generation_concurrency_from_env()
    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded_generate(segment: MarketSegment) -> _SegmentGenerationResult:
        segment_source_items = routed.for_segment(segment)
        data_limited = routed.is_data_limited(segment)
        segment_outcomes = segment_source_outcomes(segment, source_outcomes)
        segment_anchors: tuple[MarketAnchor, ...] = ()
        if market_anchors_by_segment is not None:
            segment_anchors = tuple(market_anchors_by_segment.get(segment, ()))
        segment_carryover = (
            carryover_by_segment.get(segment) if carryover_by_segment is not None else None
        )
        async with semaphore:
            return await _generate_one_segment(
                target_date=target_date,
                all_items=items,
                segment=segment,
                segment_source_items=segment_source_items,
                data_limited=data_limited,
                segment_outcomes=segment_outcomes,
                runner=runner,
                runner_callable=generate_segment,
                use_default_generator=generate_segment is None,
                recent_context=recent_context,
                segment_anchors=segment_anchors,
                segment_carryover=segment_carryover,
                bundle_context=bundle_context,
                fact_context_block=fact_context_block,
                watchlist_config=watchlist_config,
            )

    raw_results = await asyncio.gather(
        *(_bounded_generate(segment) for segment in SEGMENT_ORDER),
        return_exceptions=True,
    )
    results_by_segment: dict[MarketSegment, _SegmentGenerationResult] = {}
    for segment, raw_result in zip(SEGMENT_ORDER, raw_results, strict=True):
        if isinstance(raw_result, BaseException):
            raise raw_result
        results_by_segment[segment] = raw_result

    for segment in SEGMENT_ORDER:
        result = results_by_segment[segment]
        segment_timings[f"generate:{segment}"] = result.elapsed_s
        if result.failure is not None:
            failures[segment] = result.failure
            continue
        assert result.briefing is not None
        briefings[segment] = result.briefing
        if result.macro_lineage:
            macro_lineage_by_segment[segment] = result.macro_lineage

    if not briefings:
        # Preserve the original BGE routing when the run produced no
        # publishable segment at all.
        raise next(iter(failures.values()))

    _logger.info(
        "[generate] segmented briefings built target_date=%s ok=%d failed=%d",
        target_date,
        len(briefings),
        len(failures),
    )
    return (
        briefings,
        failures,
        bundle_context,
        fact_bundle,
        macro_lineage_by_segment,
        segment_timings,
    )


def _log_briefing_generation_error(exc: BriefingGenerationError) -> None:
    """Log u2 failure details that are otherwise only visible in alerts."""
    cause_type = type(exc.cause).__name__ if exc.cause is not None else None
    cause = str(exc.cause) if exc.cause is not None else None
    _logger.error(
        "[generate] failed stage=%s attempts=%s cause_type=%s cause=%s "
        "last_stderr=%s last_stdout=%s",
        exc.stage,
        exc.attempt_count,
        cause_type,
        cause,
        exc.last_stderr,
        exc.last_stdout,
        extra={
            "briefing_stage": exc.stage,
            "attempt_count": exc.attempt_count,
            "cause_type": cause_type,
            "cause": cause,
            "last_stderr": exc.last_stderr,
            "last_stdout": exc.last_stdout,
        },
    )


def _macro_lineage_trace_path(target_date: date, segment: MarketSegment) -> Path:
    from investo.publisher.paths import ARCHIVE_ROOT

    return ARCHIVE_ROOT / "_meta" / "run_traces" / target_date.isoformat() / f"{segment}.json"


def _macro_carryover_path() -> Path:
    from investo.publisher.paths import ARCHIVE_ROOT

    return ARCHIVE_ROOT / "_meta" / "macro_event_carryover.jsonl"


def _fact_snapshot_path() -> Path:
    from investo.publisher.paths import ARCHIVE_ROOT

    return ARCHIVE_ROOT / "_meta" / "fact_snapshots.jsonl"


def _persist_fact_snapshot_safely(
    target_date: date,
    *,
    fact_bundle: VerifiedFactBundle,
    observed_at: datetime,
    conflict_fact_ids: tuple[FactId, ...] = (),
) -> None:
    try:
        append_fact_snapshot_jsonl(
            _fact_snapshot_path(),
            fact_bundle,
            target_date=target_date,
            observed_at=observed_at,
            conflict_fact_ids=conflict_fact_ids,
        )
    except OSError as exc:
        _logger.warning(
            "[facts] snapshot persistence failed target_date=%s error=%s; continuing",
            target_date,
            exc,
        )


def _advance_and_persist_macro_carryover(
    target_date: date,
    items: Sequence[NormalizedItem],
    routed_candidates: SegmentedItems,
) -> None:
    """Advance + persist the u59 macro lifecycle carryover snapshot.

    Operator-only state under ``archive/_meta/``. This is a best-effort
    diagnostic surface: a persistence (or load) failure must never crash
    the pipeline, so any :class:`MacroCarryoverError` is logged as a
    WARNING and swallowed (mirrors the Step 7 lineage persistence).
    """
    path = _macro_carryover_path()
    try:
        prior_events = load_macro_lifecycle_events(path)
        next_events = advance_macro_lifecycle(
            prior_events,
            items,
            target_date,
            segment_for=lambda item: _segment_for_item(item, routed_candidates),
        )
        upsert_macro_lifecycle_snapshot(target_date, next_events, path=path)
    except MacroCarryoverError as exc:
        _logger.warning(
            "[macro_carryover] failed target_date=%s error=%s; continuing without carryover",
            target_date,
            exc,
        )


def _segment_for_item(item: NormalizedItem, routed: SegmentedItems) -> MarketSegment:
    """Map a collected item to its routed segment (default ``us-equity``)."""
    for segment in SEGMENT_ORDER:
        if any(candidate is item for candidate in routed.for_segment(segment)):
            return segment
    return US_EQUITY


def _write_macro_lineage_traces(
    target_date: date,
    *,
    segment: MarketSegment,
    traces: Sequence[MacroLineageTrace],
) -> Path:
    path = _macro_lineage_trace_path(target_date, segment)
    payload = {
        "target_date": target_date.isoformat(),
        "segment": segment,
        "watched_events": [trace.to_json_dict() for trace in traces],
    }
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        tmp.replace(path)
    except OSError as exc:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        raise PublisherIOError(target_date=target_date, path=path, cause=exc) from exc
    return path


def _log_macro_lineage_trace(segment: MarketSegment, trace: MacroLineageTrace) -> None:
    _logger.info(
        "[diagnostics] segment=%s event=%s collected=%s routed=%s stage1=%s stage2=%s "
        "final=%s diagnosis=%s",
        segment,
        trace.event_key,
        trace.collected,
        trace.routed_segment == segment,
        trace.selected_for_stage1 and trace.stage1_state == "assigned",
        trace.rendered_in_stage2_grouped_sections or trace.rendered_in_lookahead_block,
        trace.final_body_mentions and trace.final_body_has_source_link,
        trace.diagnosis,
        extra={
            "macro_lineage_segment": segment,
            "macro_lineage_event_key": trace.event_key,
            "macro_lineage_diagnosis": trace.diagnosis,
        },
    )


async def _stage_publish(
    briefing: Briefing,
    target_date: date,
    *,
    git_runner: GitRunner | None = None,
) -> Path:
    """Atomic write + git lifecycle, both bridged off the event loop.

    Two phases (per ``component-methods.md`` C5):

    1. ``write_briefing(briefing, target_date)`` — atomic markdown
       write to ``archive/YYYY/MM/YYYY-MM-DD.md``. Verifies the
       disclaimer FIRST (NFR-004 hard block); raises
       :class:`PublisherDisclaimerError` and writes nothing on
       missing disclaimer. Atomicity via tmp + ``os.replace``;
       :class:`PublisherIOError` on filesystem errors.
    2. ``commit_and_push("briefing: YYYY-MM-DD", [path], runner=...)``
       — 3-attempt git lifecycle (FD R3 backoff 0/2/8 s) with
       idempotent-commit detection on retry. Raises
       :class:`PublisherGitError` after exhaustion; ``last_stderr`` is
       1024-byte UTF-8 truncated by the error class itself.

    Both u3 functions are **sync**, so this stage uses ``asyncio
    .to_thread`` per TS-2 — keeping the orchestrator's async surface
    uniform and the event loop responsive (matters less here than for
    u4's notify, but pinning the convention so the integration test
    can still run other coroutines if needed).

    Parameters
    ----------
    briefing:
        Validated :class:`Briefing` from ``_stage_generate`` —
        ``rendered_markdown`` is what gets written; ``target_date`` on
        the briefing must match the parameter (orchestrator passes
        through; mismatch is a programmer error).
    target_date:
        Same date used by ``_stage_collect`` / ``_stage_generate``.
        Determines the archive path and the commit message.
    git_runner:
        Test seam forwarded to ``commit_and_push`` so integration
        tests can substitute a fake ``GitRunner`` Protocol
        implementation (per AC-006-1, AC-006-3).

    Returns
    -------
    Path
        Absolute path to the written ``archive/YYYY/MM/YYYY-MM-DD.md``.
        Used by ``run_pipeline`` to derive the public ``briefing_url``
        for the notify stage.

    Raises
    ------
    PublisherDisclaimerError
        Disclaimer missing from ``briefing.rendered_markdown`` —
        write was rejected before any I/O. Routed by
        ``run_pipeline`` per AC-003-4.
    PublisherIOError
        Atomic write failed (filesystem error). Routed per AC-003-4.
    PublisherGitError
        ``commit_and_push`` exhausted retries. Routed per AC-003-5;
        ``last_stderr`` (1024-byte truncated) propagates to the
        operator alert.
    """
    _logger.info("[publish] starting target_date=%s", target_date)

    # Phase 1 — write_briefing is sync; bridge to thread.
    archive_path = await asyncio.to_thread(write_briefing, briefing, target_date)
    _logger.info("[publish] wrote %s", archive_path)

    # Phase 2 — commit_and_push is sync; bridge to thread. The runner
    # parameter forwards through; ``None`` lets u3 use the real
    # subprocess runner.
    commit_message = f"briefing: {target_date}"
    dry_run = _is_dry_run()
    await asyncio.to_thread(
        commit_and_push,
        commit_message,
        [archive_path],
        runner=git_runner,
        dry_run=dry_run,
    )
    if dry_run:
        _logger.info("[publish] dry-run — skipped git commit + push for %s", target_date)
    else:
        _logger.info("[publish] committed + pushed %s", target_date)
    return archive_path


async def _stage_publish_segments(
    briefings: dict[MarketSegment, Briefing],
    target_date: date,
    *,
    asset_paths: Sequence[Path] = (),
    git_runner: GitRunner | None = None,
    items: Sequence[NormalizedItem] = (),
    source_outcomes: Sequence[SourceOutcome] = (),
    macro_lineage_by_segment: Mapping[MarketSegment, Sequence[MacroLineageTrace]] | None = None,
    fact_bundle: VerifiedFactBundle | None = None,
) -> dict[MarketSegment, Path]:
    """Write all segment archive files, then commit/push them together.

    The set is best-effort atomic before git commit: all disclaimers are
    validated up front, and any write failure rolls back files already
    written in this stage to their prior bytes or absence.
    """
    _logger.info("[publish] starting segmented target_date=%s", target_date)

    archive_paths: dict[MarketSegment, Path] = {}
    if fact_bundle is None:
        try:
            fact_bundle = build_verified_fact_bundle(tuple(items), target_date, datetime.now(UTC))
        except VerifiedFactConflictError as exc:
            _logger.warning(
                "[publish] fact conflict fact_id=%s values=%s; entity guard uses unverified state",
                exc.fact_id,
                exc.values,
            )
            fact_bundle = VerifiedFactBundle(target_date=target_date)
    entity_now_utc = datetime.now(UTC)
    entity_blocked: dict[MarketSegment, object] = {}
    for segment in SEGMENT_ORDER:
        briefing = briefings.get(segment)
        if briefing is None:
            continue
        violations = scan_entity_fact_claims(
            briefing.rendered_markdown,
            fact_bundle,
            target_date,
            entity_now_utc,
            segment=segment,
        )
        if violations:
            entity_blocked[segment] = violations
            for violation in violations:
                _logger.error(
                    "[publish] entity fact blocked segment=%s fact_id=%s expected=%s "
                    "term=%s line=%d preview=%s",
                    violation.segment,
                    violation.fact_id,
                    violation.expected_value,
                    violation.offending_term,
                    violation.line_number,
                    violation.preview,
                )
    if entity_blocked:
        briefings = {
            segment: briefing
            for segment, briefing in briefings.items()
            if segment not in entity_blocked
        }
        if not briefings:
            raise PublisherDisclaimerError(target_date=target_date)

    published_segments = tuple(segment for segment in SEGMENT_ORDER if segment in briefings)
    snapshot_paths = [
        *(compute_archive_path(target_date, segment=segment) for segment in published_segments),
    ]
    snapshots: dict[Path, bytes | None] = {
        path: _read_existing_bytes(path) for path in snapshot_paths
    }
    snapshots.update({path: None for path in asset_paths})
    briefings = _rewrite_segment_nav_for_published_segments(
        briefings,
        target_date=target_date,
        published_segments=published_segments,
    )

    # u56 — ensure the segment-aware first-viewport short disclaimer is
    # present BEFORE the gate checks it. The reader-format chain inserts
    # it for full run_pipeline paths; this defensive pass covers callers
    # that bypass _apply_reader_format_to_segments (e.g. unit tests
    # exercising _stage_publish_segments directly). Idempotent — a
    # second insertion is a noop.
    briefings = {
        segment: briefing.model_copy(
            update={
                "rendered_markdown": emit_first_viewport_disclaimer(
                    briefing.rendered_markdown, segment
                )
            }
        )
        if emit_first_viewport_disclaimer(briefing.rendered_markdown, segment)
        != briefing.rendered_markdown
        else briefing
        for segment, briefing in briefings.items()
    }

    try:
        for segment in published_segments:
            canonical_markdown = ensure_canonical_disclaimer(
                briefings[segment].rendered_markdown,
                segment,
            )
            if canonical_markdown != briefings[segment].rendered_markdown:
                _logger.warning(
                    "[publish] repaired canonical disclaimer segment=%s",
                    segment,
                )
                briefings[segment] = briefings[segment].model_copy(
                    update={"rendered_markdown": canonical_markdown}
                )
            repaired_markdown = repair_first_viewport_summary(briefings[segment].rendered_markdown)
            if repaired_markdown != briefings[segment].rendered_markdown:
                _logger.warning(
                    "[publish] repaired first-viewport summary segment=%s",
                    segment,
                )
                briefings[segment] = briefings[segment].model_copy(
                    update={"rendered_markdown": repaired_markdown}
                )
            segment_items_for_evidence = segment_items(items).for_segment(segment)
            verified_report = verify_core_facts(
                briefings[segment].rendered_markdown,
                segment_items_for_evidence,
            )
            evidence_counts = count_rendered_evidence(
                briefings[segment].rendered_markdown,
                segment=segment,
                source_outcomes=segment_source_outcomes(segment, source_outcomes),
                verified_facts=tuple(verified_report.verified),
            )
            updated_markdown = render_body_used_count(
                briefings[segment].rendered_markdown,
                evidence_counts,
            )
            if updated_markdown != briefings[segment].rendered_markdown:
                briefings[segment] = briefings[segment].model_copy(
                    update={"rendered_markdown": updated_markdown}
                )
            # u85 — the per-segment publish-boundary gate trio is run
            # through the shared validator registry (first-viewport
            # summary → canonical disclaimer footer → first-viewport short
            # disclaimer), preserving order, the raise-at-boundary
            # ``SummaryQualityError`` (raised inside the summary gate), and
            # the ``PublisherDisclaimerError`` raised here on the first
            # blocking disclaimer result with the same log line.
            for _gate_result in build_publish_boundary_registry(
                markdown=briefings[segment].rendered_markdown,
                segment=segment,
            ).run():
                if _gate_result.is_block:
                    _logger.error("[publish] %s", _gate_result.message)
                    raise PublisherDisclaimerError(target_date=target_date)
    except (SummaryQualityError, PublisherDisclaimerError, PublisherIOError):
        # Visual asset files (snapshotted with previous_bytes=None) must be
        # rolled back — otherwise a SummaryQualityError leaves orphan
        # ``*.assets/`` SVGs on disk that the next run picks up as stale.
        _rollback_paths(snapshots)
        raise

    try:
        index_paths: tuple[Path, ...] = ()
        weekly_paths: tuple[Path, ...] = ()
        macro_lineage_paths: tuple[Path, ...] = ()
        for segment in published_segments:
            archive_path = await asyncio.to_thread(
                write_briefing,
                briefings[segment],
                target_date,
                segment=segment,
            )
            from investo.publisher.paths import ARCHIVE_ROOT, normalize_archive_publish_path

            try:
                normalized_archive_path = normalize_archive_publish_path(
                    archive_path,
                    archive_root=ARCHIVE_ROOT,
                )
            except ValueError as exc:
                raise PublisherIOError(
                    target_date=target_date,
                    path=archive_path,
                    cause=OSError(str(exc)),
                ) from exc
            archive_paths[segment] = normalized_archive_path
            _logger.info("[publish] wrote segment=%s path=%s", segment, archive_path)
            if macro_lineage_by_segment is not None:
                traces = tuple(macro_lineage_by_segment.get(segment, ()))
                if traces:
                    lineage_path = _macro_lineage_trace_path(target_date, segment)
                    snapshots[lineage_path] = _read_existing_bytes(lineage_path)
                    written_lineage_path = await asyncio.to_thread(
                        _write_macro_lineage_traces,
                        target_date,
                        segment=segment,
                        traces=traces,
                    )
                    macro_lineage_paths = (*macro_lineage_paths, written_lineage_path)
                    for trace in traces:
                        _log_macro_lineage_trace(segment, trace)
        if archive_paths:
            # Snapshot every page the index/heatmap update may rewrite so a
            # subsequent ``write_briefing`` failure rolls them back too.
            snapshots.update(
                {
                    SITE_INDEX_PATH: _read_existing_bytes(SITE_INDEX_PATH),
                    ARCHIVE_INDEX_PATH: _read_existing_bytes(ARCHIVE_INDEX_PATH),
                    OG_CARD_RELATIVE_PATH: _read_existing_bytes(OG_CARD_RELATIVE_PATH),
                    OG_CARD_PNG_RELATIVE_PATH: _read_existing_bytes(OG_CARD_PNG_RELATIVE_PATH),
                    manifest_path_for(OG_CARD_RELATIVE_PATH): _read_existing_bytes(
                        manifest_path_for(OG_CARD_RELATIVE_PATH)
                    ),
                    manifest_path_for(OG_CARD_PNG_RELATIVE_PATH): _read_existing_bytes(
                        manifest_path_for(OG_CARD_PNG_RELATIVE_PATH)
                    ),
                }
            )
            for segment_index_path in SEGMENT_ARCHIVE_INDEX_PATHS.values():
                snapshots[segment_index_path] = _read_existing_bytes(segment_index_path)

            heatmap_svg = await asyncio.to_thread(
                _build_publish_heatmap_svg,
                target_date,
            )
            index_paths = await asyncio.to_thread(
                update_latest_index_pages,
                target_date,
                segment_briefings=briefings,
                heatmap_svg=heatmap_svg,
            )
            og_card_paths = await asyncio.to_thread(
                write_og_card,
                target_date,
                briefings,
            )
            if isinstance(og_card_paths, Path):
                og_card_paths = (og_card_paths,)
            index_paths = (*index_paths, *og_card_paths)
            # u32 Step 4 — public quality dashboard. Snapshot first so a
            # later atomic-rollback also reverses the dashboard write.
            quality_history_path = resolve_quality_history_path()
            quality_history_paths: tuple[Path, ...] = ()
            # u54 — derive per-segment severity once so both the quality
            # snapshot and the coverage.jsonl line carry the same view.
            quality_segmented_items = segment_items(items)
            severities_by_segment_for_quality: dict[MarketSegment, str] = {
                segment: quality_segmented_items.coverage_for_segment(
                    segment, source_outcomes=source_outcomes
                ).status
                for segment in published_segments
            }
            if not _is_dry_run():
                snapshots[quality_history_path] = _read_existing_bytes(quality_history_path)
                written_quality_history = await asyncio.to_thread(
                    append_quality_snapshot,
                    target_date,
                    snapshot=_build_quality_snapshot(
                        briefings=briefings,
                        published_segments=published_segments,
                        items=items,
                        source_outcomes=source_outcomes,
                        severities_by_segment=severities_by_segment_for_quality,
                    ),
                    history_path=quality_history_path,
                )
                quality_history_paths = (written_quality_history,)
            quality_path_resolved = _site_index_mod.QUALITY_PAGE_PATH
            snapshots[quality_path_resolved] = _read_existing_bytes(quality_path_resolved)
            quality_path = await asyncio.to_thread(
                update_quality_page,
                target_date,
                coverage_path=source_health.resolve_coverage_path(),
                archive_root=ARCHIVE_ROOT,
                quality_history_path=quality_history_path,
                quality_page_path=quality_path_resolved,
            )
            index_paths = (*index_paths, *quality_history_paths, quality_path)

            # u69 — publish-boundary canonical quality-consistency gate.
            # Runs after the quality / history / index pages are rendered
            # and before commit. Compares the per-segment markdown status
            # blocks against the quality-history row and the rendered
            # dashboard so a healthier-looking public surface cannot ship
            # alongside a failed / limited archive body. A genuine
            # contradiction rolls back this run's writes and raises.
            await asyncio.to_thread(
                _enforce_quality_consistency_gate,
                target_date,
                briefings=briefings,
                history_path=quality_history_path,
                quality_page_path=quality_path_resolved,
            )

            forecast_paths: tuple[Path, ...] = ()
            if not _is_dry_run():
                forecast_log_path = resolve_forecast_log_path()
                snapshots[forecast_log_path] = _read_existing_bytes(forecast_log_path)
                snapshots[ACCURACY_PAGE_PATH] = _read_existing_bytes(ACCURACY_PAGE_PATH)
                forecast_log_written = await asyncio.to_thread(
                    append_forecast_entries,
                    target_date,
                    segment_briefings=briefings,
                    published_at=datetime.now(UTC),
                    briefing_urls=_forecast_briefing_urls(target_date, published_segments),
                    log_path=forecast_log_path,
                )
                accuracy_page = await asyncio.to_thread(
                    update_accuracy_page,
                    forecast_log_path=forecast_log_path,
                    accuracy_page_path=ACCURACY_PAGE_PATH,
                )
                forecast_paths = (forecast_log_written, accuracy_page)
            index_paths = (*index_paths, *forecast_paths)

            monthly_paths: tuple[Path, ...] = ()
            if not _is_dry_run():
                monthly_paths = await asyncio.to_thread(
                    _maybe_publish_monthly_retrospective,
                    target_date,
                    snapshots,
                )
            index_paths = (*index_paths, *monthly_paths)
            # u33 Step 3 — per-ticker accumulation pages. Recompute the
            # full match set across all segments (cheap pure function);
            # the writer is idempotent so re-running for the same
            # target_date replaces only that day's section.
            from investo.briefing.watchlist import (
                load_watchlist,
                match_watchlist_items,
            )
            from investo.briefing.watchlist_impact import build_impact_center
            from investo.publisher.watchlist_pages import (
                update_watchlist_pages,
                watchlist_publish_paths_for,
                write_daily_impact_page,
            )

            watchlist_cfg = load_watchlist()
            all_matches: list[Any] = []
            all_items_for_match: list[Any] = []
            if watchlist_cfg.is_configured:
                for segment_for_match in SEGMENT_ORDER:
                    if segment_for_match not in briefings:
                        continue
                    segment_items_for_match = segment_items(items).for_segment(segment_for_match)
                    all_items_for_match.extend(segment_items_for_match)
                    impact_for_match = match_watchlist_items(segment_items_for_match, watchlist_cfg)
                    all_matches.extend(impact_for_match.matches)
            for path in watchlist_publish_paths_for(all_matches):
                snapshots.setdefault(path, _read_existing_bytes(path))
            watchlist_paths = await asyncio.to_thread(
                update_watchlist_pages,
                target_date,
                all_matches,
            )
            # u73 — daily-first impact center page. Recompute the grouped
            # center across all segments (Direct/Related/Uncertain/Rejected)
            # and write today's impacts as the first content block. The
            # writer fully regenerates the page so re-runs are idempotent.
            combined_impact = match_watchlist_items(all_items_for_match, watchlist_cfg)
            impact_center = build_impact_center(
                combined_impact,
                items=all_items_for_match,
                config=watchlist_cfg,
            )
            _briefing_urls = _forecast_briefing_urls(target_date, published_segments)
            daily_segment_links = [
                (SEGMENT_LABELS[segment_for_link], _briefing_urls[segment_for_link])
                for segment_for_link in SEGMENT_ORDER
                if segment_for_link in briefings
            ]
            daily_path = await asyncio.to_thread(
                write_daily_impact_page,
                target_date,
                impact_center,
                segment_links=daily_segment_links,
            )
            watchlist_paths = (*watchlist_paths, daily_path)
            index_paths = (*index_paths, *watchlist_paths)
            # u29 weekly retrospective — opt-in via INVESTO_PUBLISH_WEEKLY=1
            # set by the GHA Saturday cron path. Failing here would block
            # the segmented publish (which is already on disk), so we
            # treat weekly publish as part of the same atomic try block.
            if weekly_digest_opt_in() and len(published_segments) == len(SEGMENT_ORDER):
                weekly_md_path = compute_weekly_path(target_date)
                snapshots[weekly_md_path] = _read_existing_bytes(weekly_md_path)
                snapshots[WEEKLY_INDEX_PATH] = _read_existing_bytes(WEEKLY_INDEX_PATH)
                written_weekly = await asyncio.to_thread(
                    publish_weekly_digest,
                    target_date,
                )
                weekly_index_path = await asyncio.to_thread(update_weekly_index)
                weekly_paths = (written_weekly, weekly_index_path)
                _logger.info(
                    "[publish] weekly digest written %s + index %s",
                    written_weekly,
                    weekly_index_path,
                )
    except (
        PublisherDisclaimerError,
        PublisherIOError,
        QualityHistoryError,
        ForecastLogError,
        QualityConsistencyError,
    ):
        _rollback_paths(snapshots)
        raise

    commit_message = (
        f"briefing: {target_date} segmented"
        if len(published_segments) == len(SEGMENT_ORDER)
        else f"briefing: {target_date} segmented partial"
    )
    dry_run = _is_dry_run()
    await asyncio.to_thread(
        commit_and_push,
        commit_message,
        [
            *archive_paths.values(),
            *asset_paths,
            *macro_lineage_paths,
            *index_paths,
            *weekly_paths,
        ],
        runner=git_runner,
        dry_run=dry_run,
    )
    if dry_run:
        _logger.info("[publish] dry-run — skipped git commit + push for segmented %s", target_date)
    else:
        _logger.info("[publish] committed + pushed segmented %s", target_date)
    return archive_paths


def _inject_chart_blocks_into_segments(
    segment_briefings: dict[MarketSegment, Briefing],
    *,
    target_date: date,
    anchors_by_segment: Mapping[MarketSegment, Sequence[MarketAnchor]],
    history_by_ticker: Mapping[str, Sequence[OHLCRow]],
) -> tuple[dict[MarketSegment, Briefing], tuple[Path, ...]]:
    """Insert a Lightweight Charts placeholder block into each briefing (u75).

    The heavy OHLC history no longer rides inline: each placeholder
    carries only a small ``data-history-src`` relative URL and the per-
    chart history is written to a deterministic sidecar JSON file next
    to the segment markdown / visual assets. The JS layer lazy-fetches
    the sidecar on expand.

    Relies only on the supplied anchors / history dicts plus the target
    date; no network, no clock (the sidecar provenance uses
    ``target_date``). Idempotent — re-running with the same inputs
    yields byte-equal markdown AND byte-equal sidecar files so same-day
    re-runs (FR-006) do not duplicate or churn the block.

    Returns ``(rewritten_briefings, sidecar_paths)``. ``sidecar_paths``
    are the absolute on-disk paths the publish stage must stage / commit
    alongside the markdown. Segments without matching history (or with
    the section-five header missing) are passed through unchanged and
    contribute no sidecar.
    """
    if not history_by_ticker:
        return segment_briefings, ()
    rewritten: dict[MarketSegment, Briefing] = {}
    sidecar_paths: list[Path] = []
    for segment, briefing in segment_briefings.items():
        anchors = anchors_by_segment.get(segment, ())
        if not anchors:
            rewritten[segment] = briefing
            continue
        artifacts = build_chart_artifacts(
            anchors,
            history_by_ticker,
            segment=segment,
            markdown_stem=target_date.isoformat(),
            run_date=target_date,
        )
        if not artifacts.block:
            rewritten[segment] = briefing
            continue
        new_md = inject_chart_block(briefing.rendered_markdown, artifacts.block)
        if new_md == briefing.rendered_markdown:
            rewritten[segment] = briefing
            continue
        markdown_path = compute_archive_path(target_date, segment=segment)
        for sidecar in artifacts.sidecars:
            sidecar_paths.append(write_chart_sidecar(sidecar, markdown_path))
        rewritten[segment] = briefing.model_copy(update={"rendered_markdown": new_md})
    return rewritten, tuple(sidecar_paths)


# u51 — pre-publish reader-format pass.
#
# Two rewrites:
#   1. Replace the deprecated ``> **시장 anchor**: ...`` blockquote line
#      (u49) with a 4-column markdown table (Plan Step 2).
#   2. Run the pure ``apply_reader_format`` chain (Plan Step 3): TL;DR
#      block insert / H3 promotion / number bold / glossing dedupe /
#      action-ratio diagnostic.
#
# Position: invoked AFTER ``_inject_chart_blocks_into_segments`` and
# BEFORE ``_stage_publish_segments``. The chain is a string transform
# only — no I/O, no clock, no env reads — so a same-day re-publish
# (FR-006) yields byte-equal output.
#
# ---------------------------------------------------------------------------
# P1-2 — header-table / body / trace close reconciliation (option B).
#
# Root cause: the anchor header table renders ``MarketAnchor.close`` (the
# last OHLCV bar from ``yfinance_history``), while the body prose and the
# trace footer cite the price-snapshot ``NormalizedItem`` close (stooq-price
# / yfinance). The two feeds differ by provider / timestamp / resolution, so
# the same ticker can show e.g. AAPL 304.99 (header) vs 305.10 (trace).
#
# Fix: reconcile the *display* close only. We extract the per-ticker snapshot
# close from the collected price items — exactly the value the body + trace
# derive from — and override ``MarketAnchor.close`` when it disagrees beyond
# tolerance. ATH / 52w / MTD / YTD / pct stay history-derived (NOT
# recomputed): only the displayed close is swapped so all three surfaces
# agree. Tickers without a snapshot keep the history close (safe fallback).
#
# Mapping: both stooq-price and yfinance stamp ``raw_metadata["ticker"]`` in
# the same yfinance vocabulary the anchors use (``^GSPC`` / ``AAPL`` /
# ``BTC-USD``) plus ``raw_metadata["close"]``. That ticker key is the
# universal snapshot (covers indices AND individual stocks); the
# ``core_fact:`` keys are a redundant overlay for the 12 mapped tickers
# derived from the *same* ``close`` value, so matching on the raw ticker is
# both broader and equivalent.

# Override fires when the absolute difference exceeds $0.01 OR the relative
# difference exceeds 0.05 % — below that the feeds are effectively equal and
# a swap would only churn the bytes.
_ANCHOR_CLOSE_ABS_TOLERANCE: Final[Decimal] = Decimal("0.01")
_ANCHOR_CLOSE_REL_TOLERANCE: Final[Decimal] = Decimal("0.0005")  # 0.05 %


def _reconcile_anchor_closes(
    anchors_by_segment: Mapping[MarketSegment, Sequence[MarketAnchor]],
    snapshot_close: Mapping[str, Decimal],
) -> dict[MarketSegment, tuple[MarketAnchor, ...]]:
    """Override each anchor's display close with the snapshot value (option B).

    Returns a fresh per-segment map. For every anchor whose ticker has a
    snapshot close differing beyond tolerance, the displayed ``close`` is
    replaced (via ``model_copy``) with the snapshot value; derived fields
    (ATH / 52w / MTD / YTD / pct / volume_z_score) are preserved unchanged
    because they remain history-correct. Anchors without a snapshot, or
    within tolerance, pass through untouched.
    """
    reconciled: dict[MarketSegment, tuple[MarketAnchor, ...]] = {}
    for segment, anchors in anchors_by_segment.items():
        out: list[MarketAnchor] = []
        for anchor in anchors:
            snapshot = snapshot_close.get(anchor.ticker)
            if snapshot is None or not _close_differs(anchor.close, snapshot):
                out.append(anchor)
                continue
            _logger.info(
                "[market_anchor] reconciled display close ticker=%s history=%s snapshot=%s",
                anchor.ticker,
                anchor.close,
                snapshot,
            )
            out.append(anchor.model_copy(update={"close": snapshot}))
        reconciled[segment] = tuple(out)
    return reconciled


def _close_differs(history: Decimal, snapshot: Decimal) -> bool:
    """True when ``snapshot`` exceeds the abs OR rel tolerance vs ``history``.

    The dual tolerance is a no-churn floor (avoid swapping bytes when the
    two feeds agree modulo Decimal-quantization). Either threshold being
    exceeded counts as "different" → the goal is identical closes across
    surfaces, so the bar for triggering an override is deliberately low
    (the real bug was AAPL 304.99 vs 305.10 — a $0.11 / 0.036 % gap).
    """
    abs_diff = abs(history - snapshot)
    if abs_diff > _ANCHOR_CLOSE_ABS_TOLERANCE:
        return True
    return history != 0 and abs_diff / abs(history) > _ANCHOR_CLOSE_REL_TOLERANCE


def _inject_carryover_into_segments(
    segment_briefings: dict[MarketSegment, Briefing],
    *,
    carryover_by_segment: Mapping[MarketSegment, BriefingCarryover],
) -> dict[MarketSegment, Briefing]:
    """Post-process per-segment markdown with the u52 carryover block.

    Returns a fresh dict where every segment's :class:`Briefing` has
    the Watchlist Carryover block injected (or replaced) at the §② →
    §③ boundary. Empty :class:`BriefingCarryover` for a segment leaves
    that segment's markdown untouched (modulo stale-block strip on
    same-day re-runs — see :func:`inject_carryover_block`).

    Pure string transform — no I/O, no clock, no env reads — so a
    same-day re-publish (FR-006) yields byte-equal output.
    Disclaimer enforcement: the block lands above §⑦ (disclaimer is
    appended by ``append_disclaimer`` after segment generation). The
    publisher's ``verify_disclaimer`` gate runs on the final markdown.
    """
    if not segment_briefings:
        return segment_briefings
    rewritten: dict[MarketSegment, Briefing] = {}
    for segment, briefing in segment_briefings.items():
        carryover = carryover_by_segment.get(segment)
        if carryover is None:
            rewritten[segment] = briefing
            continue
        block = render_carryover_block(carryover)
        new_markdown = inject_carryover_block(briefing.rendered_markdown, block)
        if new_markdown == briefing.rendered_markdown:
            rewritten[segment] = briefing
        else:
            rewritten[segment] = briefing.model_copy(update={"rendered_markdown": new_markdown})
    return rewritten


def _filter_entity_fact_violations(
    segment_briefings: dict[MarketSegment, Briefing],
    *,
    fact_bundle: VerifiedFactBundle,
    target_date: date,
    now_utc: datetime,
) -> tuple[dict[MarketSegment, Briefing], tuple[MarketSegment, ...]]:
    """Drop segments whose current-role claims contradict verified facts."""

    blocked: list[MarketSegment] = []
    for segment in SEGMENT_ORDER:
        briefing = segment_briefings.get(segment)
        if briefing is None:
            continue
        violations = scan_entity_fact_claims(
            briefing.rendered_markdown,
            fact_bundle,
            target_date,
            now_utc,
            segment=segment,
        )
        if not violations:
            continue
        blocked.append(segment)
        for violation in violations:
            _logger.error(
                "[publish] entity fact blocked segment=%s fact_id=%s expected=%s "
                "term=%s line=%d preview=%s",
                violation.segment,
                violation.fact_id,
                violation.expected_value,
                violation.offending_term,
                violation.line_number,
                violation.preview,
            )
    if not blocked:
        return segment_briefings, ()
    blocked_set = set(blocked)
    return (
        {
            segment: briefing
            for segment, briefing in segment_briefings.items()
            if segment not in blocked_set
        },
        tuple(blocked),
    )


def _build_quality_snapshot(
    *,
    briefings: dict[MarketSegment, Briefing],
    published_segments: Sequence[MarketSegment],
    items: Sequence[NormalizedItem],
    source_outcomes: Sequence[SourceOutcome],
    severities_by_segment: dict[MarketSegment, str] | None = None,
) -> QualitySnapshot:
    from investo.publisher.quality_consistency import parse_segment_status_block

    failed_sources = sum(1 for outcome in source_outcomes if outcome.status == "failed")
    zero_item_sources = sum(1 for outcome in source_outcomes if outcome.status == "zero")
    # u54 — Liveness denominator counts only segments with ≥ 1 registered
    # core source so a future segment without core registration cannot
    # silently dilute the rate. Today every segment has core sources
    # registered, but the guard future-proofs the denominator.
    from investo.briefing.segments import SEGMENT_CORE_SOURCES

    core_eligible_segments = sum(
        1 for segment in published_segments if SEGMENT_CORE_SOURCES.get(segment)
    )
    source_liveness = (
        1.0 if source_outcomes and failed_sources == 0 and core_eligible_segments > 0 else 0.0
    )
    bodies = [briefings[segment].rendered_markdown for segment in published_segments]
    routed = segment_items(items)
    evidence_by_segment = {
        segment: count_rendered_evidence(
            briefings[segment].rendered_markdown,
            segment=segment,
            source_outcomes=segment_source_outcomes(segment, source_outcomes),
            verified_facts=tuple(
                verify_core_facts(
                    briefings[segment].rendered_markdown,
                    routed.for_segment(segment),
                ).verified
            ),
        )
        for segment in published_segments
    }
    data_limited_markers = ("[데이터부족]", "데이터 부족 안내", "실시간 안내")
    data_limited_count = sum(
        1 for body in bodies if any(marker in body for marker in data_limited_markers)
    )
    non_limited = max(len(bodies) - data_limited_count, 0)
    figures_count = sum(
        1 for body in bodies if "데이터 부족 안내" not in body and extract_flaggable_numbers(body)
    )
    verified_figures_count = sum(
        1 for segment in published_segments if evidence_by_segment[segment].verified_figure_mentions
    )
    worst_severity: str | None = None
    if severities_by_segment:
        rank = {"normal": 0, "partial": 1, "limited": 2, "failed": 3}
        worst_severity = max(severities_by_segment.values(), key=lambda s: rank.get(s, -1))
    current_run_core_missing_segments = (
        sum(1 for severity in severities_by_segment.values() if severity in ("limited", "failed"))
        if severities_by_segment
        else 0
    )
    status_block_limited_or_worse = sum(
        1
        for segment in published_segments
        if parse_segment_status_block(briefings[segment].rendered_markdown, segment).status
        in ("limited", "failed")
    )
    current_run_segments_limited_or_worse = max(
        current_run_core_missing_segments,
        status_block_limited_or_worse,
    )
    domestic_verdicts = domestic_anchor_verdicts(
        items,
        target_date=briefings[published_segments[0]].target_date if published_segments else None,
        source_outcomes=source_outcomes,
    )
    domestic_withheld_count = sum(1 for verdict in domestic_verdicts if verdict.trust != "trusted")
    domestic_withheld_reasons = tuple(
        reason
        for reason in ("unavailable", "stale", "implausible", "provenance_missing")
        if any(verdict.trust == reason for verdict in domestic_verdicts)
    )
    return QualitySnapshot(
        source_liveness=source_liveness,
        figures_presence=(figures_count / non_limited) if non_limited > 0 else 0.0,
        figures_verified=(verified_figures_count / non_limited) if non_limited > 0 else None,
        fallback_ratio=(data_limited_count / len(bodies)) if bodies else 0.0,
        published_segments=len(published_segments),
        total_items=len(items),
        total_failed_sources=failed_sources,
        worst_severity=worst_severity,
        current_run_zero_item_sources=zero_item_sources,
        current_run_core_missing_segments=current_run_core_missing_segments,
        current_run_segments_limited_or_worse=current_run_segments_limited_or_worse,
        current_run_data_limited_briefings=data_limited_count,
        current_run_briefings_observed=len(bodies),
        domestic_anchor_withheld_count=domestic_withheld_count,
        domestic_anchor_withheld_reasons=domestic_withheld_reasons,
    )


class QualityConsistencyError(RuntimeError):
    """u69 — raised when public quality surfaces contradict the archive.

    Aborts the publish so a healthier-looking dashboard / index / history
    row cannot ship alongside a failed / limited / data-limited segment
    body. Carries the deterministic finding codes for operator triage.
    """


def _enforce_quality_consistency_gate(
    target_date: date,
    *,
    briefings: dict[MarketSegment, Briefing],
    history_path: Path,
    quality_page_path: Path,
) -> None:
    """u69 — publish-boundary canonical quality-consistency gate.

    Skipped (``quality_page_missing``) surfaces never fail. A genuine
    contradiction raises :class:`QualityConsistencyError` so the caller's
    rollback reverses this run's writes.
    """
    from investo.publisher.quality_consistency import validate_date_quality_consistency

    segment_texts = {segment: briefing.rendered_markdown for segment, briefing in briefings.items()}
    page_text = (
        quality_page_path.read_text(encoding="utf-8") if quality_page_path.exists() else None
    )
    findings = validate_date_quality_consistency(
        target_date,
        segment_texts=segment_texts,
        history_path=history_path,
        quality_page_text=page_text,
    )
    failures = [finding for finding in findings if finding.is_failure]
    for finding in findings:
        if finding.skipped:
            _logger.info("[publish] quality-consistency skipped: %s", finding.code)
    if failures:
        codes = ", ".join(sorted({finding.code for finding in failures}))
        details = "; ".join(finding.message for finding in failures)
        raise QualityConsistencyError(
            f"quality-consistency gate failed for {target_date.isoformat()} [{codes}]: {details}"
        )


def _forecast_briefing_urls(
    target_date: date,
    published_segments: Sequence[MarketSegment],
) -> dict[MarketSegment, str]:
    return {
        segment: f"archive/{segment}/{target_date:%Y}/{target_date:%m}/{target_date.isoformat()}.md"
        for segment in published_segments
    }


def _rewrite_segment_nav_for_published_segments(
    briefings: dict[MarketSegment, Briefing],
    *,
    target_date: date,
    published_segments: Sequence[MarketSegment],
) -> dict[MarketSegment, Briefing]:
    """Rewrite nav so partial publishes label missing segments explicitly."""
    published_set = set(published_segments)
    rewritten: dict[MarketSegment, Briefing] = {}
    for segment, briefing in briefings.items():
        nav_line = _segment_nav_line(
            target_date,
            current_segment=segment,
            published_segments=published_set,
        )
        markdown = _SEGMENT_NAV_LINE_RE.sub(nav_line, briefing.rendered_markdown, count=1)
        rewritten[segment] = briefing.model_copy(update={"rendered_markdown": markdown})
    return rewritten


def _segment_nav_line(
    target_date: date,
    *,
    current_segment: MarketSegment,
    published_segments: set[MarketSegment],
) -> str:
    parts: list[str] = []
    filename = f"{target_date.isoformat()}.md"
    for segment in SEGMENT_ORDER:
        label = SEGMENT_LABELS[segment]
        if segment not in published_segments:
            parts.append(f"{label}(미발행)")
            continue
        href = (
            filename
            if segment == current_segment
            else f"../../../{segment}/{target_date.year}/{target_date.month:02d}/{filename}"
        )
        parts.append(f"[{label}]({href})")
    return f"**세그먼트**: {' | '.join(parts)}"


def _maybe_publish_monthly_retrospective(
    target_date: date,
    snapshots: dict[Path, bytes | None],
) -> tuple[Path, ...]:
    if target_date.day != 1:
        return ()
    from investo.publisher.paths import ARCHIVE_ROOT

    previous_year = target_date.year if target_date.month > 1 else target_date.year - 1
    previous_month = target_date.month - 1 if target_date.month > 1 else 12
    if not month_has_archive_days(previous_year, previous_month, archive_root=ARCHIVE_ROOT):
        return ()
    monthly_root = ARCHIVE_ROOT / "monthly"
    monthly_path = monthly_root / f"{previous_year:04d}-{previous_month:02d}.md"
    monthly_index_path = monthly_root / "index.md"
    snapshots[monthly_path] = _read_existing_bytes(monthly_path)
    snapshots[monthly_index_path] = _read_existing_bytes(monthly_index_path)
    monthly_path.parent.mkdir(parents=True, exist_ok=True)
    body = render_monthly_retrospective(
        previous_year,
        previous_month,
        archive_root=ARCHIVE_ROOT,
    )
    monthly_path.write_text(body, encoding="utf-8")
    index_path = update_monthly_index(monthly_root=monthly_root)
    return (monthly_path, index_path)


def _build_publish_heatmap_svg(target_date: date) -> str:
    """Scan the archive root and render the publish-calendar heatmap.

    Lives at module scope so the orchestrator can run it via
    ``asyncio.to_thread``. The function reads from the repo-root-relative
    archive directory and is therefore cwd-sensitive in the same way as
    :func:`investo.publisher.writer.write_briefing` — production runs
    invoke the pipeline from the repo root.
    """
    from investo.publisher.paths import ARCHIVE_ROOT

    cells = scan_publish_coverage(ARCHIVE_ROOT, today=target_date)
    return render_publish_heatmap(cells, today=target_date)


async def _stage_prepare_segment_visual_assets(
    briefings: dict[MarketSegment, Briefing],
    items: Sequence[NormalizedItem],
    target_date: date,
    *,
    source_outcomes: Sequence[SourceOutcome] = (),
) -> tuple[dict[MarketSegment, Briefing], tuple[Path, ...]]:
    """Generate visual assets and return briefings with relative image links."""
    from investo.publisher.paths import ARCHIVE_ROOT

    archive_layout = ArchiveLayout(ARCHIVE_ROOT)
    routed = segment_items(items)
    watchlist_config = load_watchlist()
    curated_runtime = _load_curated_runtime_safely()
    concurrency = _visual_prep_concurrency_from_env()
    semaphore = asyncio.Semaphore(concurrency)

    async def _prepare_one(segment: MarketSegment) -> _VisualPrepResult:
        segment_source_items = routed.for_segment(segment)
        segment_coverage = routed.coverage_for_segment(
            segment,
            source_outcomes=source_outcomes,
        )
        prepared_kwargs: dict[str, Any] = {
            "archive_layout": archive_layout,
            "target_date": target_date,
            "segment": segment,
            "items": segment_source_items,
            "coverage": segment_coverage,
            "watchlist_impact": match_watchlist_items(
                segment_source_items,
                watchlist_config,
                coverage_status=segment_coverage.status,
            ),
        }
        if curated_runtime is not None:
            curated_library, curated_registry, select_curated_asset = curated_runtime
            curated_selection = select_curated_asset(
                segment,
                segment_source_items,
                curated_library,
                curated_registry,
            )
            if curated_selection is not None:
                prepared_kwargs["curated_selection"] = curated_selection
        async with semaphore:
            prepared = await asyncio.to_thread(
                prepare_segment_visual_assets,
                briefings[segment],
                **prepared_kwargs,
            )
        segment_asset_paths: list[Path] = list(prepared.asset_paths)
        for path in prepared.asset_paths:
            manifest_path = manifest_path_for(path)
            if manifest_path.exists():
                segment_asset_paths.append(manifest_path)
        return _VisualPrepResult(
            segment=segment,
            briefing=prepared.briefing,
            asset_paths=tuple(segment_asset_paths),
        )

    segments = [segment for segment in SEGMENT_ORDER if segment in briefings]
    raw_results = await asyncio.gather(
        *(_prepare_one(segment) for segment in segments),
        return_exceptions=True,
    )
    results_by_segment: dict[MarketSegment, _VisualPrepResult] = {}
    for segment, raw_result in zip(segments, raw_results, strict=True):
        if isinstance(raw_result, BaseException):
            raise raw_result
        results_by_segment[segment] = raw_result

    prepared_briefings: dict[MarketSegment, Briefing] = {}
    asset_paths: list[Path] = []
    for segment in SEGMENT_ORDER:
        if segment not in results_by_segment:
            continue
        result = results_by_segment[segment]
        prepared_briefings[segment] = result.briefing
        asset_paths.extend(result.asset_paths)
    return prepared_briefings, tuple(asset_paths)


def _load_curated_runtime_safely() -> (
    tuple[
        Mapping[str, Any],
        Sequence[Any],
        Callable[[MarketSegment, Sequence[NormalizedItem], Mapping[str, Any], Sequence[Any]], Any],
    ]
    | None
):
    """Load optional u86 curated-asset hooks; fall through when not installed.

    A broken / invalid library is a *build-time* CI-gate failure
    (``scripts/check_curated_assets.py``), not a run-time crash. At
    generation time we degrade to the existing hero chain (R9 fallback).
    The import stays dynamic so a staged rollout cannot break
    ``python -m investo`` when the orchestrator lands before the curated
    module itself.
    """
    try:
        curated = importlib.import_module("investo.visuals.curated")
    except ModuleNotFoundError as exc:
        if exc.name == "investo.visuals.curated":
            _logger.info("curated asset module unavailable; falling back to existing hero chain")
            return None
        raise

    load_library = curated.load_library
    default_registry = curated.default_registry
    select_curated_asset = curated.select_curated_asset
    curated_library_error = curated.CuratedLibraryError
    try:
        curated_library = load_library()
    except curated_library_error:
        _logger.warning("curated library failed to load; falling back to existing hero chain")
        return None
    if not curated_library:
        return None
    return (curated_library, default_registry(), select_curated_asset)


def _read_existing_bytes(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()


def _rollback_paths(snapshots: dict[Path, bytes | None]) -> None:
    for path, previous_bytes in snapshots.items():
        if previous_bytes is None:
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(previous_bytes)
    _prune_empty_parent_dirs(snapshots)


def _prune_empty_parent_dirs(snapshots: dict[Path, bytes | None]) -> None:
    for path in sorted(snapshots, key=lambda item: len(item.parts), reverse=True):
        current = path.parent
        while current != current.parent:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent


async def _stage_notify_briefing(
    briefing: Briefing,
    *,
    publisher: BriefingPublisher,
    site_url: HttpUrl,
) -> SendResult:
    """Compose + dispatch the public-channel briefing notification.

    Three steps:

    1. ``build_summary(briefing, site_url=str(site_url))`` — UTF-16-aware
       composition; emits ``"📈 {target_date} 시황 요약\\n\\n{market
       summary}\\n\\n상세보기: {site_url}"`` truncated under 4096
       UTF-16 code units (Telegram's ``sendMessage`` cap).
    2. ``BriefingNotification(target_date, summary_text, site_url)`` —
       the model re-validates the UTF-16 budget at construction time
       (defense-in-depth against ``build_summary`` miscalculation).
    3. ``publisher.send(payload)`` — Telegram Bot API call. **Non-
       raising**: HTTP failures, Telegram API errors, and timeouts
       are encoded in :class:`SendResult` ``ok=False`` with a
       sanitized error message (bot tokens redacted; see
       ``investo.notifier._telegram._redact_bot_token``).

    Parameters
    ----------
    briefing:
        Validated :class:`Briefing` from ``_stage_generate``.
    publisher:
        The :class:`BriefingPublisher` instance constructed in
        ``main()`` with the public-channel ``channel_id``. Injected
        at this boundary (vs constructed here) so the orchestrator
        does not need to know the chat-ID-disjointness rule —
        ``main()`` enforces it before the dispatcher is built.
    site_url:
        ``HttpUrl`` of the archived markdown's public URL (e.g., the
        GitHub Pages URL for the day). Threaded through to both
        ``build_summary`` (string form, for the footer) and
        ``BriefingNotification`` (HttpUrl form, for the model).

    Returns
    -------
    SendResult
        ``ok=True`` with optional ``message_id`` on Telegram-confirmed
        delivery. ``ok=False`` with a sanitized ``error`` string on any
        failure. ``run_pipeline`` consults ``result.ok`` to decide
        ``PipelineStatus.PARTIAL`` (publish was ok, notify failed) vs
        ``SUCCESS`` per AC-003-6 + AC-003-8.

    Raises
    ------
    Nothing related to delivery — u4's contract is non-raising.
    Programmer errors (KeyError from a malformed ``Briefing``,
    pydantic ``ValidationError`` from a too-long summary even after
    truncation, etc.) propagate unwrapped per the FD failure
    contract; ``main()``'s top-level handler routes per AC-003-7.
    """
    _logger.info("[notify_briefing] starting target_date=%s", briefing.target_date)

    summary_text = build_summary(briefing, site_url=str(site_url))
    payload = BriefingNotification(
        target_date=briefing.target_date,
        summary_text=summary_text,
        site_url=site_url,
    )
    result = await publisher.send(payload)

    if result.ok:
        # message_id is Telegram's delivery receipt. Logging it (vs
        # leaving it unlogged) helps diagnose chat-ID misconfiguration
        # when the message lands in the wrong channel.
        _logger.info(
            "[notify_briefing] ok target_date=%s message_id=%s",
            briefing.target_date,
            result.message_id,
        )
    else:
        # Per AC-003-6: notify failure → PARTIAL pipeline status,
        # NO operator alert (PARTIAL itself is the visibility signal).
        # Logging at WARNING per AC-005-6 — the GHA log shows the
        # failure even though no alert was sent.
        _logger.warning(
            "[notify_briefing] failed target_date=%s error=%s",
            briefing.target_date,
            result.error,
        )

    return result


async def _stage_notify_segmented_briefing(
    briefings: dict[MarketSegment, Briefing],
    *,
    publisher: BriefingPublisher,
    site_urls: dict[MarketSegment, HttpUrl],
    items: Sequence[NormalizedItem] = (),
    coverage_by_segment: Mapping[MarketSegment, SegmentCoverage] | None = None,
    lookahead_items_by_segment: Mapping[MarketSegment, Sequence[NormalizedItem]] | None = None,
    now_utc: datetime | None = None,
    missing_segments: Sequence[MarketSegment] = (),
) -> SendResult:
    """Compose + dispatch one public-channel message for all segments.

    u43 / DEBT-067 M1 — clock-explicit contract. When the caller wants
    forward-looking imminent-event tags rendered into the Telegram
    summary, both ``lookahead_items_by_segment`` and ``now_utc`` must
    be supplied. The notifier never reads ``datetime.now(UTC)`` for
    the imminent-event tag; the orchestrator owns the clock so test
    fixtures can pin the rendered output deterministically. The
    notifier itself enforces the symmetric invariant
    (``ValueError`` when one is supplied without the other).
    """
    published_segments = tuple(segment for segment in SEGMENT_ORDER if segment in briefings)
    if not published_segments:
        return SendResult(ok=False, error="segmented notification requires at least one briefing")
    primary_segment = DOMESTIC_EQUITY if DOMESTIC_EQUITY in briefings else published_segments[0]
    target_date = briefings[primary_segment].target_date
    _logger.info("[notify_briefing] starting segmented target_date=%s", target_date)

    try:
        summary_text = build_segmented_summary(
            briefings,
            site_urls={segment: str(url) for segment, url in site_urls.items()},
            price_items=items,
            coverage_by_segment=coverage_by_segment,
            enabled_segments=resolve_enabled_segments(),
            lookahead_items_by_segment=lookahead_items_by_segment,
            now_utc=now_utc,
            missing_segments=missing_segments,
        )
        payload = BriefingNotification(
            target_date=target_date,
            summary_text=summary_text,
            site_url=site_urls[primary_segment],
        )
    except (ValueError, ValidationError) as exc:
        error = f"segmented summary build failed: {type(exc).__name__}: {exc}"
        _logger.warning(
            "[notify_briefing] failed segmented target_date=%s error=%s", target_date, error
        )
        return SendResult(ok=False, error=error)
    result = await publisher.send(payload)

    if result.ok:
        _logger.info(
            "[notify_briefing] ok segmented target_date=%s message_id=%s",
            target_date,
            result.message_id,
        )
    else:
        _logger.warning(
            "[notify_briefing] failed segmented target_date=%s error=%s",
            target_date,
            result.error,
        )

    return result


# ---------------------------------------------------------------------------
# run_pipeline composer
# ---------------------------------------------------------------------------


def _truncate_excerpt(text: str | None) -> str | None:
    """Truncate to the FailureContext-validator-safe limit."""
    if text is None:
        return None
    if len(text) <= TRACEBACK_EXCERPT_MAX:
        return text
    return text[:TRACEBACK_EXCERPT_MAX]


def _build_failure_context(
    *,
    stage: str,
    exc: BaseException,
) -> FailureContext:
    """Build a ``FailureContext`` from an arbitrary exception.

    ``stage`` is constrained by ``FailureStage`` Literal to one of
    ``"collect"``, ``"generate"``, ``"publish"``, ``"notify_briefing"``.
    The orchestrator only constructs alerts for the four catalogued
    stages; programmer errors at the top level are formatted by
    ``main()`` with its own context (per AC-003-7).
    """
    return FailureContext(
        stage=stage,  # orchestrator only passes the 4 catalogued FailureStage values
        error_type=type(exc).__name__,
        error_message=str(exc) or type(exc).__name__,
        traceback_excerpt=_truncate_excerpt(
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        ),
        occurred_at=datetime.now(UTC),
    )


def _briefing_url_for(
    target_date: date,
    site_url_base: HttpUrl,
    *,
    segment: MarketSegment | None = None,
) -> HttpUrl:
    """Compose the per-day archive URL from the configured base.

    ``site_url_base`` is something like
    ``https://example.github.io/investo`` (with or without a trailing
    slash). The mkdocs site exposes repo-root ``archive/`` through the
    ``site_docs/archive`` symlink, so each archived briefing renders
    under ``{base}/archive/{YYYY}/{MM}/{YYYY-MM-DD}/``. New u7
    segmented runs pass ``segment`` and render under
    ``{base}/archive/{segment}/{YYYY}/{MM}/{YYYY-MM-DD}/``. The
    default keeps historical unsegmented archive pages readable.
    """
    base = str(site_url_base).rstrip("/")
    iso = target_date.isoformat()
    segment_prefix = "" if segment is None else f"{segment}/"
    return _HTTP_URL_ADAPTER.validate_python(
        f"{base}/archive/{segment_prefix}{target_date.year}/{target_date.month:02d}/{iso}/"
    )


# ---------------------------------------------------------------------------
# u84 — Stage classes (thin wrappers around the existing stage runners +
# inline transforms) + the declarative exception-routing table + the
# composition root. ``run_pipeline`` (below) drives these via a sequencing
# + error-routing loop instead of an inline try/except cascade.
#
# Behaviour-preserving discipline: each stage reproduces the exact phase
# logic that previously lived inline in ``run_pipeline``. Stage outputs
# flow via ``StageResult.data`` (accumulated by the loop); the frozen
# ``PipelineContext`` carries inputs only. The five catalogued routable
# failures are reported by returning ``StageResult(status="failed",
# error=exc)``; the loop maps the exception type through
# :data:`EXCEPTION_ROUTING` to the operator-alert ``stage`` label + the
# resulting :class:`PipelineStatus` (exactly the prior arms).
# ---------------------------------------------------------------------------


class CollectStage:
    """u1 source aggregation. ``EmptyCollectError`` → routable failure."""

    name = "collect"

    async def execute(
        self,
        ctx: PipelineContext,
        accumulated: dict[str, object],
    ) -> StageResult[dict[str, object]]:
        fetch = cast("CollectCallable | None", ctx.fetch)
        start = time.monotonic()
        try:
            items, source_outcomes = await _stage_collect(ctx.target_date, fetch=fetch)
        except EmptyCollectError as exc:
            return StageResult(
                status="failed",
                error=exc,
                stage_notes={
                    "collect": "failed: empty",
                    "generate": "skipped",
                    "publish": "skipped",
                    "notify_briefing": "skipped",
                },
                timings={"collect": time.monotonic() - start},
            )
        return StageResult(
            status="ok",
            data={"items": items, "source_outcomes": source_outcomes},
            stage_notes={"collect": "ok"},
            timings={"collect": time.monotonic() - start},
        )


class GenerateStage:
    """u2 synthesis + (segmented) the pre-publish transform chain.

    Carries the segmented context loaders, the visual-asset preparation,
    the deterministic carryover / anchor-reconcile / chart-block / reader-
    format passes that ran inline between generate and publish. Routable
    failures: ``BriefingGenerationError`` (→ generate label), and the
    reader-format gate's ``ComplianceLanguageError`` /
    ``NumericAnchorReconciliationError`` (→ publish label, preserving the
    prior ``stage_timings["publish"]=0.0`` marker).
    """

    name = "generate"

    async def execute(
        self,
        ctx: PipelineContext,
        accumulated: dict[str, object],
    ) -> StageResult[dict[str, object]]:
        target_date = ctx.target_date
        runner = cast("ClaudeRunner | None", ctx.runner)
        generate = cast("GenerateCallable | None", ctx.generate)
        generate_segment = cast("SegmentGenerateCallable | None", ctx.generate_segment)
        items = cast("list[NormalizedItem]", accumulated["items"])
        source_outcomes = cast("tuple[SourceOutcome, ...]", accumulated["source_outcomes"])

        start = time.monotonic()
        segmented_mode = generate is None
        segment_generation_failures: dict[MarketSegment, BriefingGenerationError] = {}
        surface_quality_failures: dict[MarketSegment, SurfaceQualityError] = {}
        entity_fact_blocked_segments: tuple[MarketSegment, ...] = ()
        market_history_by_ticker: dict[str, tuple[OHLCRow, ...]] = {}
        market_anchors_by_segment: dict[MarketSegment, tuple[MarketAnchor, ...]] = {
            segment: () for segment in SEGMENT_ORDER
        }
        run_bundle_context: BundleContext | None = None
        carryover_by_segment: dict[MarketSegment, BriefingCarryover] = {}
        segment_briefings: dict[MarketSegment, Briefing] | None = None
        fact_bundle: VerifiedFactBundle | None = None
        macro_lineage_by_segment: Mapping[MarketSegment, Sequence[MacroLineageTrace]] = {}
        generate_sub_timings: dict[str, float] = {}
        try:
            if segmented_mode:
                context_start = time.monotonic()
                recent_context = _load_recent_context_for_run(target_date)
                (
                    market_anchors_by_segment,
                    market_history_by_ticker,
                ) = await _load_market_anchors_for_run(target_date)
                # u67 — fold deterministic KR index-close + 원/달러 anchors
                # (from the stooq-kr-market snapshot items) into the domestic
                # segment. Yahoo history cannot supply these (429 on GHA), so
                # they are synthesized close-only from the collected items.
                kr_anchors = _build_kr_anchors_from_items(
                    items,
                    target_date=target_date,
                    source_outcomes=source_outcomes,
                )
                if kr_anchors:
                    existing = market_anchors_by_segment.get(DOMESTIC_EQUITY, ())
                    seen = {a.ticker for a in existing}
                    merged = (*existing, *(a for a in kr_anchors if a.ticker not in seen))
                    market_anchors_by_segment[DOMESTIC_EQUITY] = merged
                # u52 — build per-segment carryover bundles from prior ≤3
                # trading-day archives. Each segment receives only its own
                # routed candidates so resolution matching stays
                # source-scoped.
                routed_candidates = segment_items(items)
                candidates_by_segment: dict[MarketSegment, tuple[NormalizedItem, ...]] = {
                    segment: routed_candidates.for_segment(segment) for segment in SEGMENT_ORDER
                }
                carryover_by_segment = _load_carryover_for_run(target_date, candidates_by_segment)
                # u59 — advance + persist the operator-only macro lifecycle
                # carryover snapshot from the collected/routed items. Pure
                # transition; persistence failures degrade gracefully.
                _advance_and_persist_macro_carryover(
                    target_date,
                    items,
                    routed_candidates,
                )
                generate_sub_timings["generate:context"] = time.monotonic() - context_start
                (
                    segment_briefings,
                    segment_generation_failures,
                    run_bundle_context,
                    fact_bundle,
                    macro_lineage_by_segment,
                    segment_timings,
                ) = await _stage_generate_segments(
                    target_date,
                    items,
                    runner=runner,
                    generate_segment=generate_segment,
                    source_outcomes=source_outcomes,
                    recent_context=recent_context,
                    market_anchors_by_segment=market_anchors_by_segment,
                    carryover_by_segment=carryover_by_segment,
                )
                generate_sub_timings.update(segment_timings)
                primary_generated_segment = (
                    DOMESTIC_EQUITY
                    if DOMESTIC_EQUITY in segment_briefings
                    else next(iter(segment_briefings))
                )
                briefing = segment_briefings[primary_generated_segment]
            else:
                segment_briefings = None
                run_bundle_context = None
                fact_bundle = None
                macro_lineage_by_segment = {}
                briefing = await _stage_generate(
                    target_date, items, runner=runner, generate=generate
                )
        except BriefingGenerationError as exc:
            _log_briefing_generation_error(exc)
            return StageResult(
                status="failed",
                error=exc,
                stage_notes={
                    "generate": f"failed: {exc.stage}",
                    "publish": "skipped",
                    "notify_briefing": "skipped",
                },
                timings={"generate": time.monotonic() - start},
            )
        generate_elapsed = time.monotonic() - start

        stage_notes: dict[str, str] = {}
        stage_alerts: list[BriefingGenerationError] = []
        if segment_generation_failures:
            failed_segments = ", ".join(segment_generation_failures)
            stage_notes["generate"] = f"partial: failed {failed_segments}"
            for segment, generation_error in segment_generation_failures.items():
                _log_briefing_generation_error(generation_error)
                stage_alerts.append(generation_error)
                stage_notes[f"generate:{segment}"] = f"failed: {generation_error.stage}"
        else:
            stage_notes["generate"] = "ok"

        visual_assets_failed = False
        visual_asset_paths: tuple[Path, ...] = ()

        if segmented_mode:
            assert segment_briefings is not None
            va_start = time.monotonic()
            try:
                segment_briefings, visual_asset_paths = await _stage_prepare_segment_visual_assets(
                    segment_briefings,
                    items,
                    target_date,
                    source_outcomes=source_outcomes,
                )
            except VisualAssetError as exc:
                visual_assets_failed = True
                visual_asset_paths = ()
                stage_notes["visual_assets"] = f"failed: {type(exc).__name__}"
                _logger.warning(
                    "[visual_assets] failed target_date=%s error=%s; publishing text-only",
                    target_date,
                    exc,
                )
                va_elapsed = time.monotonic() - va_start
            else:
                stage_notes["visual_assets"] = f"ok: {len(visual_asset_paths)} files"
                va_elapsed = time.monotonic() - va_start

            # u52 — inject the deterministic Watchlist Carryover block.
            segment_briefings = _inject_carryover_into_segments(
                segment_briefings,
                carryover_by_segment=carryover_by_segment,
            )

            # u70 — derive the SINGLE canonical anchor payload before any
            # reader surface renders.
            anchor_table_input = _reconcile_anchor_closes(
                market_anchors_by_segment,
                _snapshot_close_by_ticker(items),
            )

            # u50 — inject the per-segment chart placeholder block.
            segment_briefings, chart_sidecar_paths = _inject_chart_blocks_into_segments(
                segment_briefings,
                target_date=target_date,
                anchors_by_segment=anchor_table_input,
                history_by_ticker=market_history_by_ticker,
            )
            if chart_sidecar_paths:
                visual_asset_paths = (*visual_asset_paths, *chart_sidecar_paths)

            # u51 / u56 — reader-format chain (incl. the compliance gate).
            # A P0 hit raises ``ComplianceLanguageError`` here and an
            # un-rewritable anchor contradiction raises
            # ``NumericAnchorReconciliationError``; both route to the
            # publish label (preserving ``stage_timings["publish"]=0.0``).
            reader_format_start = time.monotonic()
            try:
                _routed_for_indicators = segment_items(items)
                items_by_segment = {
                    seg: _routed_for_indicators.for_segment(seg) for seg in SEGMENT_ORDER
                }
                while True:
                    reader_bundle_context = (
                        redecide_daily_thesis_for_successful_segments(
                            run_bundle_context,
                            tuple(segment_briefings),
                        )
                        if run_bundle_context is not None
                        else None
                    )
                    try:
                        segment_briefings = _apply_reader_format_to_segments(
                            segment_briefings,
                            anchors_by_segment=anchor_table_input,
                            bundle_context=reader_bundle_context,
                            items_by_segment=items_by_segment,
                        )
                        break
                    except SurfaceQualityError as exc:
                        failed_segment = cast(MarketSegment, exc.segment)
                        if failed_segment not in segment_briefings:
                            raise
                        surface_quality_failures[failed_segment] = exc
                        segment_briefings = {
                            segment: briefing
                            for segment, briefing in segment_briefings.items()
                            if segment != failed_segment
                        }
                        stage_notes[f"publish:{failed_segment}"] = "failed: SurfaceQualityError"
                        _logger.error(
                            "[publish] surface quality blocked segment=%s; "
                            "issues=%s continuing with %d remaining segment(s)",
                            failed_segment,
                            [
                                {
                                    "code": issue.code,
                                    "region": issue.region,
                                    "evidence_len": len(issue.evidence),
                                }
                                for issue in exc.issues
                            ],
                            len(segment_briefings),
                        )
                        if not segment_briefings:
                            reader_format_elapsed = time.monotonic() - reader_format_start
                            stage_notes["publish"] = "failed: SurfaceQualityError"
                            stage_notes["notify_briefing"] = "skipped"
                            return StageResult(
                                status="failed",
                                error=exc,
                                stage_notes=stage_notes,
                                timings={
                                    "generate": generate_elapsed,
                                    **generate_sub_timings,
                                    "visual_assets": va_elapsed,
                                    "generate:reader_format": reader_format_elapsed,
                                    "publish": 0.0,
                                },
                                data={"_stage_alerts": stage_alerts},
                            )
            except (ComplianceLanguageError, NumericAnchorReconciliationError) as exc:
                reader_format_elapsed = time.monotonic() - reader_format_start
                _logger.error(
                    "[publish] failed during reader-format target_date=%s error_type=%s error=%s",
                    target_date,
                    type(exc).__name__,
                    exc,
                )
                stage_notes["publish"] = f"failed: {type(exc).__name__}"
                stage_notes["notify_briefing"] = "skipped"
                return StageResult(
                    status="failed",
                    error=exc,
                    stage_notes=stage_notes,
                    timings={
                        "generate": generate_elapsed,
                        **generate_sub_timings,
                        "visual_assets": va_elapsed,
                        "generate:reader_format": reader_format_elapsed,
                        "publish": 0.0,
                    },
                    data={"_stage_alerts": stage_alerts},
                )
            reader_format_elapsed = time.monotonic() - reader_format_start
            assert fact_bundle is not None
            segment_briefings, entity_fact_blocked_segments = _filter_entity_fact_violations(
                segment_briefings,
                fact_bundle=fact_bundle,
                target_date=target_date,
                now_utc=datetime.now(UTC),
            )
            for blocked_segment in entity_fact_blocked_segments:
                stage_notes[f"publish:{blocked_segment}"] = "failed: EntityFactGuard"
            if entity_fact_blocked_segments and not segment_briefings:
                entity_error = PublisherDisclaimerError(target_date=target_date)
                stage_notes["publish"] = "failed: EntityFactGuard"
                stage_notes["notify_briefing"] = "skipped"
                return StageResult(
                    status="failed",
                    error=entity_error,
                    stage_notes=stage_notes,
                    timings={
                        "generate": generate_elapsed,
                        **generate_sub_timings,
                        "visual_assets": va_elapsed,
                        "generate:reader_format": reader_format_elapsed,
                        "publish": 0.0,
                    },
                    data={"_stage_alerts": stage_alerts},
                )

            timings = {
                "generate": generate_elapsed,
                **generate_sub_timings,
                "visual_assets": va_elapsed,
                "generate:reader_format": reader_format_elapsed,
            }
        else:
            timings = {"generate": generate_elapsed}

        return StageResult(
            status=(
                "partial"
                if segment_generation_failures
                or surface_quality_failures
                or entity_fact_blocked_segments
                else "ok"
            ),
            data={
                "segmented_mode": segmented_mode,
                "briefing": briefing,
                "segment_briefings": segment_briefings,
                "segment_generation_failures": segment_generation_failures,
                "surface_quality_failures": surface_quality_failures,
                "entity_fact_blocked_segments": entity_fact_blocked_segments,
                "visual_assets_failed": visual_assets_failed,
                "visual_asset_paths": visual_asset_paths,
                "fact_bundle": fact_bundle,
                "macro_lineage_by_segment": macro_lineage_by_segment,
                "_stage_alerts": stage_alerts,
            },
            stage_notes=stage_notes,
            timings=timings,
        )


class PublishStage:
    """u3 atomic write + git lifecycle (segmented or unsegmented)."""

    name = "publish"

    async def execute(
        self,
        ctx: PipelineContext,
        accumulated: dict[str, object],
    ) -> StageResult[dict[str, object]]:
        target_date = ctx.target_date
        git_runner = cast("GitRunner | None", ctx.git_runner)
        segmented_mode = cast("bool", accumulated["segmented_mode"])
        items = cast("list[NormalizedItem]", accumulated["items"])
        source_outcomes = cast("tuple[SourceOutcome, ...]", accumulated["source_outcomes"])
        segment_briefings = cast(
            "dict[MarketSegment, Briefing] | None", accumulated["segment_briefings"]
        )
        briefing = cast("Briefing", accumulated["briefing"])
        macro_lineage_by_segment = cast(
            "Mapping[MarketSegment, Sequence[MacroLineageTrace]]",
            accumulated["macro_lineage_by_segment"],
        )
        fact_bundle = cast("VerifiedFactBundle | None", accumulated.get("fact_bundle"))
        visual_asset_paths = cast("tuple[Path, ...]", accumulated["visual_asset_paths"])

        start = time.monotonic()
        try:
            if segmented_mode:
                assert segment_briefings is not None
                await _stage_publish_segments(
                    segment_briefings,
                    target_date,
                    asset_paths=visual_asset_paths,
                    git_runner=git_runner,
                    items=items,
                    source_outcomes=source_outcomes,
                    macro_lineage_by_segment=macro_lineage_by_segment,
                    fact_bundle=fact_bundle,
                )
            else:
                await _stage_publish(briefing, target_date, git_runner=git_runner)
        except _PUBLISH_FAILURES as exc:
            _logger.error(
                "[publish] failed target_date=%s error_type=%s error=%s",
                target_date,
                type(exc).__name__,
                exc,
            )
            return StageResult(
                status="failed",
                error=exc,
                stage_notes={
                    "publish": f"failed: {type(exc).__name__}",
                    "notify_briefing": "skipped",
                },
                timings={"publish": time.monotonic() - start},
            )
        return StageResult(
            status="ok",
            stage_notes={"publish": "ok"},
            timings={"publish": time.monotonic() - start},
        )


class NotifyStage:
    """u4 public-channel dispatch. Non-raising — encodes failure in data."""

    name = "notify_briefing"

    async def execute(
        self,
        ctx: PipelineContext,
        accumulated: dict[str, object],
    ) -> StageResult[dict[str, object]]:
        target_date = ctx.target_date
        publisher = cast("BriefingPublisher", accumulated["publisher"])
        segmented_mode = cast("bool", accumulated["segmented_mode"])
        items = cast("list[NormalizedItem]", accumulated["items"])
        source_outcomes = cast("tuple[SourceOutcome, ...]", accumulated["source_outcomes"])
        segment_briefings = cast(
            "dict[MarketSegment, Briefing] | None", accumulated["segment_briefings"]
        )
        briefing = cast("Briefing", accumulated["briefing"])
        segment_generation_failures = cast(
            "dict[MarketSegment, BriefingGenerationError]",
            accumulated["segment_generation_failures"],
        )
        surface_quality_failures = cast(
            "dict[MarketSegment, SurfaceQualityError]",
            accumulated.get("surface_quality_failures", {}),
        )
        entity_fact_blocked_segments = cast(
            "tuple[MarketSegment, ...]",
            accumulated.get("entity_fact_blocked_segments", ()),
        )

        primary_segment = (
            DOMESTIC_EQUITY
            if segmented_mode
            and segment_briefings is not None
            and DOMESTIC_EQUITY in segment_briefings
            else next(iter(segment_briefings), None)
            if segmented_mode and segment_briefings is not None
            else None
        )
        briefing_url = _briefing_url_for(
            target_date,
            ctx.site_url_base,
            segment=primary_segment if segmented_mode else None,
        )
        segment_urls = (
            {
                segment: _briefing_url_for(target_date, ctx.site_url_base, segment=segment)
                for segment in SEGMENT_ORDER
            }
            if segmented_mode
            else None
        )

        start = time.monotonic()
        if segmented_mode:
            assert segment_briefings is not None
            assert segment_urls is not None
            routed_items_for_alert = segment_items(items)
            coverage_by_segment = {
                segment: routed_items_for_alert.coverage_for_segment(
                    segment,
                    source_outcomes=source_outcomes,
                )
                for segment in segment_briefings
            }
            notify_now_utc = datetime.now(UTC)
            lookahead_items_by_segment: dict[MarketSegment, tuple[NormalizedItem, ...]] = {
                segment: filter_lookahead_items(routed_items_for_alert.for_segment(segment))
                for segment in segment_briefings
            }
            notify_result = await _stage_notify_segmented_briefing(
                segment_briefings,
                publisher=publisher,
                site_urls=segment_urls,
                items=trusted_domestic_price_items(
                    items,
                    target_date=target_date,
                    source_outcomes=source_outcomes,
                ),
                coverage_by_segment=coverage_by_segment,
                lookahead_items_by_segment=lookahead_items_by_segment,
                now_utc=notify_now_utc,
                missing_segments=tuple(
                    segment
                    for segment in SEGMENT_ORDER
                    if segment in segment_generation_failures
                    or segment in surface_quality_failures
                    or segment in entity_fact_blocked_segments
                ),
            )
        else:
            notify_result = await _stage_notify_briefing(
                briefing, publisher=publisher, site_url=briefing_url
            )
        return StageResult(
            status="ok" if notify_result.ok else "partial",
            data={"notify_result": notify_result, "briefing_url": briefing_url},
            timings={"notify_briefing": time.monotonic() - start},
        )


class HealthTrackingStage:
    """u31 per-source coverage append + consecutive-failure soft alert.

    Best-effort: any failure is swallowed (logged) so it never changes the
    pipeline's exit semantics. Always reports ``ok``; the soft alert is
    requested via ``data`` (the loop dispatches it through ``_safe_alert``).
    """

    name = "health"

    async def execute(
        self,
        ctx: PipelineContext,
        accumulated: dict[str, object],
    ) -> StageResult[dict[str, object]]:
        target_date = ctx.target_date
        segmented_mode = cast("bool", accumulated["segmented_mode"])
        items = cast("list[NormalizedItem]", accumulated["items"])
        source_outcomes = cast("tuple[SourceOutcome, ...]", accumulated["source_outcomes"])
        segment_briefings = cast(
            "dict[MarketSegment, Briefing] | None", accumulated["segment_briefings"]
        )
        soft_alert: RuntimeError | None = None
        try:
            severities_for_coverage: dict[str, str] = {}
            if segmented_mode and segment_briefings is not None:
                severity_segmented = segment_items(items)
                for segment in segment_briefings:
                    severities_for_coverage[segment] = severity_segmented.coverage_for_segment(
                        segment, source_outcomes=source_outcomes
                    ).status
            source_health.append_daily_coverage(
                target_date,
                source_outcomes,
                severities=severities_for_coverage or None,
            )
            consecutive_failed = source_health.detect_consecutive_failed(today=target_date)
            if consecutive_failed:
                _logger.warning(
                    "[source_health] sources failed for %d consecutive days: %s",
                    source_health.DEFAULT_CONSECUTIVE_THRESHOLD,
                    ", ".join(consecutive_failed),
                )
                soft_alert = RuntimeError(
                    f"sources failed {source_health.DEFAULT_CONSECUTIVE_THRESHOLD} "
                    f"consecutive days: {', '.join(consecutive_failed)}"
                )
        except Exception as exc:
            _logger.warning("[source_health] could not record coverage log: %s", exc)
        return StageResult(status="ok", data={"_soft_alert": soft_alert})


# Publish-stage routable failures — the exact prior tuple (the reader-
# format gate's ``ComplianceLanguageError`` / ``NumericAnchorReconciliation
# Error`` are caught inside ``GenerateStage`` and routed to the publish
# label via :data:`EXCEPTION_ROUTING`).
_PUBLISH_FAILURES: Final = (
    SummaryQualityError,
    ComplianceLanguageError,
    PublisherDisclaimerError,
    PublisherIOError,
    PublisherGitError,
    SurfaceQualityError,
    QualityConsistencyError,
    QualityHistoryError,
    ForecastLogError,
)


# Declarative exception → (alert / status) routing table. The single
# change-point for "which failure means what" — new failure types extend
# this table, not the loop (guide §4). Keyed by exception TYPE.
EXCEPTION_ROUTING: dict[type[BaseException], StageAction] = {
    EmptyCollectError: StageAction(stage="collect", alert=True, status=PipelineStatus.FAILED),
    BriefingGenerationError: StageAction(
        stage="generate", alert=True, status=PipelineStatus.FAILED
    ),
    SummaryQualityError: StageAction(stage="publish", alert=True, status=PipelineStatus.FAILED),
    ComplianceLanguageError: StageAction(stage="publish", alert=True, status=PipelineStatus.FAILED),
    NumericAnchorReconciliationError: StageAction(
        stage="publish", alert=True, status=PipelineStatus.FAILED
    ),
    PublisherDisclaimerError: StageAction(
        stage="publish", alert=True, status=PipelineStatus.FAILED
    ),
    PublisherIOError: StageAction(stage="publish", alert=True, status=PipelineStatus.FAILED),
    PublisherGitError: StageAction(stage="publish", alert=True, status=PipelineStatus.FAILED),
    SurfaceQualityError: StageAction(stage="publish", alert=True, status=PipelineStatus.FAILED),
    QualityConsistencyError: StageAction(stage="publish", alert=True, status=PipelineStatus.FAILED),
    QualityHistoryError: StageAction(stage="publish", alert=True, status=PipelineStatus.FAILED),
    ForecastLogError: StageAction(stage="publish", alert=True, status=PipelineStatus.FAILED),
}


def _route_failure(exc: Exception) -> StageAction:
    """Resolve the routing action for a routable stage failure.

    Looks the exception type up in :data:`EXCEPTION_ROUTING` (exact type
    first, then by MRO so a subclass of a catalogued failure still routes).
    A miss is a programmer error — the loop never reaches here for an
    uncatalogued type because stages only set ``error`` for catalogued ones.
    """
    action = EXCEPTION_ROUTING.get(type(exc))
    if action is not None:
        return action
    for exc_type, candidate in EXCEPTION_ROUTING.items():
        if isinstance(exc, exc_type):
            return candidate
    raise KeyError(f"no routing for {type(exc).__name__}")


def build_default_stages() -> tuple[Stage, ...]:
    """Composition root — assemble the production stage sequence.

    Returned as a tuple of :class:`Stage` instances and injected into
    :func:`run_pipeline` so stages are not instantiated inline (DIP). Tests
    may build their own sequence and pass it via ``stages=``.
    """
    sequence: tuple[Stage, ...] = (
        CollectStage(),
        GenerateStage(),
        PublishStage(),
        NotifyStage(),
        HealthTrackingStage(),
    )
    return sequence


async def run_pipeline(
    target_date: date | None = None,
    *,
    publisher: BriefingPublisher,
    alerter: OperatorAlerter,
    site_url_base: HttpUrl,
    fetch: CollectCallable | None = None,
    runner: ClaudeRunner | None = None,
    git_runner: GitRunner | None = None,
    generate: GenerateCallable | None = None,
    generate_segment: SegmentGenerateCallable | None = None,
    stages: tuple[Stage, ...] | None = None,
) -> PipelineResult:
    """Run the four-stage pipeline under Q9=B Error Policy routing.

    The composer is **non-raising** for the four catalogued stage
    failures: each is converted into a :class:`FailureContext` and
    routed to ``alerter.alert(...)`` (best-effort), then encoded in
    the returned :class:`PipelineResult`. Programmer errors (anything
    not in the explicit catch list — ``KeyError``, ``RuntimeError``,
    pydantic ``ValidationError``, etc.) propagate to ``main()`` per
    AC-003-7.

    Per Q1=A there is **no** stage-level ``asyncio.wait_for``: each
    unit owns its own timeout. Per Q5 stages are sequential (no
    ``asyncio.gather``). Per Q4=A there is **no** orchestrator-level
    retry; unit-level retry is the only retry budget.

    Parameters
    ----------
    target_date:
        When ``None`` (production cron path), resolved via
        :func:`investo.orchestrator.date_resolution.resolve_target_date`
        from ``datetime.now(UTC)``. Tests pass an explicit date for
        determinism.
    publisher, alerter:
        Constructed in :func:`investo.orchestrator.main` from the
        validated env vars (chat-ID disjointness already enforced
        before construction per CLAUDE.md #5).
    site_url_base:
        Base ``HttpUrl`` of the public mkdocs site (e.g.
        ``https://murphygo.github.io/investo``). The per-day URL
        ``{base}/{YYYY}/{MM}/{YYYY-MM-DD}/`` is computed once and
        threaded into both ``_stage_notify_briefing`` and the
        :class:`PipelineResult`'s ``briefing_url`` field.
    fetch / runner / git_runner / generate:
        DI seams forwarded into the matching stage runner. Production
        passes them all as ``None`` (so each stage uses its real
        production binding); tests inject fakes.

    Returns
    -------
    PipelineResult
        ``status`` ∈ {SUCCESS, PARTIAL, FAILED}; ``stages`` carries
        the human-readable per-stage status; ``stage_timings`` carries
        the wall-clock per-stage seconds; ``duration_seconds`` is the
        total run wall-clock; ``briefing_url`` is the per-day archive
        URL on SUCCESS / PARTIAL, ``None`` on FAILED.
    """
    if target_date is None:
        target_date = resolve_target_date(datetime.now(UTC))
    target_date = validate_target_date_sanity(target_date)

    if stages is None:
        stages = build_default_stages()

    pipeline_start = time.monotonic()
    ctx = PipelineContext(
        target_date=target_date,
        site_url_base=site_url_base,
        fetch=fetch,
        runner=runner,
        git_runner=git_runner,
        generate=generate,
        generate_segment=generate_segment,
    )
    stage_status: dict[str, str] = {}
    stage_timings: dict[str, float] = {}
    # The loop's own accumulator — stage outputs flow here (NOT into the
    # frozen ``ctx``). ``publisher`` is an input the notify stage needs but
    # is not a DI seam threaded through ``PipelineContext``; it is placed
    # here so stages read it uniformly from the accumulator.
    accumulated: dict[str, object] = {"publisher": publisher}

    _logger.info("[pipeline] starting target_date=%s", target_date)

    failed_status: PipelineStatus | None = None
    status: PipelineStatus = PipelineStatus.SUCCESS
    briefing_url: HttpUrl | None = None
    for stage in stages:
        result = await stage.execute(ctx, accumulated)
        stage_status.update(result.stage_notes)
        stage_timings.update(result.timings)

        # Per-segment generate alerts fire as the generate stage reports
        # them — before any later (publish / notify) alert — preserving the
        # historical ``alerter.calls`` ordering.
        if result.data is not None:
            for generation_error in cast(
                "list[BriefingGenerationError]", result.data.get("_stage_alerts", [])
            ):
                await _safe_alert(alerter, "generate", generation_error)
            accumulated.update({k: v for k, v in result.data.items() if not k.startswith("_")})

        if result.status == "failed":
            assert result.error is not None
            action = _route_failure(result.error)
            if action.alert:
                await _safe_alert(alerter, action.stage, result.error)
            failed_status = action.status
            break

        # AC-003-6 / AC-003-8 — notify is non-raising: a delivery failure is
        # PARTIAL + an operator alert; otherwise a visual-asset failure or a
        # per-segment generate failure is PARTIAL with no extra alert (the
        # per-segment generate alerts already fired above). The reconciliation
        # runs inside the loop (before the best-effort health soft alert) so
        # the ``alerter.calls`` ordering matches the pre-refactor pipeline.
        if stage.name == "notify_briefing":
            notify_result = cast("SendResult", accumulated["notify_result"])
            briefing_url = cast("HttpUrl", accumulated["briefing_url"])
            visual_assets_failed = cast("bool", accumulated["visual_assets_failed"])
            segment_generation_failures = cast(
                "dict[MarketSegment, BriefingGenerationError]",
                accumulated["segment_generation_failures"],
            )
            surface_quality_failures = cast(
                "dict[MarketSegment, SurfaceQualityError]",
                accumulated.get("surface_quality_failures", {}),
            )
            if notify_result.ok:
                stage_status["notify_briefing"] = "ok"
                status = (
                    PipelineStatus.PARTIAL
                    if (
                        visual_assets_failed
                        or bool(segment_generation_failures)
                        or bool(surface_quality_failures)
                    )
                    else PipelineStatus.SUCCESS
                )
            else:
                stage_status["notify_briefing"] = f"failed: {notify_result.error}"
                status = PipelineStatus.PARTIAL
                await _safe_alert(
                    alerter,
                    "notify_briefing",
                    NotifyDeliveryError(
                        notify_result.error or "public briefing notification failed"
                    ),
                )

        # Soft (best-effort) alert requested by the health stage.
        if result.data is not None:
            soft_alert = cast("RuntimeError | None", result.data.get("_soft_alert"))
            if soft_alert is not None:
                await _safe_alert(alerter, "orchestrator", soft_alert)

    source_outcomes = cast("tuple[SourceOutcome, ...]", accumulated.get("source_outcomes", ()))

    if failed_status is not None:
        return _build_result(
            target_date=target_date,
            status=failed_status,
            stages=stage_status,
            stage_timings=stage_timings,
            pipeline_start=pipeline_start,
            briefing_url=None,
            source_outcomes=source_outcomes,
        )

    return _build_result(
        target_date=target_date,
        status=status,
        stages=stage_status,
        stage_timings=stage_timings,
        pipeline_start=pipeline_start,
        briefing_url=briefing_url,
        source_outcomes=source_outcomes,
    )


async def _safe_alert(
    alerter: OperatorAlerter,
    stage: str,
    exc: BaseException,
) -> None:
    """Best-effort operator alert.

    Per AC-003-10 a delivery failure during a FAILED run does NOT
    change the pipeline status (already FAILED). The alert failure
    is logged at WARNING but the pipeline still returns FAILED.
    """
    ctx = _build_failure_context(stage=stage, exc=exc)
    for attempt in range(1, _ALERT_DELIVERY_ATTEMPTS + 1):
        try:
            result = await alerter.alert(ctx)
        except Exception as alert_exc:
            # Alerter contract is non-raising for transport errors, but a
            # broken alerter (test stub bug, programmer error,
            # ``httpx.HTTPError`` leaked from a future u4 change,
            # ``asyncio.TimeoutError`` from a misconfigured client, pydantic
            # ``ValidationError`` constructing the response) should not
            # mask the underlying stage failure. Catch ``Exception`` to
            # honor the documented intent — KeyboardInterrupt /
            # SystemExit / asyncio.CancelledError (BaseException) still
            # propagate so an operator's Ctrl-C is not swallowed.
            if attempt == _ALERT_DELIVERY_ATTEMPTS:
                _logger.warning(
                    "[pipeline] alert raised unexpected %s during %s failure after %s attempts: %s",
                    type(alert_exc).__name__,
                    stage,
                    attempt,
                    alert_exc,
                )
            continue
        if result.ok:
            return
        if attempt == _ALERT_DELIVERY_ATTEMPTS:
            _logger.warning(
                "[pipeline] alert delivery failed during %s failure after %s attempts: %s",
                stage,
                attempt,
                result.error,
            )


def _build_result(
    *,
    target_date: date,
    status: PipelineStatus,
    stages: dict[str, str],
    stage_timings: dict[str, float],
    pipeline_start: float,
    briefing_url: HttpUrl | None,
    source_outcomes: Sequence[SourceOutcome] = (),
) -> PipelineResult:
    """Final ``PipelineResult`` constructor + closing INFO log."""
    duration = time.monotonic() - pipeline_start
    _logger.info(
        "[pipeline] complete target_date=%s status=%s duration=%.3fs",
        target_date,
        status.value,
        duration,
    )
    return PipelineResult(
        target_date=target_date,
        status=status,
        stages=stages,
        stage_timings=stage_timings,
        duration_seconds=duration,
        briefing_url=briefing_url,
        source_outcomes=tuple(source_outcomes),
    )


__all__ = [
    "NotifyDeliveryError",
    "run_pipeline",
]
