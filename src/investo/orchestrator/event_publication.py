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
from datetime import datetime
from pathlib import Path

from investo.models.event_quality import EventCoverage
from investo.models.events import EventIdentityReceipt
from investo.models.publication import PublicationRequest
from investo.models.segments import MarketSegment
from investo.orchestrator.event_receipts import (
    EVENT_RECEIPT_PATH,
    EventReceiptBaseline,
    event_receipt_bytes,
    load_committed_event_receipts,
)
from investo.publisher.errors import PublisherGitError
from investo.publisher.git_ops import GitRunner


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
