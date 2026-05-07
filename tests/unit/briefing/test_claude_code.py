"""Tests for ``briefing.claude_code`` (FD R2/R3/L4/E5; NFR AC-1.5/2.5/7.1/7.2)."""

from __future__ import annotations

import re
import subprocess

import pytest

from investo.briefing import claude_code as cc
from investo.briefing.claude_code import (
    DEFAULT_TIMEOUT_S,
    DEFAULT_TOTAL_BUDGET_S,
    ClaudeRunner,
    RetryBudget,
    call_claude_code,
)
from investo.briefing.errors import BriefingGenerationError, SubprocessOutcome
from tests._helpers.ast_helpers import executable_source

# --- RetryBudget ------------------------------------------------------------


def test_retry_budget_default_state() -> None:
    budget = RetryBudget()
    assert budget.total_budget_s == DEFAULT_TOTAL_BUDGET_S
    assert budget.elapsed_s == 0.0


def test_retry_budget_record_accumulates() -> None:
    budget = RetryBudget(total_budget_s=300.0)
    budget.record(120.0)
    assert budget.elapsed_s == 120.0
    budget.record(30.0)
    assert budget.elapsed_s == 150.0


def test_would_exceed_below_threshold() -> None:
    budget = RetryBudget(total_budget_s=300.0)
    budget.record(120.0)  # 120 / 300 used
    # next attempt of 60 s → 180 / 300 — not exceeded
    assert budget.would_exceed(60.0) is False


def test_would_exceed_at_threshold_inclusive() -> None:
    budget = RetryBudget(total_budget_s=300.0)
    budget.record(240.0)  # 240 / 300 used
    # next attempt of 60 s → 300 — equality counts as exceeded
    assert budget.would_exceed(60.0) is True


def test_would_exceed_above_threshold() -> None:
    budget = RetryBudget(total_budget_s=300.0)
    budget.record(280.0)
    assert budget.would_exceed(60.0) is True  # 340 > 300


def test_check_or_raise_does_not_raise_when_under_budget() -> None:
    budget = RetryBudget(total_budget_s=300.0)
    budget.record(150.0)
    budget.check_or_raise(stage="classification")  # no raise


def test_check_or_raise_raises_at_threshold() -> None:
    budget = RetryBudget(total_budget_s=300.0)
    budget.record(300.0)  # equality triggers
    with pytest.raises(BriefingGenerationError) as excinfo:
        budget.check_or_raise(stage="synthesis")
    assert excinfo.value.stage == "budget"
    assert excinfo.value.last_stderr is None


def test_check_or_raise_raises_when_over_budget() -> None:
    budget = RetryBudget(total_budget_s=300.0)
    budget.record(400.0)
    with pytest.raises(BriefingGenerationError):
        budget.check_or_raise(stage="classification")


# --- call_claude_code with injected runner ----------------------------------


def _fake_runner_returning(
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> ClaudeRunner:
    """Build a runner that returns a canned ``CompletedProcess``."""

    def runner(
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        # Verify the wrapper passes through the expected args shape.
        assert args[0] == "claude"
        assert args[1] == "-p"
        assert input is not None
        assert capture_output is True
        assert text is True
        assert timeout > 0
        return subprocess.CompletedProcess(
            args=args, returncode=returncode, stdout=stdout, stderr=stderr
        )

    return runner


@pytest.mark.asyncio
async def test_call_claude_code_returns_outcome_on_success() -> None:
    runner = _fake_runner_returning(stdout="hello", stderr="warn", returncode=0)
    outcome = await call_claude_code("prompt body", runner=runner)

    assert isinstance(outcome, SubprocessOutcome)
    assert outcome.stdout == "hello"
    assert outcome.stderr == "warn"
    assert outcome.returncode == 0
    assert outcome.elapsed_s >= 0.0


@pytest.mark.asyncio
async def test_call_claude_code_does_not_raise_on_nonzero_returncode() -> None:
    """FD R3 — non-zero returncode is surfaced via outcome, not raised.
    The caller's retry loop decides whether to retry.
    """
    runner = _fake_runner_returning(stdout="", stderr="oops", returncode=1)
    outcome = await call_claude_code("prompt", runner=runner)
    assert outcome.returncode == 1
    assert outcome.stderr == "oops"


@pytest.mark.asyncio
async def test_call_claude_code_passes_prompt_through() -> None:
    """The exact prompt string is passed via stdin, not argv."""
    captured: list[str] = []
    captured_input: list[str | None] = []

    def capturing_runner(
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        captured.extend(args)
        captured_input.append(input)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    await call_claude_code("PROMPT-BODY-CONTENT", runner=capturing_runner)
    assert captured == ["claude", "-p"]
    assert captured_input == ["PROMPT-BODY-CONTENT"]


@pytest.mark.asyncio
async def test_call_claude_code_uses_default_timeout() -> None:
    """When ``timeout_s`` is omitted, default is ``DEFAULT_TIMEOUT_S``."""
    captured_timeout: list[float] = []

    def capturing_runner(
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        captured_timeout.append(timeout)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    await call_claude_code("p", runner=capturing_runner)
    assert captured_timeout == [DEFAULT_TIMEOUT_S]


@pytest.mark.asyncio
async def test_call_claude_code_propagates_custom_timeout() -> None:
    captured_timeout: list[float] = []

    def capturing_runner(
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        captured_timeout.append(timeout)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    await call_claude_code("p", timeout_s=5.0, runner=capturing_runner)
    assert captured_timeout == [5.0]


@pytest.mark.asyncio
async def test_call_claude_code_wraps_timeout_expired() -> None:
    """``subprocess.TimeoutExpired`` becomes a SubprocessOutcome with
    returncode=124 and stderr containing 'timeout' — the caller
    treats this as a failure for retry purposes (FD R3) without
    needing exception-handling discipline.
    """

    def timing_out_runner(
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=args, timeout=timeout)

    outcome = await call_claude_code("prompt", timeout_s=2.5, runner=timing_out_runner)
    assert outcome.returncode == 124
    assert "timeout" in outcome.stderr.lower()
    assert "2.5" in outcome.stderr  # the timeout value lands in the message
    assert outcome.stdout == ""


@pytest.mark.asyncio
async def test_call_claude_code_does_not_block_event_loop() -> None:
    """``asyncio.to_thread`` ensures the event loop stays responsive
    while the runner is "thinking". Use a runner that sleeps briefly;
    schedule a parallel coroutine and verify both make progress
    concurrently.
    """
    import asyncio
    import time

    async def parallel_marker() -> str:
        await asyncio.sleep(0.05)
        return "parallel-done"

    def slow_runner(
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        time.sleep(0.1)  # blocks the thread, NOT the event loop
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok", stderr="")

    start = asyncio.get_event_loop().time()
    outcome, marker = await asyncio.gather(
        call_claude_code("p", runner=slow_runner),
        parallel_marker(),
    )
    elapsed = asyncio.get_event_loop().time() - start

    assert outcome.stdout == "ok"
    assert marker == "parallel-done"
    # Concurrent execution: total elapsed should be ~0.1 s. Serial
    # would be ~0.15 s. Margin of 0.25 — far enough above 0.10 to be
    # meaningful and below 0.15 + jitter to detect serialization, but
    # generous enough for CI thread-scheduling jitter (Step 6 review
    # M2 — bumped from 0.18 to 0.25).
    assert elapsed < 0.25, (
        f"call_claude_code blocked the event loop ({elapsed:.3f}s for 0.1+0.05 concurrent work)"
    )


# --- Source self-checks (AC-2.5, AC-7.1, AC-7.2, AC-7.6) -------------------


def test_source_has_no_oauth_token_literal() -> None:
    """AC-2.5 / AC-7.2 — ``CLAUDE_CODE_OAUTH_TOKEN`` is read by the
    ``claude`` CLI binary itself; this Python module's *executable
    code* never references it.

    The check uses ``executable_source`` so the negative-context
    mention in the module docstring ("the OAuth token env var is
    consumed by the CLI, not by us") doesn't trigger a false positive.
    """
    code = executable_source(cc)
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in code


def test_source_has_no_shell_true() -> None:
    """AC-7.1 / AC-7.6 — never ``shell=True`` in executable code.

    Docstring may discuss the rule (e.g. "Never ``shell=True``"); the
    grep scopes to executable AST only.
    """
    code = executable_source(cc)
    assert not re.search(r"shell\s*=\s*True", code)


def test_source_has_no_string_form_subprocess() -> None:
    """AC-7.1 — never the string-form first arg to ``subprocess.run`` /
    ``subprocess.Popen`` in executable code.
    """
    code = executable_source(cc)
    assert not re.search(r"subprocess\.(run|Popen)\(\s*[\"']", code)


def test_source_does_not_import_anthropic_sdk() -> None:
    """NFR-002 invariant — locally pinned belt-and-braces. The
    repo-wide CI grep (Step 10) is the safety net.
    """
    code = executable_source(cc)
    assert not re.search(r"^\s*(from anthropic|import anthropic)", code, re.MULTILINE)


# --- Public surface ---------------------------------------------------------


def test_module_all_exports() -> None:
    assert set(cc.__all__) == {
        "DEFAULT_TIMEOUT_S",
        "DEFAULT_TOTAL_BUDGET_S",
        "ClaudeRunner",
        "RetryBudget",
        "call_claude_code",
    }


def test_default_constants_match_fd_r3() -> None:
    """FD R3 anchored values."""
    assert DEFAULT_TIMEOUT_S == 120.0
    assert DEFAULT_TOTAL_BUDGET_S == 300.0
