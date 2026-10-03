"""Remote-only event history and transaction-owned private publication receipts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from investo.models.events import EventIdentityReceipt
from investo.models.publication import PublishReceipt
from investo.publisher.git_ops import GitRunner
from investo.publisher.publication_receipts import metadata_hash_at

EVENT_RECEIPT_PATH = Path("archive/_meta/event_receipts.json")
_MAX_LEDGER_BYTES = 1024 * 1024


class EventReceiptLedger(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: int = Field(default=1, ge=1, le=1)
    receipts: tuple[EventIdentityReceipt, ...] = Field(default=(), max_length=5000)


@dataclass(frozen=True, slots=True)
class EventReceiptBaseline:
    baseline_sha: str
    metadata_hash: str
    receipts: tuple[EventIdentityReceipt, ...]


@dataclass(frozen=True, slots=True)
class GitIndexSnapshot:
    path: Path
    content: bytes | None

    def restore(self) -> None:
        if self.content is None:
            self.path.unlink(missing_ok=True)
        else:
            self.path.write_bytes(self.content)


def _run_git(args: list[str], runner: GitRunner | None) -> subprocess.CompletedProcess[str]:
    if runner is not None:
        return runner(args, capture_output=True, text=True, check=False)
    return subprocess.run(args, capture_output=True, text=True, check=False, timeout=10.0)


def snapshot_git_index(*, runner: GitRunner | None = None) -> GitIndexSnapshot:
    result = _run_git(["git", "rev-parse", "--git-path", "index"], runner)
    if result.returncode != 0 or not result.stdout.strip():
        raise ValueError("publication index snapshot unavailable")
    path = Path(result.stdout.strip()).resolve()
    return GitIndexSnapshot(path, path.read_bytes() if path.exists() else None)


def load_committed_event_receipts(
    baseline_sha: str,
    *,
    observed_at: datetime,
    runner: GitRunner | None = None,
) -> EventReceiptBaseline:
    """Read an explicitly fixed remote SHA; never inspect uncommitted ledger files.

    Failure is explicit so the caller can mark novelty unavailable. Missing
    ledger in a valid remote tree is a legitimate empty initial history.
    """
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", baseline_sha):
        raise ValueError("event receipt baseline must be a fixed Git SHA")
    if observed_at.utcoffset() is None:
        raise ValueError("event receipt clock must be timezone-aware")
    digest = metadata_hash_at(baseline_sha, (EVENT_RECEIPT_PATH,), runner=runner)
    listing = _run_git(
        ["git", "ls-tree", "--name-only", baseline_sha, "--", EVENT_RECEIPT_PATH.as_posix()], runner
    )
    if listing.returncode != 0:
        raise ValueError("event receipt baseline unavailable")
    if not listing.stdout.strip():
        return EventReceiptBaseline(baseline_sha, digest, ())
    result = _run_git(["git", "show", f"{baseline_sha}:{EVENT_RECEIPT_PATH.as_posix()}"], runner)
    if result.returncode != 0 or len(result.stdout.encode("utf-8")) > _MAX_LEDGER_BYTES:
        raise ValueError("event receipt ledger unavailable or over budget")
    try:
        ledger = EventReceiptLedger.model_validate_json(result.stdout)
    except ValueError:
        raise ValueError("invalid event receipt ledger") from None
    recent = tuple(
        r
        for r in ledger.receipts
        if observed_at - timedelta(days=7) <= r.published_at <= observed_at
    )
    return EventReceiptBaseline(baseline_sha, digest, recent)


def event_receipt_bytes(
    previous: Sequence[EventIdentityReceipt],
    survivors: Sequence[EventIdentityReceipt],
    *,
    published_at: datetime,
) -> bytes:
    """Build hash-only metadata; the finalizer supplies sealed survivor records."""
    if published_at.utcoffset() is None:
        raise ValueError("event receipt clock must be timezone-aware")
    by_id = {
        r.event_id: r
        for r in previous
        if published_at - timedelta(days=7) <= r.published_at <= published_at
    }
    for receipt in survivors:
        if receipt.published_at != published_at:
            raise ValueError("survivor receipt must belong to this publication")
        earlier = by_id.get(receipt.event_id)
        if earlier is not None:
            receipt = receipt.model_copy(
                update={
                    "document_aliases": tuple(
                        sorted(set(earlier.document_aliases) | set(receipt.document_aliases))
                    ),
                    "official_key_hashes": tuple(
                        sorted(set(earlier.official_key_hashes) | set(receipt.official_key_hashes))
                    ),
                }
            )
        by_id[receipt.event_id] = receipt
    ledger = EventReceiptLedger(receipts=tuple(by_id[k] for k in sorted(by_id)))
    data = (ledger.model_dump_json() + "\n").encode("utf-8")
    if len(data) > _MAX_LEDGER_BYTES:
        raise ValueError("event receipt ledger exceeds budget")
    return data


def persist_publication_receipt(
    receipt: PublishReceipt,
    *,
    root: Path = Path(".tmp/publication-receipts"),
) -> None:
    """Write each immutable observation privately, before any next Git action."""
    data = (json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":")) + "\n").encode()
    # Content-addressing avoids trusting caller-provided IDs as path components.
    path = root / (hashlib.sha256(data).hexdigest() + ".json")
    root.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=root, prefix=".receipt-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            # An atomic, exclusive install preserves immutable existing observations.
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != data:
                raise ValueError("publication receipt content mismatch") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
