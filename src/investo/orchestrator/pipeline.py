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
import logging
import time
import traceback
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import HttpUrl, TypeAdapter, ValidationError

from investo.briefing.claude_code import ClaudeRunner
from investo.briefing.context import (
    RecentBriefingsContext,
    load_recent_briefings,
    resolve_recent_days,
)
from investo.briefing.errors import BriefingGenerationError
from investo.briefing.pipeline import GenerationPolicy
from investo.briefing.pipeline import generate_briefing as _u2_generate_briefing
from investo.briefing.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
    segment_items,
    segment_source_outcomes,
)
from investo.briefing.summary_quality import SummaryQualityError, validate_first_viewport_summary
from investo.briefing.watchlist import load_watchlist, match_watchlist_items
from investo.models import (
    Briefing,
    BriefingNotification,
    FailureContext,
    NormalizedItem,
    PipelineResult,
    PipelineStatus,
    SendResult,
    SourceOutcome,
)
from investo.models.results import TRACEBACK_EXCERPT_MAX
from investo.notifier import (
    BriefingPublisher,
    OperatorAlerter,
    build_segmented_summary,
    build_summary,
)
from investo.orchestrator.date_resolution import resolve_target_date, validate_target_date_sanity
from investo.orchestrator.errors import EmptyCollectError
from investo.publisher import (
    GitRunner,
    PublisherDisclaimerError,
    PublisherGitError,
    PublisherIOError,
    commit_and_push,
    publish_weekly_digest,
    update_weekly_index,
    verify_disclaimer,
    weekly_digest_opt_in,
    write_briefing,
)
from investo.publisher import (
    archive_path as compute_archive_path,
)
from investo.publisher.site_index import (
    ARCHIVE_INDEX_PATH,
    SEGMENT_ARCHIVE_INDEX_PATHS,
    SITE_INDEX_PATH,
    update_latest_index_pages,
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
from investo.visuals.og_card import OG_CARD_RELATIVE_PATH, write_og_card

# Single ``HttpUrl`` adapter — pydantic v2 doesn't expose ``HttpUrl``
# as directly callable; the TypeAdapter avoids constructing a fresh
# adapter per pipeline run.
_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)

_logger = logging.getLogger("investo.orchestrator.pipeline")
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
    ],
    Awaitable[Briefing],
]
SEGMENT_ORDER: tuple[MarketSegment, MarketSegment, MarketSegment] = (
    DOMESTIC_EQUITY,
    US_EQUITY,
    CRYPTO,
)
SEGMENT_GENERATION_POLICIES: dict[MarketSegment, GenerationPolicy] = {
    DOMESTIC_EQUITY: GenerationPolicy(timeout_s=150.0, max_attempts=2, total_budget_s=330.0),
    US_EQUITY: GenerationPolicy(timeout_s=150.0, max_attempts=2, total_budget_s=330.0),
    CRYPTO: GenerationPolicy(timeout_s=180.0, max_attempts=2, total_budget_s=390.0),
}


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
    return await _u2_generate_briefing(target_date, items, runner=runner)


async def _default_generate_segment_briefing(
    target_date: date,
    items: Sequence[NormalizedItem],
    runner: ClaudeRunner | None,
    segment: MarketSegment,
    data_limited: bool,
    source_outcomes: Sequence[SourceOutcome],
    recent_context: RecentBriefingsContext | None,
) -> Briefing:
    """Adapter for u7 segmented generation."""
    return await _u2_generate_briefing(
        target_date,
        items,
        runner=runner,
        segment=segment,
        data_limited=data_limited,
        source_outcomes=source_outcomes,
        recent_context=recent_context,
        generation_policy=SEGMENT_GENERATION_POLICIES[segment],
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


async def _stage_generate_segments(
    target_date: date,
    items: Sequence[NormalizedItem],
    *,
    runner: ClaudeRunner | None = None,
    generate_segment: SegmentGenerateCallable | None = None,
    source_outcomes: Sequence[SourceOutcome] = (),
    recent_context: RecentBriefingsContext | None = None,
) -> tuple[dict[MarketSegment, Briefing], dict[MarketSegment, BriefingGenerationError]]:
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
    runner_callable = (
        generate_segment if generate_segment is not None else _default_generate_segment_briefing
    )
    routed = segment_items(items)
    briefings: dict[MarketSegment, Briefing] = {}
    failures: dict[MarketSegment, BriefingGenerationError] = {}

    _logger.info("[generate] starting segmented target_date=%s items=%d", target_date, len(items))
    for segment in SEGMENT_ORDER:
        segment_source_items = routed.for_segment(segment)
        data_limited = routed.is_data_limited(segment)
        segment_outcomes = segment_source_outcomes(segment, source_outcomes)
        _logger.info(
            "[generate] segment=%s items=%d data_limited=%s outcomes=%d",
            segment,
            len(segment_source_items),
            data_limited,
            len(segment_outcomes),
        )
        try:
            briefings[segment] = await runner_callable(
                target_date,
                segment_source_items,
                runner,
                segment,
                data_limited,
                segment_outcomes,
                recent_context,
            )
        except BriefingGenerationError as exc:
            failures[segment] = exc
            _logger.warning(
                "[generate] segment failed segment=%s stage=%s attempts=%s; continuing",
                segment,
                exc.stage,
                exc.attempt_count,
            )

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
    return briefings, failures


def _log_briefing_generation_error(exc: BriefingGenerationError) -> None:
    """Log u2 failure details that are otherwise only visible in alerts."""
    cause_type = type(exc.cause).__name__ if exc.cause is not None else None
    _logger.error(
        "[generate] failed stage=%s attempts=%s cause_type=%s last_stderr=%s last_stdout=%s",
        exc.stage,
        exc.attempt_count,
        cause_type,
        exc.last_stderr,
        exc.last_stdout,
        extra={
            "briefing_stage": exc.stage,
            "attempt_count": exc.attempt_count,
            "cause_type": cause_type,
            "last_stderr": exc.last_stderr,
            "last_stdout": exc.last_stdout,
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
    await asyncio.to_thread(
        commit_and_push,
        commit_message,
        [archive_path],
        runner=git_runner,
    )
    _logger.info("[publish] committed + pushed %s", target_date)
    return archive_path


async def _stage_publish_segments(
    briefings: dict[MarketSegment, Briefing],
    target_date: date,
    *,
    asset_paths: Sequence[Path] = (),
    git_runner: GitRunner | None = None,
) -> dict[MarketSegment, Path]:
    """Write all segment archive files, then commit/push them together.

    The set is best-effort atomic before git commit: all disclaimers are
    validated up front, and any write failure rolls back files already
    written in this stage to their prior bytes or absence.
    """
    _logger.info("[publish] starting segmented target_date=%s", target_date)

    archive_paths: dict[MarketSegment, Path] = {}
    published_segments = tuple(segment for segment in SEGMENT_ORDER if segment in briefings)
    snapshot_paths = [
        *(compute_archive_path(target_date, segment=segment) for segment in published_segments),
    ]
    snapshots: dict[Path, bytes | None] = {
        path: _read_existing_bytes(path) for path in snapshot_paths
    }
    snapshots.update({path: None for path in asset_paths})

    try:
        for segment in published_segments:
            validate_first_viewport_summary(briefings[segment].rendered_markdown)
            if not verify_disclaimer(briefings[segment].rendered_markdown):
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
        for segment in published_segments:
            archive_path = await asyncio.to_thread(
                write_briefing,
                briefings[segment],
                target_date,
                segment=segment,
            )
            archive_paths[segment] = archive_path
            _logger.info("[publish] wrote segment=%s path=%s", segment, archive_path)
        if all(not path.is_absolute() for path in archive_paths.values()):
            # Snapshot every page the index/heatmap update may rewrite so a
            # subsequent ``write_briefing`` failure rolls them back too.
            snapshots.update(
                {
                    SITE_INDEX_PATH: _read_existing_bytes(SITE_INDEX_PATH),
                    ARCHIVE_INDEX_PATH: _read_existing_bytes(ARCHIVE_INDEX_PATH),
                    OG_CARD_RELATIVE_PATH: _read_existing_bytes(OG_CARD_RELATIVE_PATH),
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
            og_card_path = await asyncio.to_thread(
                write_og_card,
                target_date,
                briefings,
            )
            index_paths = (*index_paths, og_card_path)
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
    except (PublisherDisclaimerError, PublisherIOError):
        _rollback_paths(snapshots)
        raise

    commit_message = (
        f"briefing: {target_date} segmented"
        if len(published_segments) == len(SEGMENT_ORDER)
        else f"briefing: {target_date} segmented partial"
    )
    await asyncio.to_thread(
        commit_and_push,
        commit_message,
        [*archive_paths.values(), *asset_paths, *index_paths, *weekly_paths],
        runner=git_runner,
    )
    _logger.info("[publish] committed + pushed segmented %s", target_date)
    return archive_paths


def _load_recent_context_for_run(target_date: date) -> RecentBriefingsContext | None:
    """Resolve the env-var window and load the trailing recent-briefings context.

    Returns ``None`` when the user explicitly disabled the feature
    (``INVESTO_RECENT_CONTEXT_DAYS=0``); the orchestrator threads
    ``None`` straight through and the briefing prompt omits the
    "최근 N일 컨텍스트" block entirely. Otherwise returns the loaded
    :class:`RecentBriefingsContext`, which itself may be empty (first
    publish path) — the prompt builder handles both cases.

    The :data:`ARCHIVE_ROOT` lookup is deferred to call time (not at
    import) so unit tests that monkeypatch
    ``investo.publisher.paths.ARCHIVE_ROOT`` see the redirected path.
    """
    days = resolve_recent_days()
    if days <= 0:
        _logger.info("[recent_context] disabled (days=0)")
        return None
    from investo.publisher.paths import ARCHIVE_ROOT

    context = load_recent_briefings(ARCHIVE_ROOT, target_date, days=days)
    total = sum(len(entries) for entries in context.entries_by_segment.values())
    _logger.info(
        "[recent_context] loaded target_date=%s days=%d entries=%d",
        target_date,
        days,
        total,
    )
    return context


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
    routed = segment_items(items)
    watchlist_config = load_watchlist()
    prepared_briefings: dict[MarketSegment, Briefing] = {}
    asset_paths: list[Path] = []
    for segment in SEGMENT_ORDER:
        if segment not in briefings:
            continue
        segment_source_items = routed.for_segment(segment)
        segment_coverage = routed.coverage_for_segment(
            segment,
            source_outcomes=source_outcomes,
        )
        prepared = await asyncio.to_thread(
            prepare_segment_visual_assets,
            briefings[segment],
            target_date=target_date,
            segment=segment,
            items=segment_source_items,
            coverage=segment_coverage,
            watchlist_impact=match_watchlist_items(
                segment_source_items,
                watchlist_config,
                coverage_status=segment_coverage.status,
            ),
        )
        prepared_briefings[segment] = prepared.briefing
        asset_paths.extend(prepared.asset_paths)
    return prepared_briefings, tuple(asset_paths)


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
) -> SendResult:
    """Compose + dispatch one public-channel message for all segments."""
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

    pipeline_start = time.monotonic()
    stages: dict[str, str] = {}
    stage_timings: dict[str, float] = {}

    _logger.info("[pipeline] starting target_date=%s", target_date)

    # ------------------------------------------------------------------
    # COLLECT (AC-003-1, AC-003-2)
    # ------------------------------------------------------------------
    stage_start = time.monotonic()
    try:
        items, source_outcomes = await _stage_collect(target_date, fetch=fetch)
    except EmptyCollectError as exc:
        stage_timings["collect"] = time.monotonic() - stage_start
        stages["collect"] = "failed: empty"
        stages.update({"generate": "skipped", "publish": "skipped", "notify_briefing": "skipped"})
        await _safe_alert(alerter, "collect", exc)
        return _build_result(
            target_date=target_date,
            status=PipelineStatus.FAILED,
            stages=stages,
            stage_timings=stage_timings,
            pipeline_start=pipeline_start,
            briefing_url=None,
        )
    stage_timings["collect"] = time.monotonic() - stage_start
    stages["collect"] = "ok"

    # ------------------------------------------------------------------
    # GENERATE (AC-003-3)
    # ------------------------------------------------------------------
    stage_start = time.monotonic()
    segmented_mode = generate is None
    segment_generation_failures: dict[MarketSegment, BriefingGenerationError] = {}
    try:
        if segmented_mode:
            recent_context = _load_recent_context_for_run(target_date)
            segment_briefings, segment_generation_failures = await _stage_generate_segments(
                target_date,
                items,
                runner=runner,
                generate_segment=generate_segment,
                source_outcomes=source_outcomes,
                recent_context=recent_context,
            )
            primary_generated_segment = (
                DOMESTIC_EQUITY
                if DOMESTIC_EQUITY in segment_briefings
                else next(iter(segment_briefings))
            )
            briefing = segment_briefings[primary_generated_segment]
        else:
            segment_briefings = None
            briefing = await _stage_generate(target_date, items, runner=runner, generate=generate)
    except BriefingGenerationError as exc:
        stage_timings["generate"] = time.monotonic() - stage_start
        stages["generate"] = f"failed: {exc.stage}"
        stages.update({"publish": "skipped", "notify_briefing": "skipped"})
        _log_briefing_generation_error(exc)
        await _safe_alert(alerter, "generate", exc)
        return _build_result(
            target_date=target_date,
            status=PipelineStatus.FAILED,
            stages=stages,
            stage_timings=stage_timings,
            pipeline_start=pipeline_start,
            briefing_url=None,
        )
    stage_timings["generate"] = time.monotonic() - stage_start
    if segment_generation_failures:
        failed_segments = ", ".join(segment_generation_failures)
        stages["generate"] = f"partial: failed {failed_segments}"
        for segment, generation_error in segment_generation_failures.items():
            _log_briefing_generation_error(generation_error)
            await _safe_alert(alerter, "generate", generation_error)
            stages[f"generate:{segment}"] = f"failed: {generation_error.stage}"
    else:
        stages["generate"] = "ok"
    visual_assets_failed = False
    visual_asset_paths: tuple[Path, ...] = ()

    if segmented_mode:
        assert segment_briefings is not None
        stage_start = time.monotonic()
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
            stage_timings["visual_assets"] = time.monotonic() - stage_start
            stages["visual_assets"] = f"failed: {type(exc).__name__}"
            _logger.warning(
                "[visual_assets] failed target_date=%s error=%s; publishing text-only",
                target_date,
                exc,
            )
        else:
            stage_timings["visual_assets"] = time.monotonic() - stage_start
            stages["visual_assets"] = f"ok: {len(visual_asset_paths)} files"

    # ------------------------------------------------------------------
    # PUBLISH (AC-003-4, AC-003-5)
    # ------------------------------------------------------------------
    stage_start = time.monotonic()
    try:
        if segmented_mode:
            assert segment_briefings is not None
            await _stage_publish_segments(
                segment_briefings,
                target_date,
                asset_paths=visual_asset_paths,
                git_runner=git_runner,
            )
        else:
            await _stage_publish(briefing, target_date, git_runner=git_runner)
    except (
        SummaryQualityError,
        PublisherDisclaimerError,
        PublisherIOError,
        PublisherGitError,
    ) as exc:
        stage_timings["publish"] = time.monotonic() - stage_start
        stages["publish"] = f"failed: {type(exc).__name__}"
        stages["notify_briefing"] = "skipped"
        await _safe_alert(alerter, "publish", exc)
        return _build_result(
            target_date=target_date,
            status=PipelineStatus.FAILED,
            stages=stages,
            stage_timings=stage_timings,
            pipeline_start=pipeline_start,
            briefing_url=None,
        )
    stage_timings["publish"] = time.monotonic() - stage_start
    stages["publish"] = "ok"

    primary_segment = (
        DOMESTIC_EQUITY
        if segmented_mode and segment_briefings is not None and DOMESTIC_EQUITY in segment_briefings
        else next(iter(segment_briefings), None)
        if segmented_mode and segment_briefings is not None
        else None
    )
    briefing_url = _briefing_url_for(
        target_date,
        site_url_base,
        segment=primary_segment if segmented_mode else None,
    )
    segment_urls = (
        {
            segment: _briefing_url_for(target_date, site_url_base, segment=segment)
            for segment in SEGMENT_ORDER
        }
        if segmented_mode
        else None
    )

    # ------------------------------------------------------------------
    # NOTIFY (AC-003-6 + AC-003-8 — notify failure remains PARTIAL, but is
    # operator-visible because the public channel did not receive the briefing.)
    # ------------------------------------------------------------------
    stage_start = time.monotonic()
    if segmented_mode:
        assert segment_briefings is not None
        assert segment_urls is not None
        notify_result = await _stage_notify_segmented_briefing(
            segment_briefings,
            publisher=publisher,
            site_urls=segment_urls,
            items=items,
        )
    else:
        notify_result = await _stage_notify_briefing(
            briefing, publisher=publisher, site_url=briefing_url
        )
    stage_timings["notify_briefing"] = time.monotonic() - stage_start

    if notify_result.ok:
        stages["notify_briefing"] = "ok"
        status = (
            PipelineStatus.PARTIAL
            if visual_assets_failed or bool(segment_generation_failures)
            else PipelineStatus.SUCCESS
        )
    else:
        stages["notify_briefing"] = f"failed: {notify_result.error}"
        status = PipelineStatus.PARTIAL
        await _safe_alert(
            alerter,
            "notify_briefing",
            NotifyDeliveryError(notify_result.error or "public briefing notification failed"),
        )

    return _build_result(
        target_date=target_date,
        status=status,
        stages=stages,
        stage_timings=stage_timings,
        pipeline_start=pipeline_start,
        briefing_url=briefing_url,
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
    )


__all__ = [
    "NotifyDeliveryError",
    "run_pipeline",
]
