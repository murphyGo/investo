"""Hash-only event history and crash-safe private publication observations."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from investo.models.events import EventIdentityReceipt
from investo.models.publication import PublishReceipt
from investo.orchestrator import event_receipts as receipts

_NOW = datetime(2026, 9, 27, 3, tzinfo=UTC)


def _identity(key: str, *, published_at: datetime = _NOW) -> EventIdentityReceipt:
    digest = hashlib.sha256(key.encode()).hexdigest()
    return EventIdentityReceipt(
        event_id=digest[:24],
        event_key_hash=digest,
        semantic_key_hash=digest,
        document_aliases=(digest,),
        revision_hashes=(digest,),
        fact_hashes=(digest,),
        published_at=published_at,
    )


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=True, timeout=10)
    return result.stdout.strip()


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    _git("init", "-b", "main")
    _git("config", "user.name", "Event Receipt Test")
    _git("config", "user.email", "event-receipt@example.invalid")
    return tmp_path


def _commit_ledger(records: tuple[EventIdentityReceipt, ...]) -> str:
    path = receipts.EVENT_RECEIPT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(receipts.EventReceiptLedger(receipts=records).model_dump_json())
    _git("add", "--", str(path))
    _git("commit", "-m", "event baseline")
    return _git("rev-parse", "HEAD")


def test_fixed_baseline_ignores_dirty_and_later_local_ledgers(repository: Path) -> None:
    prior = _identity("prior", published_at=_NOW - timedelta(days=1))
    baseline = _commit_ledger((prior,))
    _commit_ledger((_identity("unpublished local commit"),))
    receipts.EVENT_RECEIPT_PATH.write_text("dirty and invalid local ledger")

    loaded = receipts.load_committed_event_receipts(baseline, observed_at=_NOW)

    assert loaded.baseline_sha == baseline
    assert loaded.receipts == (prior,)
    assert len(loaded.metadata_hash) == 64
    assert receipts.EVENT_RECEIPT_PATH.read_text() == "dirty and invalid local ledger"


def test_loaded_history_prunes_expired_and_future_records(repository: Path) -> None:
    boundary = _identity("boundary", published_at=_NOW - timedelta(days=7))
    current = _identity("current")
    baseline = _commit_ledger(
        (
            _identity("expired", published_at=_NOW - timedelta(days=7, microseconds=1)),
            boundary,
            current,
            _identity("future", published_at=_NOW + timedelta(microseconds=1)),
        )
    )
    assert receipts.load_committed_event_receipts(baseline, observed_at=_NOW).receipts == (
        boundary,
        current,
    )


def test_missing_committed_ledger_is_empty_but_corruption_is_explicit(repository: Path) -> None:
    Path("baseline.txt").write_text("baseline")
    _git("add", "baseline.txt")
    _git("commit", "-m", "without ledger")
    baseline = _git("rev-parse", "HEAD")
    assert receipts.load_committed_event_receipts(baseline, observed_at=_NOW).receipts == ()
    receipts.EVENT_RECEIPT_PATH.parent.mkdir(parents=True)
    receipts.EVENT_RECEIPT_PATH.write_text('{"receipts":[{"source_text":"private"}]}')
    _git("add", str(receipts.EVENT_RECEIPT_PATH))
    _git("commit", "-m", "invalid ledger")
    with pytest.raises(ValueError, match="invalid event receipt ledger"):
        receipts.load_committed_event_receipts(_git("rev-parse", "HEAD"), observed_at=_NOW)


def test_published_bytes_prune_merge_aliases_and_keep_only_hashes() -> None:
    original = _identity("source text must remain private", published_at=_NOW - timedelta(days=1))
    alias = hashlib.sha256(b"new document").hexdigest()
    official = hashlib.sha256(b"official event key").hexdigest()
    survivor = original.model_copy(
        update={
            "document_aliases": (alias,),
            "official_key_hashes": (official,),
            "published_at": _NOW,
        }
    )
    data = receipts.event_receipt_bytes(
        (original, _identity("old", published_at=_NOW - timedelta(days=8))),
        (survivor,),
        published_at=_NOW,
    )
    ledger = receipts.EventReceiptLedger.model_validate_json(data)
    assert len(ledger.receipts) == 1
    assert ledger.receipts[0].document_aliases == tuple(sorted((*original.document_aliases, alias)))
    assert ledger.receipts[0].official_key_hashes == (official,)
    assert b"source text must remain private" not in data
    assert b"new document" not in data
    assert b"official event key" not in data
    assert data == receipts.event_receipt_bytes((original,), (survivor,), published_at=_NOW)


def test_survivor_from_another_publication_is_rejected() -> None:
    with pytest.raises(ValueError, match="belong to this publication"):
        receipts.event_receipt_bytes(
            (),
            (_identity("wrong run", published_at=_NOW - timedelta(seconds=1)),),
            published_at=_NOW,
        )


def _publication() -> PublishReceipt:
    return PublishReceipt(
        run_id="private-test",
        local_sha="a" * 40,
        remote_ref="refs/heads/main",
        baseline_metadata_hash="b" * 64,
        status="pending",
    )


def test_private_receipt_is_immutable_and_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "private"
    receipts.persist_publication_receipt(_publication(), root=root)
    (path,) = root.iterdir()
    data = path.read_bytes()
    assert path.name == hashlib.sha256(data).hexdigest() + ".json"
    assert json.loads(data)["status"] == "pending"
    receipts.persist_publication_receipt(_publication(), root=root)
    assert list(root.iterdir()) == [path]
    assert path.read_bytes() == data
    path.write_bytes(b"corrupt existing immutable record")
    with pytest.raises(ValueError, match="content mismatch"):
        receipts.persist_publication_receipt(_publication(), root=root)
    assert path.read_bytes() == b"corrupt existing immutable record"


@pytest.mark.parametrize("failure_point", ["partial_write", "fsync", "install"])
def test_partial_persistence_failure_leaves_retryable_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_point: str
) -> None:
    root = tmp_path / "private"
    real_temporary = tempfile.NamedTemporaryFile

    class PartialWrite:
        def __init__(self, **kwargs: Any) -> None:
            self.handle = real_temporary(**kwargs)
            self.name = self.handle.name

        def __enter__(self) -> PartialWrite:
            return self

        def __exit__(self, *args: object) -> None:
            self.handle.close()

        def write(self, data: bytes) -> None:
            self.handle.write(data[:10])
            self.handle.flush()
            raise OSError("injected partial write")

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("injected persistence failure")

    with monkeypatch.context() as patch:
        if failure_point == "partial_write":
            patch.setattr(
                "investo.orchestrator.event_receipts.tempfile.NamedTemporaryFile", PartialWrite
            )
        else:
            operation = "fsync" if failure_point == "fsync" else "link"
            patch.setattr(f"investo.orchestrator.event_receipts.os.{operation}", fail)
        with pytest.raises(OSError):
            receipts.persist_publication_receipt(_publication(), root=root)
    assert list(root.iterdir()) == []

    receipts.persist_publication_receipt(_publication(), root=root)
    (path,) = root.iterdir()
    assert json.loads(path.read_bytes())["local_sha"] == "a" * 40


def test_git_index_snapshot_restores_unrelated_staged_bytes(repository: Path) -> None:
    Path("unrelated.txt").write_text("unrelated staged content")
    _git("add", "unrelated.txt")
    snapshot = receipts.snapshot_git_index()
    Path("transaction.txt").write_text("transaction")
    _git("add", "transaction.txt")
    snapshot.restore()
    assert snapshot.path.read_bytes() == snapshot.content
    assert _git("diff", "--cached", "--name-only") == "unrelated.txt"
