"""Local bare-Git evidence only; no production push, source call or Pages run."""

import asyncio
import subprocess
import threading
from datetime import timedelta
from pathlib import Path

import pytest

from investo.models.insights import MANIFEST_PATH
from investo.orchestrator import insights_publication as publication
from investo.orchestrator.insights import InsightsConfig
from investo.orchestrator.insights_projection import update_history
from investo.publisher.insights.store import InsightTransaction, prepare_bundle
from tests._helpers.insights import NOW, capture, module, qualification


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def repository(tmp_path, monkeypatch):
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    other = tmp_path / "other"
    git(tmp_path, "init", "--bare", str(remote))
    git(tmp_path, "init", "-b", "main", str(work))
    git(work, "config", "user.name", "Insight Fixture")
    git(work, "config", "user.email", "fixture@example.invalid")
    (work / "legacy.md").write_text("legacy")
    git(work, "add", "legacy.md")
    git(work, "commit", "-m", "baseline")
    git(work, "remote", "add", "origin", str(remote))
    git(work, "push", "-u", "origin", "main")
    git(tmp_path, "clone", "-b", "main", str(remote), str(other))
    git(other, "config", "user.name", "Concurrent Writer")
    git(other, "config", "user.email", "other@example.invalid")
    monkeypatch.chdir(work)
    monkeypatch.setattr(publication, "load_qualifications", lambda: (qualification(),))
    monkeypatch.setattr("investo.publisher.publication_receipts.time.sleep", lambda _: None)
    return work, remote, other


async def phase(mode="active", *, write_allowed=True, runner=None):
    return await publication.run_insights_phase(
        InsightsConfig(mode, ("crypto",)),
        capture(),
        run_started_at=NOW,
        collection_completed_at=NOW,
        evaluated_at=NOW,
        write_allowed=write_allowed,
        runner=runner,
    )


async def test_real_remote_confirmed_bundle_and_dirty_unrelated_preserved(repository):
    work, remote, _ = repository
    (work / "legacy.md").write_text("unrelated dirty")
    result = await phase()
    assert result.status == "remote_confirmed"
    assert result.receipt.local_sha == git(remote, "rev-parse", "main")
    assert (work / "legacy.md").read_text() == "unrelated dirty"
    baseline = publication.load_remote_baseline()
    assert baseline.modules["crypto"].snapshot_id == result.projected_modules[0].snapshot_id
    assert baseline.histories["crypto"].rows
    assert not (work / ".tmp/insights-publication").exists()


async def test_unrelated_staged_index_rejected_without_mutation(repository):
    work, remote, _ = repository
    before = git(remote, "rev-parse", "main")
    (work / "legacy.md").write_text("staged")
    git(work, "add", "legacy.md")
    index = (work / ".git/index").read_bytes()
    result = await phase()
    assert result.status == "failed"
    assert (work / ".git/index").read_bytes() == index
    assert git(remote, "rev-parse", "main") == before
    assert not (work / MANIFEST_PATH).exists()


@pytest.mark.parametrize("same_metadata", [False, True])
async def test_concurrent_writer_uses_manifest_only_cas(repository, same_metadata):
    work, remote, other = repository
    advanced = False

    def runner(args, **kwargs):
        nonlocal advanced
        if args[1] == "push" and not advanced:
            advanced = True
            relative = (
                Path(MANIFEST_PATH) if same_metadata else Path("archive/_meta/event_receipts.json")
            )
            target = other / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                '{"schema_version":1,"modules":[]}' if same_metadata else '{"unrelated":true}'
            )
            git(other, "add", "--", str(relative))
            git(other, "commit", "-m", "other metadata")
            git(other, "push", "origin", "HEAD:refs/heads/main")
        return subprocess.run(args, capture_output=True, text=True)

    result = await phase(runner=runner)
    if same_metadata:
        assert result.status == "failed"
        assert result.receipt.status == "definitely_unpublished"
        assert (work / ".tmp/insights-publication").exists()
    else:
        assert result.status == "remote_confirmed"
        assert (
            git(work, "show", f"{result.receipt.local_sha}:archive/_meta/event_receipts.json")
            == '{"unrelated":true}'
        )
        assert git(remote, "merge-base", "--is-ancestor", result.receipt.local_sha, "main") == ""


async def test_push_success_with_confirmation_unavailable_is_unknown(repository):
    work, remote, _ = repository
    pushed = False

    def runner(args, **kwargs):
        nonlocal pushed
        if args[1] == "fetch" and pushed:
            return subprocess.CompletedProcess(args, 1, "", "private diagnostic")
        result = subprocess.run(args, capture_output=True, text=True)
        if args[1] == "push":
            pushed = True
        return result

    result = await phase(runner=runner)
    assert result.status == "outcome_unknown"
    assert result.receipt.status == "outcome_unknown"
    assert result.receipt.local_sha == git(remote, "rev-parse", "main")
    assert (work / ".tmp/insights-publication").exists()


@pytest.mark.parametrize(
    "mode,write_allowed,expected", [("shadow", True, "shadow"), ("active", False, "skipped")]
)
async def test_shadow_dry_run_replay_have_no_git_or_file_writes(
    repository, mode, write_allowed, expected
):
    work, _, _ = repository

    def forbidden(*args, **kwargs):
        raise AssertionError("Git called in no-write mode")

    result = await phase(mode, write_allowed=write_allowed, runner=forbidden)
    assert result.status == expected
    assert not (work / MANIFEST_PATH).exists()
    assert not (work / ".tmp/insights-publication").exists()


async def test_cancellation_drains_worker(monkeypatch):
    started = threading.Event()
    finish = threading.Event()
    drained = threading.Event()

    def worker(*args, **kwargs):
        started.set()
        finish.wait(2)
        drained.set()

    monkeypatch.setattr(publication, "_phase", worker)
    task = asyncio.create_task(phase("shadow"))
    await asyncio.to_thread(started.wait, 2)
    task.cancel()
    task.cancel()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert drained.is_set()


async def test_unknown_publication_is_reconciled_before_next_baseline(repository):
    pushed = False

    def runner(args, **kwargs):
        nonlocal pushed
        if args[1] == "fetch" and pushed:
            return subprocess.CompletedProcess(args, 1, "", "unavailable")
        result = subprocess.run(args, capture_output=True, text=True)
        if args[1] == "push":
            pushed = True
        return result

    first = await phase(runner=runner)
    assert first.status == "outcome_unknown"
    second = await phase()
    assert second.status == "remote_confirmed"
    assert publication.load_remote_baseline().histories["crypto"].rows


async def test_live_transaction_cannot_be_recovered_by_second_worker(repository):
    from investo.publisher.insights.store import InsightTransaction
    from tests.unit.publisher.test_insights_store_u180 import prepared

    first = InsightTransaction()
    first.acquire()
    try:
        first.stage(prepared())
        before = {p: p.read_bytes() for p, _ in prepared().files}
        second = await phase()
        assert second.status == "failed"
        assert {p: p.read_bytes() for p in before} == before
        first.rollback()
    finally:
        first.release()


async def test_programming_error_is_not_silenced(repository, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("programming error")

    monkeypatch.setattr(publication, "project_module", broken)
    with pytest.raises(RuntimeError, match="programming error"):
        await phase("shadow")


async def test_remote_confirmation_wins_over_private_cleanup_failure(repository, monkeypatch):
    from investo.publisher.insights.store import InsightTransaction

    def fail_cleanup(self):
        raise OSError("private cleanup failed")

    monkeypatch.setattr(InsightTransaction, "finish", fail_cleanup)
    result = await phase()
    assert result.status == "remote_confirmed"
    assert result.receipt.status == "remote_confirmed"


async def test_committed_byte_mismatch_blocks_push_and_retains_receipt(repository):
    work, remote, _ = repository
    before = git(remote, "rev-parse", "main")

    def runner(args, **kwargs):
        if args[1] == "commit":
            target = work / "site_docs/insights/_data/crypto/current.json"
            target.write_text("unexpected concurrent write")
            git(work, "add", "--", str(target.relative_to(work)))
        return subprocess.run(args, capture_output=True, text=True)

    result = await phase(runner=runner)
    assert result.status == "outcome_unknown"
    assert result.receipt.local_sha != before
    assert git(remote, "rev-parse", "main") == before
    assert (work / ".tmp/insights-publication").exists()


@pytest.mark.parametrize("revoke", [True, False])
async def test_inactive_module_rights_or_retention_withdrawal_is_published(
    repository, monkeypatch, revoke
):
    assert (await phase()).status == "remote_confirmed"
    changed = qualification().model_copy(update={"revoked": revoke, "retention_allowed": False})
    monkeypatch.setattr(publication, "load_qualifications", lambda: (changed,))
    result = await publication.run_insights_phase(
        InsightsConfig("active", ("macro",)),
        capture(),
        run_started_at=NOW,
        collection_completed_at=NOW,
        evaluated_at=NOW,
        write_allowed=True,
    )
    assert result.status == "remote_confirmed"
    baseline = publication.load_remote_baseline()
    assert not baseline.histories["crypto"].rows
    assert bool(baseline.modules["crypto"].metrics) is not revoke


def stage_without_receipt(work):
    current = module(now=NOW + timedelta(seconds=1))
    prepared = prepare_bundle(
        (current,), {"crypto": update_history(current, None, (qualification(),))}
    )
    transaction = InsightTransaction(work)
    transaction.acquire()
    try:
        transaction.stage(prepared, initial_head=git(work, "rev-parse", "HEAD"))
    finally:
        transaction.release()
    git(work, "add", "--", *(str(p) for p, _ in prepared.files))
    return prepared


@pytest.mark.parametrize("existing_baseline", [False, True])
async def test_crash_after_add_recovers_owned_index_before_next_publication(
    repository, existing_baseline
):
    work, _, _ = repository
    if existing_baseline:
        assert (await phase()).status == "remote_confirmed"
    stage_without_receipt(work)
    assert git(work, "diff", "--cached", "--name-only")
    result = await phase()
    assert result.status == "remote_confirmed"
    assert not git(work, "diff", "--cached", "--name-only")
    assert not (work / ".tmp/insights-publication").exists()


async def test_crash_after_commit_before_receipt_preserves_unknown_transaction(repository):
    work, remote, _ = repository
    before = git(remote, "rev-parse", "main")
    prepared = stage_without_receipt(work)
    git(work, "commit", "-m", "Commit before receipt crash")
    committed = git(work, "rev-parse", "HEAD")
    result = await phase()
    assert result.status == "outcome_unknown"
    assert git(work, "rev-parse", "HEAD") == committed
    assert git(remote, "rev-parse", "main") == before
    assert all((work / p).read_bytes() == data for p, data in prepared.files)
    assert (work / ".tmp/insights-publication/journal.json").exists()


async def test_crash_recovery_preserves_unrelated_staged_index(repository):
    work, _, _ = repository
    prepared = stage_without_receipt(work)
    (work / "legacy.md").write_text("unrelated staging")
    git(work, "add", "legacy.md")
    result = await phase()
    assert result.status == "failed"
    assert git(work, "diff", "--cached", "--name-only") == "legacy.md"
    assert git(work, "show", ":legacy.md") == "unrelated staging"
    assert all(not (work / p).exists() for p, _ in prepared.files)


async def test_crash_recovery_refuses_changed_owned_index(repository):
    work, _, _ = repository
    prepared = stage_without_receipt(work)
    path, expected = prepared.files[0]
    (work / path).write_bytes(b"another writer's staged content")
    git(work, "add", "--", str(path))
    (work / path).write_bytes(expected)
    index = (work / ".git/index").read_bytes()
    result = await phase()
    assert result.status == "failed"
    assert (work / ".git/index").read_bytes() == index
    assert all((work / p).read_bytes() == data for p, data in prepared.files)
    assert (work / ".tmp/insights-publication/journal.json").exists()
