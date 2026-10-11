"""Fixed remote story snapshots and exact bounded, survivor-only ledger updates."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from investo.models.event_story import (
    StoryLedger,
    StoryPublicationDelta,
    StoryRecord,
    story_record_hash,
)
from investo.publisher.git_ops import GitRunner

STORY_LEDGER_PATH = Path("archive/_meta/event_stories_v3.json")
MAX_STORY_LEDGER_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class StoryBaseline:
    baseline_sha: str
    available: bool
    records: tuple[StoryRecord, ...] = ()


def load_committed_story_ledger(
    baseline_sha: str, *, observed_at: datetime, runner: GitRunner
) -> StoryBaseline:
    if (
        re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", baseline_sha) is None
        or observed_at.utcoffset() is None
    ):
        raise ValueError("story.baseline_invalid")
    try:
        listing = runner(
            ["git", "ls-tree", "--name-only", baseline_sha, "--", STORY_LEDGER_PATH.as_posix()],
            capture_output=True,
            text=True,
            check=False,
        )
        if listing.returncode != 0:
            raise ValueError("story.baseline_unavailable")
        if not listing.stdout.strip():
            return StoryBaseline(baseline_sha, True)
        blob = f"{baseline_sha}:{STORY_LEDGER_PATH.as_posix()}"
        size = runner(["git", "cat-file", "-s", blob], capture_output=True, text=True, check=False)
        if (
            size.returncode != 0
            or not re.fullmatch(r"[0-9]{1,20}", size.stdout.strip())
            or int(size.stdout.strip()) > MAX_STORY_LEDGER_BYTES
        ):
            raise ValueError("story.baseline_unavailable")
        data = runner(
            ["git", "show", blob],
            capture_output=True,
            text=True,
            check=False,
        )
        if data.returncode != 0 or len(data.stdout.encode("utf-8")) > MAX_STORY_LEDGER_BYTES:
            raise ValueError("story.baseline_unavailable")
        ledger = StoryLedger.model_validate_json(data.stdout)
        if any(
            r.updated_at > observed_at or r.last_evidence_at > observed_at for r in ledger.records
        ):
            raise ValueError("story.clock_invalid")
        if any(
            sum(r.segment == segment and r.disposition == "active" for r in ledger.records) > 200
            for segment in ("domestic-equity", "us-equity", "crypto")
        ):
            raise ValueError("story.record_budget_exhausted")
        return StoryBaseline(baseline_sha, True, ledger.records)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return StoryBaseline(baseline_sha, False)


def story_ledger_bytes(
    previous: Sequence[StoryRecord],
    deltas: Sequence[StoryPublicationDelta],
    *,
    observed_at: datetime,
) -> bytes:
    if observed_at.utcoffset() is None:
        raise ValueError("story.clock_invalid")
    previous = tuple(StoryRecord.model_validate(r.model_dump()) for r in previous)
    deltas = tuple(StoryPublicationDelta.model_validate(d.model_dump()) for d in deltas)
    records = {(r.segment, r.story_id): r for r in previous}
    if len(records) != len(previous) or len({(d.segment, d.story_id) for d in deltas}) != len(
        deltas
    ):
        raise ValueError("story.ledger_invalid")
    for delta in deltas:
        key = (delta.segment, delta.story_id)
        prior = records.get(key)
        if delta.prior_record_hash != (story_record_hash(prior) if prior else None):
            raise ValueError("story.baseline_conflict")
        if delta.observed_clock != observed_at or delta.next_record.updated_at != observed_at:
            raise ValueError("story.clock_invalid")
        if prior is not None and (
            prior.disposition == "closed"
            or delta.next_record.last_evidence_at <= prior.last_evidence_at
        ):
            raise ValueError("story.closed_immutable")
        records[key] = delta.next_record
    retained = []
    for key in sorted(records):
        record = records[key]
        if record.last_evidence_at > observed_at or record.updated_at > observed_at:
            raise ValueError("story.clock_invalid")
        if record.disposition == "closed" and record.closed_at is not None:
            if observed_at - record.closed_at >= timedelta(days=90):
                continue
        elif observed_at - record.last_evidence_at >= timedelta(days=180):
            record = StoryRecord.model_validate(
                {**record.model_dump(), "disposition": "archived_unknown"}
            )
        retained.append(record)
    if any(
        sum(r.segment == segment and r.disposition == "active" for r in retained) > 200
        for segment in ("domestic-equity", "us-equity", "crypto")
    ):
        raise ValueError("story.record_budget_exhausted")
    ledger = StoryLedger(records=tuple(retained))
    data = (
        json.dumps(
            ledger.model_dump(mode="json"),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    if len(data) > MAX_STORY_LEDGER_BYTES:
        raise ValueError("story.record_budget_exhausted")
    return data
