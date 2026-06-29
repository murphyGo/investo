"""Git commit + push for the publisher (US-006 영구 보관).

The whole-pipeline retry shape mirrors u2's FD R3 retry loop:
``add → commit → push`` runs as a single transaction and is retried
end-to-end on any failure. ``git commit`` is idempotent when the
working tree matches a prior commit — there's no risk of duplicate
commits from a "commit succeeded but push failed" partial state.

Subprocess invocations use **list form** with no ``shell=True`` (per
NFR-007 AC-7.1 / AC-7.6, repo-wide CI-pinned by
``scripts/check_no_anthropic_sdk.py`` from u2 Step 10.1).

Reference:
    docs/requirements.md US-006, NFR-003 (retry contract)
    aidlc-docs/inception/application-design/component-methods.md
        — `commit_and_push(message, files, *, retries=2) -> None`
"""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Final, Protocol

from investo._internal.redaction import RedactionPolicy, redact_text
from investo.publisher.errors import PublisherGitError

_logger = logging.getLogger("investo.publisher.git_ops")

# Cap the operator-log excerpt of the final git stderr. 500 chars is
# enough for the first 3-4 git error lines (the diagnostic anchor) while
# bounding log noise on multi-MB stderr from a misconfigured remote.
_FINAL_STDERR_LOG_LIMIT: Final[int] = 500

# Backoff seconds before each attempt (attempt index 0 = no sleep).
# Mirrors u2's FD R3 schedule so retry behavior is uniform across
# the project.
_BACKOFF_SCHEDULE: Final[tuple[float, ...]] = (0.0, 2.0, 8.0)

_PUSH_REJECTION_MARKERS: Final[tuple[str, ...]] = (
    "failed to push some refs",
    "fetch first",
    "non-fast-forward",
    "updates were rejected",
)


class GitRunner(Protocol):
    """Test-seam protocol matching the slice of ``subprocess.run`` we
    care about. Production uses ``_default_runner`` which delegates
    to the real ``subprocess.run``; tests inject a fake to avoid
    spawning ``git`` in unit-test contexts.
    """

    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]: ...


def _default_runner(
    args: list[str],
    *,
    capture_output: bool,
    text: bool,
    check: bool,
) -> subprocess.CompletedProcess[str]:
    """Production runner — delegates to ``subprocess.run`` with the
    list-form args + no ``shell=True``. ``check=False`` so the caller
    decides retry vs. raise based on ``returncode``.
    """
    return subprocess.run(
        args,
        capture_output=capture_output,
        text=text,
        check=check,
    )


def _is_idempotent_commit_noop(result: subprocess.CompletedProcess[str]) -> bool:
    """Detect ``git commit`` returning rc=1 because the working tree
    is clean (i.e., the same commit already landed in a prior retry
    attempt; only the subsequent ``push`` step is what we really
    need to retry).

    Without this check, the retry loop on a "commit succeeded, push
    failed" partial state would infinite-loop on rc=1 / "nothing to
    commit" until the budget exhausts, and raise ``PublisherGitError``
    with a misleading ``last_stderr`` even though the local commit
    DID land. Operator alert would mis-route as "publish failed
    entirely" when the truth is "commit landed, push needs retry".

    Match is case-insensitive substring on stderr OR stdout (git
    versions vary which stream the message lands on).
    """
    if result.returncode == 0:
        return False
    haystack = (result.stderr + "\n" + result.stdout).lower()
    return any(
        marker in haystack
        for marker in (
            "nothing to commit",
            "nothing added to commit",
            "no changes added to commit",
        )
    )


def _git_diagnostic_output(result: subprocess.CompletedProcess[str]) -> str | None:
    """Return the subprocess diagnostic text worth surfacing to operators.

    Git is inconsistent about whether commit diagnostics land on stderr
    or stdout. Preserve both streams when present so Actions logs and
    operator alerts explain stdout-only failures such as untracked-file
    no-op commits.
    """
    stderr = result.stderr.strip()
    stdout = result.stdout.strip()
    if stderr and stdout:
        return f"{stderr}\n{stdout}"
    return stderr or stdout or None


def _is_recoverable_remote_ahead_push(result: subprocess.CompletedProcess[str] | None) -> bool:
    """Detect a push rejection caused by ``origin/main`` advancing.

    The publisher may run for a long time before committing. If another
    workflow lands a commit meanwhile, the generated briefing commit is
    still valid but must be replayed on top of the newer remote head.
    """
    if result is None or result.returncode == 0:
        return False
    haystack = (result.stderr + "\n" + result.stdout).lower()
    return any(marker in haystack for marker in _PUSH_REJECTION_MARKERS)


def _try_rebase_onto_origin_main(runner: GitRunner) -> subprocess.CompletedProcess[str] | None:
    """Fetch ``origin`` and rebase the local publish commit onto ``origin/main``.

    Returns ``None`` on success. On failure, returns the failed git result
    so the retry loop can surface the actionable diagnostic. A failed
    rebase is aborted before returning to leave the checkout reusable.
    """
    fetch_result = runner(
        ["git", "fetch", "origin"],
        capture_output=True,
        text=True,
        check=False,
    )
    if fetch_result.returncode != 0:
        return fetch_result

    rebase_result = runner(
        ["git", "rebase", "origin/main"],
        capture_output=True,
        text=True,
        check=False,
    )
    if rebase_result.returncode == 0:
        return None

    runner(
        ["git", "rebase", "--abort"],
        capture_output=True,
        text=True,
        check=False,
    )
    return rebase_result


def _try_attempt(
    runner: GitRunner,
    message: str,
    files: Sequence[Path],
) -> subprocess.CompletedProcess[str]:
    """Run one full ``add → commit → push`` sequence.

    Returns the final ``CompletedProcess`` (the ``push`` step) on
    success. Returns the FAILING ``CompletedProcess`` on the first
    non-zero return — the caller inspects ``stderr`` for diagnostic
    context.

    A ``git commit`` rc=1 with "nothing to commit, working tree clean"
    is treated as a no-op success (the partial-success retry case)
    and the loop proceeds to the ``push`` step.
    """
    add_args = ["git", "add", "--", *(str(p) for p in files)]
    commit_args = ["git", "commit", "-m", message]
    push_args = ["git", "push", "origin", "HEAD"]

    # Step 1 — add. Idempotent: re-staging an already-staged file
    # is a no-op and rc=0.
    result = runner(add_args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return result

    # Step 2 — commit. rc=1 with "nothing to commit" is a no-op
    # success when retrying after a successful prior commit.
    result = runner(commit_args, capture_output=True, text=True, check=False)
    if result.returncode != 0 and not _is_idempotent_commit_noop(result):
        return result

    # Step 3 — push.
    return runner(push_args, capture_output=True, text=True, check=False)


def commit_and_push(
    message: str,
    files: Sequence[Path],
    *,
    retries: int = 2,
    runner: GitRunner | None = None,
    dry_run: bool = False,
) -> None:
    """Run ``git add → git commit → git push origin HEAD`` with
    whole-pipeline retry.

    Up to ``retries + 1`` attempts; default = 3 attempts (1 initial
    + 2 retries) with the FD R3 backoff schedule (0, 2, 8 seconds
    BEFORE each attempt — first attempt sleeps 0).

    Parameters
    ----------
    message:
        Commit message passed verbatim to ``git commit -m``.
    files:
        Paths to stage. Each is ``str(path)``-formatted into the
        ``git add`` argv. ``--`` precedes the file list to separate
        flags from paths defensively.
    retries:
        Number of retries AFTER the first attempt. ``0`` = no retry.
    runner:
        Test seam. ``None`` → ``_default_runner`` (real subprocess).

    Raises
    ------
    PublisherGitError:
        All ``retries + 1`` attempts failed. ``last_stderr`` is the
        stderr from the final failed step (1024-byte UTF-8 truncated
        by the error class itself); ``cause`` holds the originating
        exception when one is raised, or ``None`` for non-zero-rc
        failures.
    """
    if dry_run:
        # u31 Step 2 — operator-rehearsal mode. The archive files have
        # already been written to disk by ``write_briefing`` /
        # ``_stage_publish_segments``; skipping the git commit + push
        # leaves the working tree dirty so the operator can inspect
        # what *would* have been committed without polluting origin
        # history.
        return

    actual_runner = runner if runner is not None else _default_runner

    last_stderr: str | None = None
    last_cause: BaseException | None = None
    max_attempts = retries + 1

    for attempt in range(max_attempts):
        if attempt > 0 and attempt < len(_BACKOFF_SCHEDULE):
            time.sleep(_BACKOFF_SCHEDULE[attempt])

        try:
            result = _try_attempt(actual_runner, message, files)
        except OSError as exc:
            last_cause = exc
            last_stderr = str(exc)
            continue

        if result is not None and result.returncode == 0:
            return

        # Failed step — record git's diagnostic output + try again (or exhaust).
        last_stderr = _git_diagnostic_output(result) if result is not None else None
        last_cause = None
        if attempt < max_attempts - 1 and _is_recoverable_remote_ahead_push(result):
            try:
                rebase_result = _try_rebase_onto_origin_main(actual_runner)
            except OSError as exc:
                last_cause = exc
                last_stderr = str(exc)
                continue
            if rebase_result is not None:
                last_stderr = _git_diagnostic_output(rebase_result)
                last_cause = None

    # 2026-05-09 GHA postmortem — surface the final git stderr at ERROR
    # level so operator log triage doesn't have to dig into the alert
    # payload to see why publish exhausted retries. STRICT redaction
    # scrubs any token / URL-embedded credential the remote may echo
    # back (R13). The first 500 chars hold git's diagnostic anchor.
    if last_stderr:
        excerpt = redact_text(last_stderr, policy=RedactionPolicy.STRICT)[:_FINAL_STDERR_LOG_LIMIT]
        _logger.error(
            "[git_ops] commit_and_push exhausted %d attempts; final stderr (redacted): %s",
            max_attempts,
            excerpt,
        )

    raise PublisherGitError(
        attempt_count=max_attempts,
        last_stderr=last_stderr,
        cause=last_cause,
    )


__all__ = ["GitRunner", "commit_and_push"]
