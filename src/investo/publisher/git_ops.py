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

import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Final, Protocol

from investo.publisher.errors import PublisherGitError

# Backoff seconds before each attempt (attempt index 0 = no sleep).
# Mirrors u2's FD R3 schedule so retry behavior is uniform across
# the project.
_BACKOFF_SCHEDULE: Final[tuple[float, ...]] = (0.0, 2.0, 8.0)


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
    return "nothing to commit" in haystack


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

        # Failed step — record stderr + try again (or exhaust).
        last_stderr = result.stderr if result is not None else None
        last_cause = None

    raise PublisherGitError(
        attempt_count=max_attempts,
        last_stderr=last_stderr,
        cause=last_cause,
    )


__all__ = ["GitRunner", "commit_and_push"]
