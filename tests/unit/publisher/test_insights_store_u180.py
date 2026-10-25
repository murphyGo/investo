from pathlib import Path

import pytest

from investo.models.insights import MANIFEST_PATH
from investo.models.publication import PublishReceipt
from investo.orchestrator.insights_projection import update_history
from investo.publisher.insights.store import (
    InsightStoreError,
    InsightTransaction,
    prepare_bundle,
    validate_bundle,
)
from tests._helpers.insights import module, qualification


def prepared():
    projected = module()
    return prepare_bundle(
        (projected,), {"crypto": update_history(projected, None, (qualification(),))}
    )


def test_bundle_identity_and_corruption():
    data = prepared()
    files = dict(data.files)
    manifest, modules, histories = validate_bundle(files)
    assert modules["crypto"].snapshot_id == manifest.modules[0].snapshot_id
    assert histories["crypto"].rows
    files[Path("site_docs/insights/crypto/index.md")] += b"changed"
    with pytest.raises(InsightStoreError):
        validate_bundle(files)


def test_multi_file_rollback_preserves_unrelated(tmp_path):
    other = tmp_path / "unrelated.md"
    other.write_text("dirty unrelated")
    transaction = InsightTransaction(tmp_path)
    data = prepared()
    transaction.stage(data)
    validate_bundle({path: (tmp_path / path).read_bytes() for path, _ in data.files})
    transaction.rollback()
    assert all(not (tmp_path / path).exists() for path, _ in data.files)
    assert other.read_text() == "dirty unrelated"


def test_crash_recovery_and_concurrent_file_protection(tmp_path):
    transaction = InsightTransaction(tmp_path)
    data = prepared()
    transaction.stage(data)
    InsightTransaction(tmp_path).recover()
    assert not transaction.directory.exists()
    transaction.stage(data)
    owned = tmp_path / MANIFEST_PATH
    owned.write_text("other writer")
    with pytest.raises(InsightStoreError):
        transaction.rollback()
    assert owned.read_text() == "other writer"


def test_ambiguous_receipt_retained(tmp_path):
    transaction = InsightTransaction(tmp_path)
    transaction.stage(prepared())
    transaction.record_receipt(
        PublishReceipt(
            run_id="fixture",
            local_sha="a" * 40,
            remote_ref="refs/heads/main",
            baseline_metadata_hash="0" * 64,
            status="outcome_unknown",
        )
    )
    with pytest.raises(InsightStoreError):
        InsightTransaction(tmp_path).recover()
    assert transaction.directory.exists()


def test_symlink_never_followed(tmp_path):
    external = tmp_path / "external"
    external.mkdir()
    (tmp_path / "site_docs").symlink_to(external)
    with pytest.raises(InsightStoreError):
        InsightTransaction(tmp_path).stage(prepared())
    assert not list(external.iterdir())


def test_journal_and_backups_durable_before_first_public_replace(tmp_path, monkeypatch):
    from investo.publisher.insights import store

    events = []
    original = store._atomic_write

    def record(path, data):
        original(path, data)
        events.append(path)

    monkeypatch.setattr(store, "_atomic_write", record)
    transaction = InsightTransaction(tmp_path)
    transaction.stage(prepared())
    journal_position = events.index(transaction.directory / "journal.json")
    public_positions = [
        i for i, path in enumerate(events) if transaction.directory not in path.parents
    ]
    assert journal_position < min(public_positions)
    transaction.rollback()


def test_partial_write_failure_rolls_back_all_owned_files(tmp_path, monkeypatch):
    from investo.publisher.insights import store

    original = store._atomic_write
    failed = False

    def fail_once(path, data):
        nonlocal failed
        if path.name == "index.md" and not failed:
            failed = True
            raise OSError("synthetic promotion failure")
        original(path, data)

    monkeypatch.setattr(store, "_atomic_write", fail_once)
    transaction = InsightTransaction(tmp_path)
    with pytest.raises(OSError):
        transaction.stage(prepared())
    assert all(not (tmp_path / path).exists() for path, _ in prepared().files)
    assert not transaction.directory.exists()


def test_corrupt_backup_never_overwrites_owned_file(tmp_path):
    data = prepared()
    for relative, content in data.files:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    transaction = InsightTransaction(tmp_path)
    transaction.stage(data)
    (transaction.directory / "0").write_bytes(b"corrupted backup")
    before = {path: (tmp_path / path).read_bytes() for path, _ in data.files}
    with pytest.raises(InsightStoreError, match="backup identity"):
        transaction.rollback()
    assert {path: (tmp_path / path).read_bytes() for path in before} == before


def test_custom_renderer_requires_disclaimer():
    projected = module()
    with pytest.raises(InsightStoreError, match="disclaimer"):
        prepare_bundle(
            (projected,),
            {"crypto": update_history(projected, None, (qualification(),))},
            renderer=lambda m: f"<!-- insights-snapshot:{m.snapshot_id} -->",
        )
