"""Run-owned event publication inputs using only a fixed remote Git tree."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType

from investo.models.event_identity import EventIdentityBaseline
from investo.models.event_quality import EventCoverage
from investo.models.event_story import StoryPublicationDelta
from investo.models.events import EventIdentityReceipt
from investo.models.news_window import NewsCursorBaseline
from investo.models.publication import PublicationRequest
from investo.models.segments import MarketSegment
from investo.orchestrator.event_receipts import (
    EVENT_RECEIPT_PATH,
    EventReceiptBaseline,
    event_identity_v3_bytes,
    event_identity_v3_path,
    event_receipt_bytes,
    load_committed_event_identity_v3,
    load_committed_event_receipts,
)
from investo.orchestrator.event_story import (
    STORY_LEDGER_PATH,
    StoryBaseline,
    load_committed_story_ledger,
    story_ledger_bytes,
)
from investo.publisher.errors import PublisherGitError
from investo.publisher.event_archive_reader import (
    published_edition_bytes,
)
from investo.publisher.git_ops import GitRunner
from investo.publisher.public_document import FinalizedPublicBundle
from investo.publisher.publication_receipts import metadata_hash_at


def load_remote_event_baseline(
    *,
    observed_at: datetime,
    runner: GitRunner | None = None,
) -> EventReceiptBaseline:
    """Resolve main once, within a shared twenty-second read budget.

    FETCH_HEAD is converted immediately to an immutable SHA. Uncommitted
    metadata and private pending observations are never used as history.
    """
    deadline = time.monotonic() + 20.0

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("event baseline deadline exhausted")
        if runner is not None:
            return runner(args, capture_output=True, text=True, check=False)
        return subprocess.run(
            args, capture_output=True, text=True, check=False, timeout=min(10.0, remaining)
        )

    try:
        fetched = run(["git", "fetch", "--no-tags", "origin", "refs/heads/main"])
        if fetched.returncode != 0:
            raise ValueError("event baseline unavailable")
        result = run(["git", "rev-parse", "--verify", "FETCH_HEAD^{commit}"])
        sha = result.stdout.strip()
        if result.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha) is None:
            raise ValueError("event baseline unavailable")
        return load_committed_event_receipts(sha, observed_at=observed_at, runner=run)
    except (OSError, subprocess.TimeoutExpired, ValueError, PublisherGitError):
        raise PublisherGitError(
            attempt_count=0, last_stderr="event baseline unavailable", cause=None
        ) from None


def prepare_event_publication(
    baseline: EventReceiptBaseline | None,
    *,
    run_id: str,
    survivors: Sequence[EventIdentityReceipt],
    observed_at: datetime,
) -> tuple[PublicationRequest, dict[Path, bytes]]:
    """Stage only sealed survivors; an unavailable CAS baseline cannot publish."""
    if baseline is None:
        raise PublisherGitError(
            attempt_count=0, last_stderr="event baseline unavailable", cause=None
        )
    return (
        PublicationRequest(run_id=run_id, baseline_metadata_hash=baseline.metadata_hash),
        {
            EVENT_RECEIPT_PATH: event_receipt_bytes(
                baseline.receipts, survivors, published_at=observed_at
            )
        },
    )


@dataclass(frozen=True, slots=True)
class EventV3Baseline:
    baseline_sha: str
    metadata_hash: str
    metadata_paths: tuple[Path, ...]
    identity: Mapping[MarketSegment, EventIdentityBaseline]
    stories: StoryBaseline
    news: NewsCursorBaseline | None = None

    def __post_init__(self) -> None:
        if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", self.baseline_sha) is None:
            raise ValueError("event.baseline_invalid")
        object.__setattr__(self, "identity", MappingProxyType(dict(self.identity)))


V3_SEGMENTS: tuple[MarketSegment, ...] = ("domestic-equity", "us-equity", "crypto")


def event_v3_metadata_paths(
    target_date: date, *, extra_paths: Sequence[Path] = ()
) -> tuple[Path, ...]:
    return tuple(
        sorted(
            {
                STORY_LEDGER_PATH,
                *(event_identity_v3_path(segment) for segment in V3_SEGMENTS),
                *(
                    Path("archive/_meta/event_editions_v3")
                    / segment
                    / f"{target_date.isoformat()}.json"
                    for segment in V3_SEGMENTS
                ),
                *extra_paths,
            }
        )
    )


def load_event_v3_baseline(
    *,
    target_date: date,
    observed_at: datetime,
    baseline_sha: str | None = None,
    extra_paths: Sequence[Path] = (),
    news_run_id: str | None = None,
    runner: GitRunner | None = None,
) -> EventV3Baseline:
    """Resolve once, then read all native metadata under one 20-second budget."""
    deadline = time.monotonic() + 20.0

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("event.baseline_unavailable")
        result = (
            runner(args, capture_output=True, text=True, check=False)
            if runner is not None
            else subprocess.run(
                args, capture_output=True, text=True, check=False, timeout=min(10.0, remaining)
            )
        )
        if time.monotonic() > deadline:
            raise TimeoutError("event.baseline_unavailable")
        return result

    try:
        sha = baseline_sha
        if sha is None:
            fetched = run(["git", "fetch", "--no-tags", "origin", "refs/heads/main"])
            if fetched.returncode != 0:
                raise ValueError("event.baseline_unavailable")
            resolved = run(["git", "rev-parse", "--verify", "FETCH_HEAD^{commit}"])
            if resolved.returncode != 0:
                raise ValueError("event.baseline_unavailable")
            sha = resolved.stdout.strip()
        if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha) is None:
            raise ValueError("event.baseline_unavailable")
        news = None
        if news_run_id is not None:
            from investo.orchestrator.news_window import (
                NEWS_CURSOR_PATH,
                load_committed_news_cursors,
                news_manifest_path,
            )

            extra_paths = (*extra_paths, NEWS_CURSOR_PATH, news_manifest_path(news_run_id))
            news = load_committed_news_cursors(
                sha,
                run_id=news_run_id,
                runner=run,
                event_metadata_paths=event_v3_metadata_paths(target_date),
            )
        paths = event_v3_metadata_paths(target_date, extra_paths=extra_paths)
        digest = metadata_hash_at(sha, paths, runner=run)
        identities = {
            segment: load_committed_event_identity_v3(
                sha, segment=segment, observed_at=observed_at, runner=run
            )
            for segment in V3_SEGMENTS
        }
        stories = load_committed_story_ledger(sha, observed_at=observed_at, runner=run)
        return EventV3Baseline(sha, digest, paths, identities, stories, news)
    except (OSError, subprocess.TimeoutExpired, ValueError, PublisherGitError):
        raise PublisherGitError(
            attempt_count=0, last_stderr="event baseline unavailable", cause=None
        ) from None


def prepare_event_v3_publication(
    baseline: EventV3Baseline | None,
    bundle: FinalizedPublicBundle,
    *,
    run_id: str,
    observed_at: datetime,
) -> tuple[PublicationRequest, dict[Path, bytes]]:
    if baseline is None or not baseline.stories.available:
        raise PublisherGitError(
            attempt_count=0, last_stderr="event baseline unavailable", cause=None
        )
    metadata: dict[Path, bytes] = {}
    deltas: list[StoryPublicationDelta] = []
    for document in bundle.documents:
        if document.edition_view is None:
            continue
        identity = baseline.identity.get(document.segment)
        if identity is None or identity.availability != "available":
            raise PublisherGitError(
                attempt_count=0, last_stderr="event baseline unavailable", cause=None
            )
        metadata[event_identity_v3_path(document.segment)] = event_identity_v3_bytes(
            identity.segment_receipts,
            document.canonical_event_receipts,
            segment=document.segment,
            published_at=observed_at,
        )
        metadata[
            Path("archive/_meta/event_editions_v3")
            / document.segment
            / f"{document.target_date.isoformat()}.json"
        ] = published_edition_bytes(document.edition_view.edition)
        deltas.extend(document.story_publication_deltas)
    metadata[STORY_LEDGER_PATH] = story_ledger_bytes(
        baseline.stories.records, deltas, observed_at=observed_at
    )
    if not set(metadata) <= set(baseline.metadata_paths):
        raise ValueError("event.baseline_conflict")
    return PublicationRequest(
        run_id=run_id,
        baseline_metadata_hash=baseline.metadata_hash,
        metadata_paths=baseline.metadata_paths,
    ), metadata


def persist_event_quality_trace(
    coverage: Mapping[MarketSegment, EventCoverage], *, root: Path = Path(".tmp/event-traces")
) -> None:
    """Store bounded hash-only stage observations privately, never as a baseline."""
    payload = {
        segment: {
            "coverage": metrics.model_dump(mode="json"),
            "receipts": [receipt.model_dump(mode="json") for receipt in metrics.receipts],
        }
        for segment, metrics in sorted(coverage.items())
    }
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(data) > 1024 * 1024:
        raise ValueError("event trace exceeds private budget")
    root.mkdir(parents=True, exist_ok=True)
    path = root / (hashlib.sha256(data).hexdigest() + ".json")
    with tempfile.NamedTemporaryFile(dir=root, prefix=".trace-", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
