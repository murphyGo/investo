"""Tests for ``investo.publisher.git_ops.commit_and_push`` (US-006).

Covered behaviors:

* Happy path — exactly 3 invocations (`add`, `commit`, `push`) on
  the first attempt, with the expected list-form argv.
* Transient retry — push fails on attempt 1, succeeds on attempt 2.
* Exhaustion — all 3 attempts fail → `PublisherGitError` with
  attempt_count=3 + last_stderr context.
* List-form pin — `git_ops.py` source contains no `shell=True` and
  no string-form `subprocess.run("git ...")` (defensive, in addition
  to the repo-wide CI grep from u2 Step 10.1).
* Programmer-error pass-through — a synthetic `TypeError` from the
  runner propagates as-is (NOT wrapped in PublisherGitError).
* OSError wrapping — runner raising OSError counts as a failed
  attempt; on exhaustion the OSError lands in `cause`.
* Backoff — `time.sleep` is called with `[2.0, 8.0]` (no sleep
  before attempt 0) when retries trigger.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from investo.publisher import git_ops
from investo.publisher.errors import PublisherGitError
from investo.publisher.git_ops import commit_and_push

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout="", stderr=stderr)


def _runner_returning(
    outcomes: list[subprocess.CompletedProcess[str]],
) -> tuple[
    list[list[str]],
    Iterator[subprocess.CompletedProcess[str]],
    object,  # callable
]:
    """Build a runner that records every invocation's argv + pops
    canned outcomes in order. Returns the captured-args list (for
    assertions) and the runner callable.
    """
    captured: list[list[str]] = []
    iterator = iter(outcomes)

    def runner(
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        captured.append(args)
        return next(iterator)

    return captured, iterator, runner


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip ``time.sleep`` in git_ops so retry-backoff tests run fast.
    Tests that need to ASSERT on backoff timing override this.
    """
    monkeypatch.setattr(git_ops.time, "sleep", lambda _s: None)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_commit_and_push_happy_path_runs_three_steps_in_order() -> None:
    """First attempt succeeds — exactly 3 invocations, argv shapes
    pin the list-form contract.
    """
    captured, _, runner = _runner_returning([_ok(), _ok(), _ok()])

    commit_and_push(
        "publish 2026-04-25",
        [Path("archive/2026/04/2026-04-25.md")],
        runner=runner,
    )

    assert len(captured) == 3
    assert captured[0] == [
        "git",
        "add",
        "--",
        "archive/2026/04/2026-04-25.md",
    ]
    assert captured[1] == ["git", "commit", "-m", "publish 2026-04-25"]
    assert captured[2] == ["git", "push", "origin", "HEAD"]


def test_commit_and_push_supports_multiple_files() -> None:
    """Multiple paths are joined into a single ``git add`` invocation."""
    captured, _, runner = _runner_returning([_ok(), _ok(), _ok()])

    commit_and_push(
        "msg",
        [Path("a.md"), Path("b.md"), Path("c.md")],
        runner=runner,
    )

    assert captured[0] == ["git", "add", "--", "a.md", "b.md", "c.md"]


# ---------------------------------------------------------------------------
# Transient retry
# ---------------------------------------------------------------------------


def test_commit_and_push_retries_on_transient_push_failure() -> None:
    """Push fails on attempt 1 (returncode=1), all 3 succeed on
    attempt 2. Total = 6 invocations (3 x 2 attempts).
    """
    captured, _, runner = _runner_returning(
        [
            _ok(),
            _ok(),
            _ok(returncode=1, stderr="connection reset"),
            _ok(),
            _ok(),
            _ok(),
        ]
    )

    commit_and_push("msg", [Path("f.md")], runner=runner)

    assert len(captured) == 6


def test_commit_and_push_retries_on_add_step_failure() -> None:
    """First step (`add`) failing also retries — failure can land
    anywhere in the 3-step sequence.
    """
    captured, _, runner = _runner_returning(
        [
            _ok(returncode=128, stderr="fatal: pathspec 'f.md' did not match"),
            _ok(),
            _ok(),
            _ok(),
        ]
    )

    commit_and_push("msg", [Path("f.md")], runner=runner)

    # Attempt 1: 1 failed call. Attempt 2: 3 successes. Total = 4.
    assert len(captured) == 4


# ---------------------------------------------------------------------------
# Exhaustion
# ---------------------------------------------------------------------------


def test_commit_and_push_raises_publisher_git_error_when_all_attempts_fail() -> None:
    """All 3 attempts fail at the push step → PublisherGitError.

    With retries=2 + 3 push failures: 3 attempts x 3 calls/attempt
    where the 3rd call (push) fails = 9 total runner invocations.
    """
    fail_push = _ok(returncode=1, stderr="git: push rejected")
    captured, _, runner = _runner_returning(
        [_ok(), _ok(), fail_push] * 3,
    )

    with pytest.raises(PublisherGitError) as exc:
        commit_and_push("msg", [Path("f.md")], runner=runner)

    assert exc.value.attempt_count == 3
    assert len(captured) == 9
    assert exc.value.last_stderr == "git: push rejected"


def test_commit_and_push_truncates_long_stderr_to_1024_bytes() -> None:
    """A 10 KB stderr from a failing git step is truncated by the
    PublisherGitError class itself to ≤ 1024 UTF-8 bytes (errors.py
    cap mirroring u2 AC-7.4). Pin the cap end-to-end through git_ops.
    """
    big_stderr = "x" * 10_240
    fail = _ok(returncode=1, stderr=big_stderr)
    _, _, runner = _runner_returning([_ok(), _ok(), fail] * 3)

    with pytest.raises(PublisherGitError) as exc:
        commit_and_push("msg", [Path("f.md")], runner=runner)

    assert exc.value.last_stderr is not None
    assert len(exc.value.last_stderr.encode("utf-8")) <= 1024


def test_commit_and_push_zero_retries_means_one_attempt() -> None:
    """``retries=0`` → 1 attempt only; first failure → PublisherGitError
    immediately with attempt_count=1.
    """
    fail = _ok(returncode=1, stderr="boom")
    captured, _, runner = _runner_returning([_ok(), _ok(), fail])

    with pytest.raises(PublisherGitError) as exc:
        commit_and_push("msg", [Path("f.md")], runner=runner, retries=0)

    assert exc.value.attempt_count == 1
    assert len(captured) == 3  # add, commit, fail-push, then stop


# ---------------------------------------------------------------------------
# H1 regression — partial-success retry (commit landed, push failed)
# ---------------------------------------------------------------------------


def test_commit_and_push_handles_partial_success_on_retry() -> None:
    """H1 regression — Step 8 sub-agent review.

    Scenario: attempt 1 succeeds at `add` + `commit`, fails at `push`.
    On the retry, `git commit` returns rc=1 with "nothing to commit,
    working tree clean" because the prior commit already absorbed the
    staged changes. The retry must treat this as a no-op success and
    proceed to the `push` step (which now succeeds), NOT exhaust the
    retry budget with a misleading "publish failed entirely" alert.

    Trace:
      attempt 1: add(rc=0) → commit(rc=0) → push(rc=1, fail) → record
      attempt 2: add(rc=0) → commit(rc=1, "nothing to commit") → push(rc=0)
    Total = 6 invocations; commit_and_push returns normally.
    """
    nothing_to_commit = subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout="",
        stderr="nothing to commit, working tree clean",
    )
    captured, _, runner = _runner_returning(
        [
            _ok(),  # attempt 1: add
            _ok(),  # attempt 1: commit (succeeds)
            _ok(returncode=1, stderr="connection reset"),  # attempt 1: push fails
            _ok(),  # attempt 2: add
            nothing_to_commit,  # attempt 2: commit (no-op success)
            _ok(),  # attempt 2: push (succeeds)
        ]
    )

    # Must NOT raise — partial-success retry recovers.
    commit_and_push("publish 2026-04-25", [Path("f.md")], runner=runner)

    assert len(captured) == 6


def test_commit_and_push_treats_nothing_to_commit_stdout_as_noop() -> None:
    """Some git versions print "nothing to commit" to stdout instead of
    stderr. `_is_idempotent_commit_noop` checks both streams.
    """
    noop_via_stdout = subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout="On branch main\nnothing to commit, working tree clean\n",
        stderr="",
    )
    captured, _, runner = _runner_returning(
        [_ok(), noop_via_stdout, _ok()],
    )

    commit_and_push("msg", [Path("f.md")], runner=runner)

    assert len(captured) == 3


def test_commit_and_push_does_not_silently_pass_real_commit_failures() -> None:
    """A `git commit` rc=1 with stderr that does NOT contain "nothing
    to commit" remains a real failure (e.g., hook rejected, disk full).
    The idempotent-noop detection must not regress to swallowing
    legitimate failures.
    """
    real_failure = subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout="",
        stderr="error: pathspec 'f.md' did not match any files\n",
    )
    _, _, runner = _runner_returning(
        [_ok(), real_failure] * 3,
    )

    with pytest.raises(PublisherGitError) as exc:
        commit_and_push("msg", [Path("f.md")], runner=runner)

    assert exc.value.attempt_count == 3
    assert exc.value.last_stderr is not None
    assert "did not match" in exc.value.last_stderr


# ---------------------------------------------------------------------------
# Programmer-error pass-through
# ---------------------------------------------------------------------------


def test_commit_and_push_propagates_typeerror_unwrapped() -> None:
    """A synthetic TypeError from the runner propagates as-is — it
    represents a programmer mistake, not a transient git failure.
    Caller (orchestrator) handles it as a separate alert class.
    """

    def boom(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise TypeError("synthetic programmer error")

    with pytest.raises(TypeError, match="synthetic programmer error"):
        commit_and_push("msg", [Path("f.md")], runner=boom)


def test_commit_and_push_wraps_oserror_into_publisher_git_error() -> None:
    """OSError (e.g., 'git binary not found') counts as a failed
    attempt and triggers retry. On exhaustion, the OSError lands in
    ``cause`` so operators can diagnose the system-level problem.
    """

    def boom(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("git: command not found")

    with pytest.raises(PublisherGitError) as exc:
        commit_and_push("msg", [Path("f.md")], runner=boom, retries=1)

    assert exc.value.attempt_count == 2
    assert isinstance(exc.value.cause, OSError)
    assert "git: command not found" in (exc.value.last_stderr or "")


# ---------------------------------------------------------------------------
# List-form pin (defensive)
# ---------------------------------------------------------------------------


def test_git_ops_module_uses_only_list_form_subprocess() -> None:
    """The executable AST of ``git_ops`` does NOT contain ``shell=True``
    or string-form ``subprocess.run("git ...")``. Stripping docstrings
    + comments via AST round-trip avoids false positives from this
    file's prose (which intentionally mentions the forbidden patterns).

    Belt-and-braces with the repo-wide CI grep from u2 Step 10.1
    (``scripts/check_no_anthropic_sdk.py``).
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(git_ops))

    def _strip_docstring(body: list[ast.stmt]) -> None:
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body.pop(0)

    _strip_docstring(tree.body)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            _strip_docstring(node.body)
    executable = ast.unparse(tree)

    assert "shell=True" not in executable
    assert "shell = True" not in executable
    assert 'subprocess.run("git' not in executable
    assert "subprocess.run('git" not in executable


# ---------------------------------------------------------------------------
# Backoff schedule
# ---------------------------------------------------------------------------


def test_commit_and_push_respects_backoff_schedule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When retries trigger, ``time.sleep`` is called with the
    ``_BACKOFF_SCHEDULE`` values BEFORE each retry attempt. Attempt 0
    has no preceding sleep.
    """
    sleeps: list[float] = []
    monkeypatch.setattr(git_ops.time, "sleep", lambda s: sleeps.append(s))

    fail = _ok(returncode=1, stderr="boom")
    _, _, runner = _runner_returning([_ok(), _ok(), fail] * 3)

    with pytest.raises(PublisherGitError):
        commit_and_push("msg", [Path("f.md")], runner=runner)

    # Attempt 0: no sleep. Attempts 1 + 2: sleep(2.0) and sleep(8.0).
    assert sleeps == [2.0, 8.0]


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def test_git_ops_module_exports_expected_names() -> None:
    assert hasattr(git_ops, "commit_and_push")
    assert hasattr(git_ops, "GitRunner")
