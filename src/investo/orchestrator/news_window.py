"""Pure news planning and E11 metadata preparation from a fixed committed tree."""

from __future__ import annotations

import json
import re
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from datetime import time as day_time
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

from investo.briefing.event_evidence import evidence_document_from_item
from investo.briefing.event_input import is_event_candidate_item
from investo.models.items import NormalizedItem
from investo.models.news_window import (
    MAX_NEWS_SOURCES,
    MAX_NEWS_WINDOWS,
    NewsCursor,
    NewsCursorBaseline,
    NewsCursorLedger,
    NewsDocumentRevision,
    NewsObservationWindow,
    NewsSeenRevision,
    NewsWindowConfig,
    NewsWindowConsumption,
    NewsWindowKey,
    NewsWindowManifest,
    NewsWindowPlan,
    news_item_in_window,
    utc_datetime,
    validate_news_source,
)
from investo.models.publication import PublicationRequest
from investo.models.segments import SEGMENT_MARKET_TZ, MarketSegment
from investo.publisher.errors import PublisherGitError
from investo.publisher.git_ops import GitRunner
from investo.publisher.publication_receipts import metadata_hash_at

if TYPE_CHECKING:
    from investo.models.coverage import SourceWindowCoverage

NEWS_CURSOR_PATH = Path("archive/_meta/news_cursors.json")
NEWS_MANIFEST_ROOT = Path("archive/_meta/news_windows")
_MAX_METADATA_BYTES = 1024 * 1024


def news_manifest_path(run_id: str) -> Path:
    # Reuse the transaction's closed, bounded ID grammar before forming a path.
    PublicationRequest(run_id=run_id, baseline_metadata_hash="0" * 64)
    return NEWS_MANIFEST_ROOT / f"{run_id}.json"


def load_news_replay_windows(path: Path) -> Mapping[NewsWindowKey, NewsObservationWindow]:
    """Read one closed local manifest, without Git/network or production state access."""
    try:
        if not path.is_file():
            raise ValueError("news replay manifest must be a regular file")
        with path.open("rb") as handle:
            data = handle.read(_MAX_METADATA_BYTES + 1)
        if len(data) > _MAX_METADATA_BYTES:
            raise ValueError("news replay manifest exceeds budget")
        manifest = NewsWindowManifest.model_validate_json(data)
    except (OSError, ValueError):
        # Parser errors can include rejected input values. Keep them private and bounded.
        raise ValueError("invalid local news replay manifest") from None
    return MappingProxyType(
        {(row.source_name, row.segment): row.window for row in manifest.windows}
    )


def make_news_window_plan(
    config: NewsWindowConfig,
    *,
    run_id: str,
    target_date: date,
    observed_at: datetime,
    source_recipients: Mapping[str, Sequence[MarketSegment]],
    baseline: NewsCursorBaseline | None = None,
    replay: bool = False,
    dry_run: bool = False,
    replay_windows: Mapping[NewsWindowKey, NewsObservationWindow] | None = None,
) -> NewsWindowPlan:
    """Plan intervals without I/O; an absent baseline means bounded bootstrap."""
    if config.start_utc is not None and not replay:
        raise ValueError("news override requires replay")
    if replay_windows is not None and not replay:
        raise ValueError("frozen news windows require replay")
    if replay_windows is not None and config.start_utc is not None:
        raise ValueError("news manifest and range override are mutually exclusive")
    if replay or dry_run:
        baseline = None  # Never mix a live cursor into a historical date.
    if baseline is not None and baseline.run_id != run_id:
        raise ValueError("news baseline belongs to another run")
    if len(source_recipients) > MAX_NEWS_SOURCES:
        raise ValueError("news plan source limit exceeded")
    for source, recipients in source_recipients.items():
        validate_news_source(source)
        if len(recipients) > 3 or any(segment not in SEGMENT_MARKET_TZ for segment in recipients):
            raise ValueError("invalid news source recipients")
    if replay_windows is not None and set(replay_windows) != {
        (source, segment)
        for source, recipients in source_recipients.items()
        for segment in recipients
    }:
        raise ValueError("news manifest recipients differ from current source configuration")
    baseline_ref = baseline.baseline_sha if baseline else None
    baseline_hash = baseline.cursor_hash if baseline else None
    cursors = (
        {(row.source_name, row.segment): row.end_utc for row in baseline.ledger.cursors}
        if baseline
        else {}
    )
    windows: dict[NewsWindowKey, NewsObservationWindow] = {}
    clock = utc_datetime(observed_at)
    for source, recipients in sorted(source_recipients.items()):
        for segment in sorted(set(recipients)):
            key = source, segment
            if replay and replay_windows is not None:
                if key not in replay_windows:
                    raise ValueError("frozen news manifest is missing recipient window")
                prior = replay_windows[key]
                window = replace(prior, mode="replay", run_id=run_id)
                if windows and window.baseline_ref != next(iter(windows.values())).baseline_ref:
                    raise ValueError("frozen news windows have mixed baselines")
                baseline_ref = window.baseline_ref
            elif replay:
                zone = SEGMENT_MARKET_TZ[segment]
                start = config.start_utc or datetime.combine(target_date, day_time.min, zone)
                end = config.end_utc or datetime.combine(
                    target_date + timedelta(days=1), day_time.min, zone
                )
                window = NewsObservationWindow(start, start, end, "replay", run_id)
            else:
                cursor = cursors.get(key)
                logical = cursor if cursor is not None else clock - timedelta(hours=72)
                requested = (
                    clock
                    if clock <= logical
                    else logical
                    if cursor is None
                    else max(logical - timedelta(hours=24), clock - timedelta(days=7))
                )
                window = NewsObservationWindow(
                    logical,
                    requested,
                    clock,
                    "shadow" if config.mode == "shadow" else "scheduled",
                    run_id,
                    baseline_ref,
                )
            windows[key] = window
    if replay:
        clock = max(
            (window.end_utc for window in windows.values()),
            default=datetime.combine(target_date + timedelta(days=1), day_time.min, UTC),
        )
    return NewsWindowPlan(
        run_id=run_id,
        mode=config.mode,
        target_date=target_date,
        observed_at=clock,
        replay=replay,
        dry_run=dry_run,
        baseline_ref=baseline_ref,
        baseline_cursor_hash=baseline_hash,
        windows=windows,
    )


def union_news_windows(plan: NewsWindowPlan) -> Mapping[str, NewsObservationWindow]:
    """Fetch each source once; held recipient intervals contribute no request."""
    result: dict[str, NewsObservationWindow] = {}
    for (source, _segment), window in plan.windows.items():
        if not window.fetch_required:
            continue
        previous = result.get(source)
        result[source] = (
            window
            if previous is None
            else replace(
                window,
                logical_start=min(previous.logical_start, window.logical_start),
                requested_start=min(previous.requested_start, window.requested_start),
                end_utc=max(previous.end_utc, window.end_utc),
            )
        )
    return MappingProxyType(result)


def news_document_revision(item: NormalizedItem) -> NewsDocumentRevision:
    evidence = evidence_document_from_item(item, received_at=item.published_at)
    return NewsDocumentRevision(
        document_id=evidence.document_id,
        revision_id=evidence.origin_revision_id or evidence.revision_id,
    )


def deduplicate_news_items(items: Sequence[NormalizedItem]) -> tuple[NormalizedItem, ...]:
    """Same document/revision collapses; changed content retains its own revision."""
    result: list[NormalizedItem] = []
    seen: set[NewsDocumentRevision] = set()
    for item in items:
        revision = news_document_revision(item)
        if revision not in seen:
            seen.add(revision)
            result.append(item)
    return tuple(result)


def filter_news_items_for_segment(
    plan: NewsWindowPlan,
    segment: MarketSegment,
    items: Sequence[NormalizedItem],
    baseline: NewsCursorBaseline | None = None,
) -> tuple[NormalizedItem, ...]:
    """Keep legacy/price/lookahead rows; apply opt-in windows and revision dedup."""
    if plan.mode != "active":
        return tuple(items)
    if (
        baseline is not None
        and not plan.replay
        and not plan.dry_run
        and (
            baseline.baseline_sha != plan.baseline_ref
            or baseline.cursor_hash != plan.baseline_cursor_hash
        )
    ):
        raise ValueError("news filtering baseline differs from plan")
    seen = (
        {
            (row.source_name, row.document_id, row.revision_id)
            for row in baseline.ledger.seen_revisions
            if row.segment == segment
            and plan.observed_at - timedelta(days=7) <= row.observed_at <= plan.observed_at
        }
        if baseline is not None and not plan.replay and not plan.dry_run
        else set()
    )
    sources = {source for source, _ in plan.windows}
    result: list[NormalizedItem] = []
    for item in items:
        if item.source_name not in sources or not is_event_candidate_item(item):
            result.append(item)
            continue
        window = plan.windows.get((item.source_name, segment))
        if window is None or not news_item_in_window(item, window):
            continue
        revision = news_document_revision(item)
        key = item.source_name, revision.document_id, revision.revision_id
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return tuple(result)


def make_news_window_consumptions(
    plan: NewsWindowPlan, *, segment: MarketSegment, items: Sequence[NormalizedItem]
) -> tuple[NewsWindowConsumption, ...]:
    """Bind actual successful generation inputs; the finalizer alone sets phase sealed."""
    if plan.mode != "active":
        return ()
    return tuple(
        NewsWindowConsumption(
            run_id=plan.run_id,
            source_name=source,
            segment=segment,
            requested_start=window.requested_start,
            end_utc=window.end_utc,
            baseline_ref=plan.baseline_ref,
            baseline_cursor_hash=plan.baseline_cursor_hash,
            documents=tuple(
                sorted(
                    {
                        news_document_revision(item)
                        for item in items
                        if item.source_name == source
                        and is_event_candidate_item(item)
                        and news_item_in_window(item, window)
                    },
                    key=lambda row: (row.document_id, row.revision_id),
                )
            ),
        )
        for (source, recipient), window in plan.windows.items()
        if recipient == segment and window.fetch_required
    )


def load_committed_news_cursors(
    baseline_sha: str,
    *,
    run_id: str,
    runner: GitRunner | None = None,
    event_metadata_paths: Sequence[Path] = (),
) -> NewsCursorBaseline:
    """Read a fixed SHA only, with a twenty-second budget; never fetch or write."""
    # Validate the SHA before it can become a Git revision argument.
    if (
        not isinstance(baseline_sha, str)
        or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", baseline_sha) is None
    ):
        raise ValueError("news baseline must be a fixed commit id")
    paths = (NEWS_CURSOR_PATH, news_manifest_path(run_id), *event_metadata_paths)
    PublicationRequest(run_id=run_id, baseline_metadata_hash="0" * 64, metadata_paths=paths)
    deadline = time.monotonic() + 20

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("news baseline deadline exhausted")
        if runner is not None:
            return runner(args, capture_output=True, text=True, check=False)
        return subprocess.run(
            args, capture_output=True, text=True, check=False, timeout=min(10, remaining)
        )

    try:
        combined_hash = metadata_hash_at(baseline_sha, paths, runner=run)
        cursor_hash = metadata_hash_at(baseline_sha, (NEWS_CURSOR_PATH,), runner=run)
        listing = run(
            [
                "git",
                "--literal-pathspecs",
                "ls-tree",
                "-z",
                baseline_sha,
                "--",
                str(NEWS_CURSOR_PATH),
            ]
        )
        if listing.returncode:
            raise ValueError("news baseline unavailable")
        ledger = NewsCursorLedger()
        if listing.stdout:
            # ls-tree returns object metadata, not blob contents. Refuse trees,
            # symlinks and malformed records before requesting any body bytes.
            metadata, separator, path = listing.stdout.partition("\t")
            identity = metadata.split()
            if (
                not separator
                or path != NEWS_CURSOR_PATH.as_posix() + "\0"
                or len(identity) != 3
                or identity[0] not in {"100644", "100755"}
                or identity[1] != "blob"
                or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", identity[2]) is None
            ):
                raise ValueError("news baseline unavailable")
            # The immutable SHA:path binds size and body to the same blob.
            size = run(["git", "cat-file", "-s", f"{baseline_sha}:{NEWS_CURSOR_PATH.as_posix()}"])
            raw_size = size.stdout.strip()
            if (
                size.returncode
                or re.fullmatch(r"[0-9]{1,20}", raw_size) is None
                or int(raw_size) > _MAX_METADATA_BYTES
            ):
                raise ValueError("news baseline unavailable")
            result = run(["git", "show", f"{baseline_sha}:{NEWS_CURSOR_PATH.as_posix()}"])
            if result.returncode or len(result.stdout.encode()) > _MAX_METADATA_BYTES:
                raise ValueError("news baseline unavailable")
            ledger = NewsCursorLedger.model_validate_json(result.stdout)
        return NewsCursorBaseline(baseline_sha, cursor_hash, ledger, combined_hash, paths, run_id)
    except (OSError, subprocess.TimeoutExpired, ValueError, PublisherGitError):
        raise PublisherGitError(
            attempt_count=0, last_stderr="news baseline unavailable", cause=None
        ) from None


def prepare_news_window_publication(
    plan: NewsWindowPlan,
    baseline: NewsCursorBaseline | None,
    *,
    coverage: Sequence[SourceWindowCoverage],
    consumed: Sequence[NewsWindowConsumption],
    event_metadata: Mapping[Path, bytes] | None = None,
) -> tuple[PublicationRequest, dict[Path, bytes]] | None:
    """Prepare transaction bytes only; E11 remote confirmation makes them committed."""
    if plan.mode != "active" or plan.replay or plan.dry_run:
        return None
    if baseline is None or (baseline.baseline_sha, baseline.cursor_hash, baseline.run_id) != (
        plan.baseline_ref,
        plan.baseline_cursor_hash,
        plan.run_id,
    ):
        raise ValueError("publication requires the exact news baseline")
    extras = dict(event_metadata or {})
    paths = (NEWS_CURSOR_PATH, news_manifest_path(plan.run_id), *sorted(extras))
    if set(paths) != set(baseline.metadata_paths) or len(paths) != len(set(paths)):
        raise ValueError("news publication metadata differs from baseline CAS fields")
    if any(len(data) > _MAX_METADATA_BYTES for data in extras.values()):
        raise ValueError("news publication metadata exceeds budget")
    observations = {item.source_name: item for item in coverage}
    if (
        len(observations) != len(coverage)
        or len(coverage) > MAX_NEWS_SOURCES
        or len(consumed) > MAX_NEWS_WINDOWS
    ):
        raise ValueError("duplicate or excessive news coverage receipts")
    receipts = {(item.source_name, item.segment): item for item in consumed}
    if len(receipts) != len(consumed):
        raise ValueError("duplicate consumed news window")
    cursors = {(row.source_name, row.segment): row for row in baseline.ledger.cursors}
    seen = {
        (row.source_name, row.segment, row.document_id, row.revision_id): row
        for row in baseline.ledger.seen_revisions
        if plan.observed_at - timedelta(days=7) <= row.observed_at
    }
    manifest_rows: list[dict[str, object]] = []
    requested = union_news_windows(plan)
    for key, window in plan.windows.items():
        receipt, source = receipts.get(key), observations.get(key[0])
        if receipt is not None and (
            receipt.run_id,
            receipt.baseline_ref,
            receipt.baseline_cursor_hash,
            receipt.requested_start,
            receipt.end_utc,
        ) != (
            plan.run_id,
            plan.baseline_ref,
            plan.baseline_cursor_hash,
            window.requested_start,
            window.end_utc,
        ):
            raise ValueError("consumed news window differs from plan")
        full = bool(
            source is not None
            and key[0] in requested
            and source.completeness == "full"
            and source.requested_start == requested[key[0]].requested_start
            and source.end_utc == requested[key[0]].end_utc
            and source.requested_start <= window.requested_start
            and source.end_utc >= window.end_utc
            and not source.cap_reached
            and not source.parse_failures
        )
        advance = (
            window.fetch_required and full and receipt is not None and receipt.phase == "sealed"
        )
        reason = (
            "advanced"
            if advance
            else "clock_not_after_cursor"
            if not window.fetch_required
            else "not_sealed"
            if receipt is None or receipt.phase != "sealed"
            else "coverage_not_full"
        )
        if advance:
            assert receipt is not None
            cursors[key] = NewsCursor(source_name=key[0], segment=key[1], end_utc=window.end_utc)
            for document in receipt.documents:
                revision = NewsSeenRevision(
                    source_name=key[0],
                    segment=key[1],
                    document_id=document.document_id,
                    revision_id=document.revision_id,
                    observed_at=window.end_utc,
                )
                seen[(*key, revision.document_id, revision.revision_id)] = revision
        manifest_rows.append(
            {
                "source_name": key[0],
                "segment": key[1],
                "window": asdict(window),
                "gap_seconds": window.gap_seconds,
                "completeness": source.completeness if source is not None else "unknown",
                "disposition": reason,
                "consumption": asdict(receipt)
                | {"documents": [row.model_dump() for row in receipt.documents]}
                if receipt is not None
                else None,
            }
        )
    if set(receipts) - set(plan.windows):
        raise ValueError("consumption outside planned source recipients")
    ledger = NewsCursorLedger(
        cursors=tuple(cursors[key] for key in sorted(cursors)),
        seen_revisions=tuple(seen[key] for key in sorted(seen)),
    )
    manifest = {
        "schema_version": 1,
        "run_id": plan.run_id,
        "baseline_cursor_hash": baseline.cursor_hash,
        "windows": manifest_rows,
    }
    NewsWindowManifest.model_validate(manifest)
    metadata = {
        **extras,
        NEWS_CURSOR_PATH: (ledger.model_dump_json() + "\n").encode(),
        news_manifest_path(plan.run_id): (
            json.dumps(
                manifest,
                sort_keys=True,
                separators=(",", ":"),
                default=lambda value: value.isoformat() if isinstance(value, datetime) else value,
            )
            + "\n"
        ).encode(),
    }
    if any(len(data) > _MAX_METADATA_BYTES for data in metadata.values()):
        raise ValueError("news publication metadata exceeds budget")
    return PublicationRequest(
        run_id=plan.run_id,
        baseline_metadata_hash=baseline.metadata_hash,
        metadata_paths=tuple(sorted(paths)),
    ), metadata
