"""Bounded remote reconciliation for the existing Git publisher (E11).

The orchestrator owns file/index rollback and private receipt storage. This
module never restores files after a commit or guesses that a failed push
means the remote did not accept it.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import time
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from investo._internal.redaction import RedactionPolicy, redact_text
from investo.models.publication import PublicationRequest, PublishReceipt
from investo.publisher.errors import PublisherGitError

if TYPE_CHECKING:
    from investo.publisher.git_ops import GitRunner

PublicationPhase = Literal["pre_commit", "post_commit", "commit_unknown"]
ReceiptSink = Callable[[PublishReceipt], None]
_logger = logging.getLogger("investo.publisher.git_ops")
_BACKOFFS = (0.0, 2.0, 8.0)


class PublicationReceiptError(PublisherGitError):
    """Only ``phase == pre_commit`` permits file/index rollback.

    A post-commit error may be definitely unpublished, but its immutable
    local commit still belongs to this transaction and must be preserved.
    Receipts carry only identifiers; diagnostics use existing redaction.
    """

    def __init__(
        self,
        *,
        receipt: PublishReceipt,
        phase: PublicationPhase,
        receipts: tuple[PublishReceipt, ...],
        attempt_count: int,
        diagnostic: str,
        cause: BaseException | None = None,
    ) -> None:
        clean = redact_text(diagnostic, policy=RedactionPolicy.STRICT)
        super().__init__(attempt_count=attempt_count, last_stderr=clean, cause=cause)
        self.receipt = receipt
        self.phase = phase
        self.receipts = receipts


class _CommandError(Exception):
    pass


class _Commands:
    def __init__(self, runner: GitRunner | None, budget_s: float) -> None:
        self.runner = runner
        self.deadline = time.monotonic() + budget_s

    def remaining(self) -> float:
        value = self.deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError("publication deadline exhausted")
        return value

    def run(self, args: list[str], *, reserve_s: float = 0.0) -> subprocess.CompletedProcess[str]:
        remaining = self.remaining() - reserve_s
        if remaining <= 0:
            raise TimeoutError("publication deadline cannot accommodate recovery reserve")
        if self.runner is None:
            result = subprocess.run(
                args, capture_output=True, text=True, check=False, timeout=remaining
            )
        else:
            result = self.runner(args, capture_output=True, text=True, check=False)
        return result

    def checked(self, args: list[str]) -> str:
        result = self.run(args)
        if result.returncode != 0:
            raise _CommandError(_diagnostic(result))
        return result.stdout


_OPERATION_ERRORS = (OSError, subprocess.TimeoutExpired, _CommandError)


def _diagnostic(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr.strip() + "\n" + result.stdout.strip()).strip() or "Git command failed"


def _sha_at(commands: _Commands, ref: str) -> str:
    value = commands.checked(
        ["git", "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"]
    ).strip()
    if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) is None:
        raise _CommandError("Git did not return a commit object id")
    return value


def _tree_hash(commands: _Commands, sha: str, paths: Sequence[Path]) -> str:
    names = sorted({path.as_posix() for path in paths})
    tree = commands.checked(["git", "--literal-pathspecs", "ls-tree", "-z", sha, "--", *names])
    # Hash Git object identities, never metadata prose. Include absent paths
    # so changing the CAS field set cannot silently match an old baseline.
    canonical = json.dumps([names, sorted(tree.split("\0"))], ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _check_index_scope(commands: _Commands, files: Sequence[Path]) -> None:
    # Git resolves absolute/relative paths itself. NUL separation and disabled
    # rename detection retain both sides of staged renames, even unusual names.
    args = [
        "git",
        "--literal-pathspecs",
        "diff",
        "--cached",
        "--name-only",
        "--no-renames",
        "-z",
        "--",
    ]
    staged = set(commands.checked(args).split("\0"))
    owned = set(commands.checked([*args, *(str(path) for path in files)]).split("\0"))
    if staged - owned:
        raise _CommandError("publication index contains staged paths outside this transaction")


def metadata_hash_at(
    ref: str,
    metadata_paths: Sequence[Path],
    *,
    runner: GitRunner | None = None,
    total_budget_s: float = 10.0,
) -> str:
    """Hash metadata at a fixed local Git tree, without fetching/writing.

    Resolve the remote baseline once in the caller and pass its SHA here;
    using the working tree would include the new uncommitted publication.
    Missing files are a valid baseline. Git read failures are explicit.
    """
    validated = PublicationRequest(
        run_id="baseline",
        baseline_metadata_hash="0" * 64,
        metadata_paths=tuple(metadata_paths),
        total_budget_s=total_budget_s,
    )
    commands = _Commands(runner, validated.total_budget_s)
    try:
        return _tree_hash(commands, _sha_at(commands, ref), validated.metadata_paths)
    except _OPERATION_ERRORS as exc:
        raise PublisherGitError(
            attempt_count=0,
            last_stderr=redact_text(str(exc), policy=RedactionPolicy.STRICT),
            cause=exc,
        ) from exc


def _observe_remote(
    commands: _Commands,
    request: PublicationRequest,
    receipt: PublishReceipt,
    tracking_ref: str,
) -> tuple[bool, str, str | None]:
    commands.checked(
        ["git", "fetch", "--no-tags", "origin", f"+{request.remote_ref}:{tracking_ref}"]
    )
    remote_sha = _sha_at(commands, tracking_ref)
    ancestry = commands.run(
        ["git", "merge-base", "--is-ancestor", str(receipt.local_sha), remote_sha]
    )
    if ancestry.returncode == 0:
        return True, remote_sha, None
    if ancestry.returncode != 1:
        raise _CommandError(_diagnostic(ancestry))
    shallow = commands.checked(["git", "rev-parse", "--is-shallow-repository"]).strip()
    if shallow != "false":
        raise _CommandError("remote non-ancestry cannot be established in a shallow repository")
    return False, remote_sha, _tree_hash(commands, remote_sha, request.metadata_paths)


def reconcile_publication(
    receipt: PublishReceipt,
    *,
    runner: GitRunner | None = None,
    total_budget_s: float = 10.0,
) -> PublishReceipt:
    """Observe a retained transaction, without add/commit/push/rebase.

    Unlike ``commit_and_push``, this is a status query: callers MUST inspect
    the returned status. Unknown confirmation never licenses rollback or
    consumption as a new run's baseline. At most two remote fetches occur.
    """
    request = PublicationRequest(
        run_id=receipt.run_id,
        baseline_metadata_hash=receipt.baseline_metadata_hash,
        remote_ref=receipt.remote_ref,
        total_budget_s=total_budget_s,
    )
    if receipt.local_sha is None:
        return replace(receipt, status="outcome_unknown")
    commands = _Commands(runner, total_budget_s)
    tracking_ref = "refs/remotes/origin/" + request.remote_ref.removeprefix("refs/heads/")
    for _ in range(2):
        try:
            contains, _, _ = _observe_remote(commands, request, receipt, tracking_ref)
        except _OPERATION_ERRORS:
            continue
        return replace(receipt, status="remote_confirmed" if contains else "definitely_unpublished")
    return replace(receipt, status="outcome_unknown")


def publish_with_receipt(
    message: str,
    files: Sequence[Path],
    *,
    request: PublicationRequest,
    retries: int,
    runner: GitRunner | None,
    receipt_sink: ReceiptSink | None,
) -> PublishReceipt:
    """Opt-in branch of ``commit_and_push``; return only confirmed success.

    At most two post-commit remote reads, with the existing attempt ceiling
    and backoff schedule. Rebase is permitted only with unchanged remote
    metadata and unchanged publication file content. No force push occurs.
    """
    from investo.publisher.git_ops import _is_idempotent_commit_noop

    if retries < 0:
        raise ValueError("retries must be non-negative")
    if not files:
        raise ValueError("publication requires explicit files")
    commands = _Commands(runner, request.total_budget_s)
    tracking_ref = "refs/remotes/origin/" + request.remote_ref.removeprefix("refs/heads/")
    receipt = PublishReceipt(
        run_id=request.run_id,
        local_sha=None,
        remote_ref=request.remote_ref,
        baseline_metadata_hash=request.baseline_metadata_hash,
        status="definitely_unpublished",
    )
    history: list[PublishReceipt] = []
    phase: PublicationPhase = "pre_commit"
    attempt_count = 0

    def fail(diagnostic: str, cause: BaseException | None = None) -> PublicationReceiptError:
        clean = redact_text(diagnostic, policy=RedactionPolicy.STRICT)
        _logger.error("[git_ops] publication %s: %s", receipt.status, clean[:500])
        return PublicationReceiptError(
            receipt=receipt,
            phase=phase,
            receipts=tuple(history),
            attempt_count=attempt_count,
            diagnostic=clean,
            cause=cause,
        )

    def record(value: PublishReceipt) -> None:
        nonlocal receipt
        receipt = value
        history.append(value)
        if receipt_sink is not None:
            try:
                receipt_sink(value)
            except Exception as exc:
                if value.status == "remote_confirmed":
                    # Remote ancestry is authoritative even if private storage
                    # becomes unavailable. Do not log sink exception contents.
                    _logger.warning(
                        "[git_ops] remote publication confirmed; "
                        "private receipt persistence degraded"
                    )
                    return
                raise fail("private publication receipt could not be persisted", exc) from exc

    def pause(attempt: int) -> None:
        if attempt and attempt < len(_BACKOFFS):
            delay = _BACKOFFS[attempt]
            if commands.remaining() <= delay:
                raise TimeoutError("publication deadline cannot accommodate retry")
            time.sleep(delay)

    try:
        initial_head = _sha_at(commands, "HEAD")
        baseline = _sha_at(commands, tracking_ref)
        if _tree_hash(commands, baseline, request.metadata_paths) != request.baseline_metadata_hash:
            raise fail("publication metadata baseline changed; regenerate from remote")
        ancestry = commands.run(["git", "merge-base", "--is-ancestor", initial_head, baseline])
        if ancestry.returncode != 0:
            raise fail("publication must start from the remote baseline, not pending local history")
        _check_index_scope(commands, files)
    except _OPERATION_ERRORS as exc:
        raise fail(str(exc), exc) from exc

    # Once committed, never run add/commit again. Retries push the same
    # immutable transaction (or a content-preserving successor rebase).
    for attempt in range(retries + 1):
        attempt_count = attempt + 1
        try:
            pause(attempt)
            _check_index_scope(commands, files)
            commands.checked(["git", "add", "--", *(str(path) for path in files)])
            _check_index_scope(commands, files)
        except _OPERATION_ERRORS as exc:
            if attempt == retries:
                raise fail(str(exc), exc) from exc
            continue
        commit_error: BaseException | None = None
        try:
            committed = commands.run(["git", "commit", "-m", message])
        except _OPERATION_ERRORS as exc:
            commit_error = exc
            committed = None
        try:
            local_sha = _sha_at(commands, "HEAD")
        except _OPERATION_ERRORS as exc:
            phase = "commit_unknown"
            record(replace(receipt, status="outcome_unknown"))
            raise fail("commit result could not be established", exc) from exc
        commit_ok = committed is not None and (
            committed.returncode == 0 or _is_idempotent_commit_noop(committed)
        )
        if local_sha != initial_head or commit_ok:
            phase = "post_commit"
            record(replace(receipt, local_sha=local_sha, status="pending"))
            try:
                content_hash = _tree_hash(commands, local_sha, files)
            except _OPERATION_ERRORS as exc:
                raise fail("committed publication content could not be verified", exc) from exc
            record(replace(receipt, content_hash=content_hash))
            break
        if attempt == retries:
            diagnostic = (
                str(commit_error)
                if commit_error
                else _diagnostic(committed)
                if committed
                else "commit failed"
            )
            raise fail(diagnostic, commit_error)

    # Two confirmation observations bound both remote I/O and uncertain
    # outcomes; the ordinary retries parameter remains an upper limit.
    confirmations = min(2, retries + 2 - attempt_count)
    for observation in range(confirmations):
        attempt_count += int(observation > 0)
        try:
            if observation:
                pause(attempt_count - 1)
            # Even a successful push requires ancestry confirmation. A
            # failed/raised push may already have changed the remote.
            with suppress(*_OPERATION_ERRORS):
                commands.run(["git", "push", "origin", f"HEAD:{request.remote_ref}"])
            try:
                contains, remote_sha, remote_hash = _observe_remote(
                    commands, request, receipt, tracking_ref
                )
            except _OPERATION_ERRORS as exc:
                record(replace(receipt, status="outcome_unknown"))
                # An unknown outcome must be reconciled, never blindly
                # pushed or rebased again. There is no extra retry pool.
                if observation == 0 and confirmations > 1:
                    try:
                        contains, remote_sha, remote_hash = _observe_remote(
                            commands, request, receipt, tracking_ref
                        )
                    except _OPERATION_ERRORS as second:
                        raise fail(
                            "remote publication confirmation unavailable", second
                        ) from second
                    if contains:
                        record(replace(receipt, status="remote_confirmed"))
                        return receipt
                    record(replace(receipt, status="definitely_unpublished"))
                    raise fail(
                        "publication absent from remote; retry from retained transaction"
                    ) from None
                raise fail("remote publication confirmation unavailable", exc) from exc
            if contains:
                record(replace(receipt, status="remote_confirmed"))
                return receipt
            record(replace(receipt, status="definitely_unpublished"))
            if remote_hash != request.baseline_metadata_hash:
                raise fail("remote publication metadata changed; regenerate from remote")
            if observation == confirmations - 1:
                raise fail("publication is not present on the remote")
            # Fetch has established both non-ancestry and the metadata CAS.
            # Only the one publication commit may be rebased, not unrelated
            # pending commits from an earlier run.
            parent = commands.checked(["git", "rev-parse", f"{receipt.local_sha}^"]).strip()
            if parent != initial_head:
                raise fail("publication contains unexpected local history")
            # Keep recovery inside the original deadline. A command timeout
            # can leave a real rebase in progress, or lose a successful result.
            cleanup_reserve = min(5.0, request.total_budget_s / 2)
            if commands.remaining() <= cleanup_reserve:
                raise fail("publication deadline cannot accommodate rebase recovery")
            try:
                rebase = commands.run(
                    ["git", "rebase", "--onto", remote_sha, initial_head],
                    reserve_s=cleanup_reserve,
                )
                if rebase.returncode != 0:
                    raise _CommandError(_diagnostic(rebase))
            except _OPERATION_ERRORS as exc:
                # An abort failure may mean rebase already completed. Inspect
                # HEAD before selecting the retained immutable receipt.
                aborted = False
                with suppress(*_OPERATION_ERRORS):
                    aborted = (
                        commands.run(
                            ["git", "rebase", "--abort"], reserve_s=cleanup_reserve / 2
                        ).returncode
                        == 0
                    )
                try:
                    recovered_sha = _sha_at(commands, "HEAD")
                    if recovered_sha == receipt.local_sha:
                        if not aborted:
                            raise _CommandError("rebase abort could not be confirmed")
                    else:
                        recovered_hash = _tree_hash(commands, recovered_sha, files)
                        recovered_parent = commands.checked(
                            ["git", "rev-parse", f"{recovered_sha}^"]
                        ).strip()
                        if recovered_hash != content_hash or recovered_parent != remote_sha:
                            raise _CommandError(
                                "rebase recovery did not establish publication HEAD"
                            )
                        record(
                            replace(
                                receipt,
                                local_sha=recovered_sha,
                                content_hash=recovered_hash,
                                status="pending" if aborted else "outcome_unknown",
                            )
                        )
                except _OPERATION_ERRORS:
                    record(replace(receipt, status="outcome_unknown"))
                    raise fail(
                        "rebase recovery could not establish local publication state", exc
                    ) from exc
                raise fail("rebase interrupted; publication commit retained", exc) from exc
            new_sha = _sha_at(commands, "HEAD")
            record(replace(receipt, local_sha=new_sha, content_hash=None, status="pending"))
            new_hash = _tree_hash(commands, new_sha, files)
            record(replace(receipt, local_sha=new_sha, content_hash=new_hash, status="pending"))
            if new_hash != content_hash:
                raise fail("rebase changed publication content; regenerate from remote")
            if (
                _tree_hash(commands, _sha_at(commands, tracking_ref), request.metadata_paths)
                != request.baseline_metadata_hash
            ):
                raise fail("publication metadata changed during rebase")
        except _OPERATION_ERRORS as exc:
            raise fail(str(exc), exc) from exc

    raise AssertionError("publication confirmation loop must return or raise")


__all__ = ["PublicationReceiptError", "ReceiptSink", "metadata_hash_at", "reconcile_publication"]
