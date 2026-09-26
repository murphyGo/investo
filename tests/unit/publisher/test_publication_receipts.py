"""E11 transaction tests with real local Git repositories; no network."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path

import pytest

from investo.models.publication import PublicationRequest, PublishReceipt
from investo.publisher.git_ops import commit_and_push
from investo.publisher.publication_receipts import (
    PublicationReceiptError,
    metadata_hash_at,
    reconcile_publication,
)

_METADATA = Path("archive/_meta/event_receipts.json")
_ARTICLE = Path("archive/article.md")


def _git(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(directory), *args], capture_output=True, text=True, check=False
    )


def _checked(directory: Path, *args: str) -> str:
    result = _git(directory, *args)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@dataclass
class Repository:
    work: Path
    remote: Path
    other: Path
    baseline: str
    request: PublicationRequest

    def head(self) -> str:
        return _checked(self.work, "rev-parse", "HEAD")

    def remote_head(self) -> str:
        return _checked(self.remote, "rev-parse", "refs/heads/main")

    def advance_remote(self, *, metadata: bool = False) -> str:
        _checked(self.other, "fetch", "origin")
        _checked(self.other, "merge", "--ff-only", "origin/main")
        path = _METADATA if metadata else Path("unrelated.md")
        (self.other / path).write_text("remote change\n")
        _checked(self.other, "add", "--", str(path))
        _checked(self.other, "commit", "-m", "remote update")
        _checked(self.other, "push", "origin", "HEAD:refs/heads/main")
        return self.remote_head()

    def runner(
        self,
        hook: Callable[[list[str]], subprocess.CompletedProcess[str] | None] | None = None,
    ) -> tuple[list[list[str]], Callable[..., subprocess.CompletedProcess[str]]]:
        calls: list[list[str]] = []

        def run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            if hook is not None:
                result = hook(args)
                if result is not None:
                    return result
            return _git(self.work, *args[1:])

        return calls, run


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Repository:
    work, remote, other = (tmp_path / name for name in ("work", "remote.git", "other"))
    for directory in (work, remote, other):
        directory.mkdir()
    _checked(remote, "init", "--bare")
    _checked(work, "init", "-b", "main")
    _checked(work, "config", "user.name", "Receipt Test")
    _checked(work, "config", "user.email", "receipt@example.invalid")
    (work / _METADATA).parent.mkdir(parents=True)
    (work / _METADATA).write_text('{"prior":true}\n')
    (work / _ARTICLE).write_text("prior article\n")
    _checked(work, "add", "--", str(_METADATA), str(_ARTICLE))
    _checked(work, "commit", "-m", "baseline")
    _checked(work, "remote", "add", "origin", str(remote))
    _checked(work, "push", "-u", "origin", "main")
    _checked(other, "clone", "--branch", "main", str(remote), ".")
    _checked(other, "config", "user.name", "Other Writer")
    _checked(other, "config", "user.email", "other@example.invalid")
    monkeypatch.chdir(work)
    monkeypatch.setattr("investo.publisher.publication_receipts.time.sleep", lambda _: None)
    baseline = _checked(work, "rev-parse", "HEAD")
    request = PublicationRequest(
        run_id="test-publication", baseline_metadata_hash=metadata_hash_at(baseline, [_METADATA])
    )
    (work / _ARTICLE).write_text("new article\n")
    (work / _METADATA).write_text('{"published_event":"hash-only"}\n')
    return Repository(work, remote, other, baseline, request)


def _publish(repository: Repository, **kwargs: object) -> PublishReceipt:
    receipt = commit_and_push(
        "publish test",
        [_ARTICLE, _METADATA],
        publication=repository.request,
        **kwargs,  # type: ignore[arg-type]
    )
    assert receipt is not None
    return receipt


def _failed(args: list[str], message: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, 1, stdout="", stderr=message)


def test_confirmed_receipt_and_pending_are_immutable(repository: Repository) -> None:
    receipts: list[PublishReceipt] = []
    result = _publish(repository, receipt_sink=receipts.append)
    assert result.status == "remote_confirmed"
    assert result.local_sha == repository.head() == repository.remote_head()
    assert receipts[0].status == "pending"
    assert receipts[-1] == result
    assert result.content_hash is not None
    with pytest.raises(FrozenInstanceError):
        result.status = "pending"  # type: ignore[misc]


def test_metadata_hash_reads_committed_tree_not_working_files(repository: Repository) -> None:
    assert (
        metadata_hash_at(repository.baseline, [_METADATA])
        == repository.request.baseline_metadata_hash
    )
    absent = metadata_hash_at(repository.baseline, [Path("absent.json")])
    assert absent != metadata_hash_at(repository.baseline, [Path("other-absent.json")])


@pytest.mark.parametrize("advance", [False, True])
def test_lost_successful_push_response_and_remote_ancestor(
    repository: Repository, advance: bool
) -> None:
    def hook(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        if args[1] == "push":
            assert _git(repository.work, *args[1:]).returncode == 0
            if advance:
                repository.advance_remote()
            return _failed(args, "connection lost after remote accepted push")
        return None

    calls, runner = repository.runner(hook)
    result = _publish(repository, runner=runner)
    assert result.status == "remote_confirmed"
    assert result.local_sha == repository.head()
    assert (result.local_sha != repository.remote_head()) is advance
    assert sum(args[1] == "push" for args in calls) == 1
    assert not any(args[1] == "rebase" for args in calls)


def test_remote_advancement_rebases_only_same_content(repository: Repository) -> None:
    advanced = False

    def hook(args: list[str]) -> None:
        nonlocal advanced
        if args[1] == "push" and not advanced:
            advanced = True
            repository.advance_remote()

    calls, runner = repository.runner(hook)
    receipts: list[PublishReceipt] = []
    result = _publish(repository, runner=runner, receipt_sink=receipts.append)
    pending = [value for value in receipts if value.status == "pending" and value.content_hash]
    assert len({value.local_sha for value in pending}) == 2
    assert len({value.content_hash for value in pending}) == 1
    assert result.status == "remote_confirmed"
    assert (repository.work / "unrelated.md").read_text() == "remote change\n"
    assert sum(args[1] == "fetch" for args in calls) == 2


def test_changed_remote_metadata_blocks_even_clean_rebase(repository: Repository) -> None:
    advanced = False

    def hook(args: list[str]) -> None:
        nonlocal advanced
        if args[1] == "push" and not advanced:
            advanced = True
            repository.advance_remote(metadata=True)

    calls, runner = repository.runner(hook)
    with pytest.raises(PublicationReceiptError) as caught:
        _publish(repository, runner=runner)
    error = caught.value
    assert error.phase == "post_commit"
    assert error.receipt.status == "definitely_unpublished"
    assert error.receipt.local_sha == repository.head()
    assert error.receipt.local_sha != repository.remote_head()
    assert "metadata changed" in (error.last_stderr or "")
    assert not any(args[1] == "rebase" for args in calls)
    assert (repository.work / _ARTICLE).read_text() == "new article\n"


def test_stale_initial_metadata_prevents_any_mutation(repository: Repository) -> None:
    calls, runner = repository.runner()
    stale = replace(repository.request, baseline_metadata_hash="f" * 64)
    with pytest.raises(PublicationReceiptError) as caught:
        commit_and_push("test", [_ARTICLE, _METADATA], publication=stale, runner=runner)
    assert caught.value.phase == "pre_commit"
    assert caught.value.receipt.local_sha is None
    assert repository.head() == repository.baseline
    assert not any(args[1] in {"add", "commit", "push"} for args in calls)


def test_unrelated_staged_work_is_rejected_without_mutation(repository: Repository) -> None:
    unrelated = Path("private staged\nnote.txt")
    (repository.work / unrelated).write_text("unrelated private work\n")
    _checked(repository.work, "add", "--", str(unrelated), str(_ARTICLE))
    original_index = (repository.work / ".git/index").read_bytes()
    calls, runner = repository.runner()
    with pytest.raises(PublicationReceiptError) as caught:
        _publish(repository, runner=runner)
    assert caught.value.phase == "pre_commit"
    assert caught.value.receipt.local_sha is None
    assert "staged paths outside" in (caught.value.last_stderr or "")
    assert repository.head() == repository.remote_head() == repository.baseline
    assert (repository.work / ".git/index").read_bytes() == original_index
    assert (repository.work / unrelated).read_text() == "unrelated private work\n"
    assert not any(args[1] in {"add", "commit", "push"} for args in calls)


def test_staged_transaction_paths_remain_publishable(repository: Repository) -> None:
    _checked(repository.work, "add", "--", str(_ARTICLE), str(_METADATA))
    assert _publish(repository).status == "remote_confirmed"


def test_metadata_cas_is_checked_again_after_clean_rebase(repository: Repository) -> None:
    advanced = False

    def hook(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        nonlocal advanced
        if args[1] == "push" and not advanced:
            advanced = True
            repository.advance_remote()
        elif args[1:3] == ["rebase", "--onto"]:
            result = _git(repository.work, *args[1:])
            assert result.returncode == 0
            repository.advance_remote(metadata=True)
            _checked(repository.work, "fetch", "origin")
            return result
        return None

    calls, runner = repository.runner(hook)
    with pytest.raises(PublicationReceiptError) as caught:
        _publish(repository, runner=runner)
    assert caught.value.phase == "post_commit"
    assert caught.value.receipt.local_sha == repository.head()
    assert "metadata changed during rebase" in (caught.value.last_stderr or "")
    assert sum(args[1] == "push" for args in calls) == 1


@pytest.mark.parametrize("failure", ["timeout", "oserror"])
def test_interrupted_real_rebase_aborts_and_retains_original_commit(
    repository: Repository, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    now = [0.0]
    monkeypatch.setattr("investo.publisher.publication_receipts.time.monotonic", lambda: now[0])
    original_sha: list[str] = []

    def hook(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        if args[1] == "push":
            original_sha.append(repository.head())
            (repository.other / _ARTICLE).write_text("conflicting remote article\n")
            _checked(repository.other, "add", "--", str(_ARTICLE))
            _checked(repository.other, "commit", "-m", "remote article")
            _checked(repository.other, "push", "origin", "HEAD:refs/heads/main")
        elif args[1:3] == ["rebase", "--onto"]:
            assert _git(repository.work, *args[1:]).returncode != 0
            assert (repository.work / ".git/rebase-merge").is_dir()
            now[0] = 55.0
            if failure == "timeout":
                raise subprocess.TimeoutExpired(args, timeout=55.0)
            raise OSError("rebase response unavailable")
        return None

    calls, runner = repository.runner(hook)
    with pytest.raises(PublicationReceiptError) as caught:
        _publish(repository, runner=runner)
    assert caught.value.phase == "post_commit"
    assert caught.value.receipt.status == "definitely_unpublished"
    assert caught.value.receipt.local_sha == repository.head() == original_sha[0]
    assert repository.head() != repository.remote_head()
    assert not (repository.work / ".git/rebase-merge").exists()
    assert not (repository.work / ".git/rebase-apply").exists()
    assert _checked(repository.work, "status", "--porcelain") == ""
    assert (repository.work / _ARTICLE).read_text() == "new article\n"
    assert sum(args[1:3] == ["rebase", "--abort"] for args in calls) == 1
    assert sum(args[1] == "push" for args in calls) == 1


def test_completed_rebase_lost_response_records_successor_without_repush(
    repository: Repository,
) -> None:
    original_sha: list[str] = []

    def hook(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        if args[1] == "push":
            original_sha.append(repository.head())
            repository.advance_remote()
        elif args[1:3] == ["rebase", "--onto"]:
            assert _git(repository.work, *args[1:]).returncode == 0
            raise subprocess.TimeoutExpired(args, timeout=1.0)
        return None

    calls, runner = repository.runner(hook)
    with pytest.raises(PublicationReceiptError) as caught:
        _publish(repository, runner=runner)
    assert caught.value.phase == "post_commit"
    assert caught.value.receipt.local_sha == repository.head() != original_sha[0]
    assert caught.value.receipt.status == "outcome_unknown"
    assert caught.value.receipt.content_hash is not None
    assert any(receipt.local_sha == original_sha[0] for receipt in caught.value.receipts)
    assert not (repository.work / ".git/rebase-merge").exists()
    assert sum(args[1] == "push" for args in calls) == 1


def test_real_subprocess_rebase_timeout_reserves_cleanup_budget(
    repository: Repository, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = [0.0]
    monkeypatch.setattr("investo.publisher.publication_receipts.time.monotonic", lambda: now[0])
    real_run = subprocess.run
    timeouts: dict[str, float] = {}

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if args[1] == "push":
            (repository.other / _ARTICLE).write_text("remote conflicting article\n")
            _checked(repository.other, "add", "--", str(_ARTICLE))
            _checked(repository.other, "commit", "-m", "remote article")
            _checked(repository.other, "push", "origin", "HEAD:refs/heads/main")
        if args[1] == "rebase":
            timeout = kwargs["timeout"]
            assert isinstance(timeout, float)
            timeouts[args[2]] = timeout
        result = real_run(args, **kwargs)  # type: ignore[call-overload]
        if args[1:3] == ["rebase", "--onto"]:
            assert result.returncode != 0
            assert (repository.work / ".git/rebase-merge").is_dir()
            now[0] = 55.0
            raise subprocess.TimeoutExpired(args, timeout=timeouts["--onto"])
        return result  # type: ignore[no-any-return]

    monkeypatch.setattr("investo.publisher.publication_receipts.subprocess.run", run)
    with pytest.raises(PublicationReceiptError) as caught:
        _publish(repository)
    assert timeouts == {"--onto": 55.0, "--abort": 2.5}
    assert caught.value.phase == "post_commit"
    assert caught.value.receipt.local_sha == repository.head()
    assert caught.value.receipt.status == "definitely_unpublished"
    assert not (repository.work / ".git/rebase-merge").exists()


def test_pending_local_history_is_not_included_in_new_publication(repository: Repository) -> None:
    (repository.work / "pending.md").write_text("unpublished prior transaction\n")
    _checked(repository.work, "add", "--", "pending.md")
    _checked(repository.work, "commit", "-m", "pending other transaction")
    pending = repository.head()
    calls, runner = repository.runner()
    with pytest.raises(PublicationReceiptError) as caught:
        _publish(repository, runner=runner)
    assert caught.value.phase == "pre_commit"
    assert repository.head() == pending
    assert not any(args[1] == "push" for args in calls)


def test_unknown_remote_does_not_return_success_or_repush(repository: Repository) -> None:
    def hook(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        if args[1] == "fetch":
            return _failed(args, "remote unavailable")
        return None

    calls, runner = repository.runner(hook)
    with pytest.raises(PublicationReceiptError) as caught:
        _publish(repository, runner=runner)
    assert caught.value.phase == "post_commit"
    assert caught.value.receipt.status == "outcome_unknown"
    assert repository.head() == repository.remote_head() != repository.baseline
    assert sum(args[1] == "fetch" for args in calls) == 2
    assert sum(args[1] == "push" for args in calls) == 1


def test_confirmation_retry_can_establish_success_without_repush(repository: Repository) -> None:
    fetches = 0

    def hook(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        nonlocal fetches
        if args[1] == "fetch":
            fetches += 1
            if fetches == 1:
                return _failed(args, "temporary remote read failure")
        return None

    calls, runner = repository.runner(hook)
    assert _publish(repository, runner=runner).status == "remote_confirmed"
    assert fetches == 2
    assert sum(args[1] == "push" for args in calls) == 1


def test_retained_receipt_is_reconciled_before_a_new_transaction(repository: Repository) -> None:
    def hook(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        return _failed(args, "remote unavailable") if args[1] == "fetch" else None

    _, unavailable = repository.runner(hook)
    with pytest.raises(PublicationReceiptError) as caught:
        _publish(repository, runner=unavailable)
    pending = caught.value.receipt
    assert pending.status == "outcome_unknown"
    repository.advance_remote()
    calls, available = repository.runner()
    confirmed = reconcile_publication(pending, runner=available)
    assert confirmed.status == "remote_confirmed"
    assert confirmed.local_sha == pending.local_sha
    assert pending.status == "outcome_unknown"
    assert not any(args[1] in {"add", "commit", "push", "rebase"} for args in calls)


def test_confirmed_absence_retains_commit_and_does_not_exceed_retry_limit(
    repository: Repository,
) -> None:
    def hook(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        return _failed(args, "push rejected") if args[1] == "push" else None

    calls, runner = repository.runner(hook)
    with pytest.raises(PublicationReceiptError) as caught:
        _publish(repository, runner=runner, retries=0)
    assert caught.value.receipt.status == "definitely_unpublished"
    assert caught.value.phase == "post_commit"
    assert repository.head() != repository.baseline == repository.remote_head()
    assert sum(args[1] == "push" for args in calls) == 1
    assert sum(args[1] == "fetch" for args in calls) == 1


def test_sink_failure_preserves_pending_commit_before_push(repository: Repository) -> None:
    calls, runner = repository.runner()

    def sink(_receipt: PublishReceipt) -> None:
        raise OSError("private ledger unavailable")

    with pytest.raises(PublicationReceiptError) as caught:
        _publish(repository, runner=runner, receipt_sink=sink)
    assert caught.value.phase == "post_commit"
    assert caught.value.receipt.status == "pending"
    assert repository.head() != repository.baseline
    assert not any(args[1] == "push" for args in calls)


def test_confirmed_sink_failure_keeps_remote_success(
    repository: Repository, caplog: pytest.LogCaptureFixture
) -> None:
    private_error = "private sink payload must not appear in logs"
    receipts: list[PublishReceipt] = []

    def sink(receipt: PublishReceipt) -> None:
        receipts.append(receipt)
        if receipt.status == "remote_confirmed":
            raise OSError(private_error)

    result = _publish(repository, receipt_sink=sink)
    assert result.status == "remote_confirmed"
    assert result.local_sha == repository.head() == repository.remote_head()
    assert receipts[-1] == result
    assert "private receipt persistence degraded" in caplog.text
    assert private_error not in caplog.text


def test_commit_response_loss_is_detected_from_head(repository: Repository) -> None:
    def hook(args: list[str]) -> None:
        if args[1] == "commit":
            assert _git(repository.work, *args[1:]).returncode == 0
            raise OSError("commit response lost")

    _, runner = repository.runner(hook)
    assert _publish(repository, runner=runner).status == "remote_confirmed"


def test_unreadable_head_after_commit_is_unknown_and_never_precommit(
    repository: Repository,
) -> None:
    committed = False

    def hook(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        nonlocal committed
        if args[1] == "commit":
            committed = True
        elif committed and args[1] == "rev-parse":
            return _failed(args, "HEAD unavailable")
        return None

    calls, runner = repository.runner(hook)
    with pytest.raises(PublicationReceiptError) as caught:
        _publish(repository, runner=runner)
    assert caught.value.phase == "commit_unknown"
    assert caught.value.receipt.status == "outcome_unknown"
    assert not any(args[1] == "push" for args in calls)


def test_precommit_failure_has_no_pending_commit(repository: Repository) -> None:
    def hook(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        return _failed(args, "cannot stage") if args[1] == "add" else None

    _, runner = repository.runner(hook)
    with pytest.raises(PublicationReceiptError) as caught:
        _publish(repository, runner=runner, retries=0)
    assert caught.value.phase == "pre_commit"
    assert caught.value.receipt.status == "definitely_unpublished"
    assert caught.value.receipt.local_sha is None
    assert repository.head() == repository.baseline


def test_deadline_after_push_is_unknown_without_more_git_calls(
    repository: Repository, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = [0.0]
    monkeypatch.setattr("investo.publisher.publication_receipts.time.monotonic", lambda: now[0])

    def hook(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        if args[1] == "push":
            result = _git(repository.work, *args[1:])
            now[0] = 100.0
            return result
        return None

    calls, runner = repository.runner(hook)
    with pytest.raises(PublicationReceiptError) as caught:
        _publish(repository, runner=runner)
    assert caught.value.receipt.status == "outcome_unknown"
    assert caught.value.phase == "post_commit"
    assert not any(args[1] == "fetch" for args in calls)
    assert repository.head() == repository.remote_head()


def test_receipt_error_and_logging_redact_command_diagnostics(
    repository: Repository, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "1234567890:AAFakeBotTokenThatLooksLikeARealOneXYZ"

    def hook(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        return _failed(args, f"error {secret}") if args[1] == "add" else None

    _, runner = repository.runner(hook)
    with pytest.raises(PublicationReceiptError) as caught:
        _publish(repository, runner=runner, retries=0)
    assert secret not in (caught.value.last_stderr or "")
    assert secret not in caplog.text
    assert secret not in repr(caught.value.receipt)


def test_retry_ceiling_includes_precommit_failures(repository: Repository) -> None:
    adds = 0

    def hook(args: list[str]) -> subprocess.CompletedProcess[str] | None:
        nonlocal adds
        if args[1] == "add":
            adds += 1
            if adds == 1:
                return _failed(args, "temporary add failure")
        if args[1] == "push":
            return _failed(args, "push failed")
        return None

    calls, runner = repository.runner(hook)
    with pytest.raises(PublicationReceiptError) as caught:
        _publish(repository, runner=runner, retries=1)
    assert caught.value.attempt_count == 2
    assert caught.value.receipt.status == "definitely_unpublished"
    assert sum(args[1] == "push" for args in calls) == 1


def test_dry_run_does_not_read_remote_or_emit_receipt(repository: Repository) -> None:
    calls, runner = repository.runner()
    receipts: list[PublishReceipt] = []
    assert (
        commit_and_push(
            "test",
            [_ARTICLE],
            publication=repository.request,
            runner=runner,
            receipt_sink=receipts.append,
            dry_run=True,
        )
        is None
    )
    assert calls == []
    assert receipts == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("run_id", "unsafe\nidentifier"),
        ("baseline_metadata_hash", "invalid"),
        ("remote_ref", "refs/heads/main:evil"),
        ("remote_ref", "refs/heads/main/../evil"),
        ("metadata_paths", (Path("../outside"),)),
        ("total_budget_s", float("nan")),
    ],
)
def test_publication_request_rejects_unsafe_configuration(field: str, value: object) -> None:
    values: dict[str, object] = {"run_id": "test", "baseline_metadata_hash": "0" * 64, field: value}
    with pytest.raises(ValueError):
        PublicationRequest(**values)  # type: ignore[arg-type]
