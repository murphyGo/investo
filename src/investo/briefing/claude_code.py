"""Subprocess wrapper + retry-budget tracking for u2 briefing's two-stage
LLM flow.

References:
    Functional Design R2 (`u2-briefing/functional-design/business-rules.md`)
        — Claude Code CLI subprocess only; Anthropic SDK forbidden
    Functional Design R3 — retry policy + total budget
    Functional Design L4 (`business-logic-model.md`) — RetryBudget algorithm
    Functional Design E5 (`domain-entities.md`) — SubprocessOutcome
    NFR Requirements AC-1.1, AC-1.2, AC-1.5 — 300 s shared budget
    NFR Requirements AC-2.1 — only LLM call site in the codebase
    NFR Requirements AC-2.5, AC-7.2 — no CLAUDE_CODE_OAUTH_TOKEN literal here
    NFR Requirements AC-7.1, AC-7.6 — list-form subprocess only; no shell=True

The ``CLAUDE_CODE_OAUTH_TOKEN`` environment variable is consumed by the
``claude`` CLI binary itself, NOT by this Python module. We never read,
log, pass, or reference it. CI grep (Step 10) re-pins this invariant
across the whole repo.

Subprocess hygiene
------------------

* List form only: ``subprocess.run(["claude", "-p", prompt], ...)``.
* Never ``shell=True``.
* Never the string-form first arg.
* Async dispatch via ``asyncio.to_thread`` so the event loop is not
  blocked while the LLM thinks. Inside the thread, ``subprocess.run``
  is synchronous (its native form); ``timeout=`` enforces the
  per-call ceiling.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from dataclasses import dataclass
from typing import Final, Protocol

from investo.briefing.errors import (
    BriefingGenerationError,
    BriefingStage,
    SubprocessOutcome,
)

# Per-call subprocess timeout per FD R3.
DEFAULT_TIMEOUT_S: Final[float] = 120.0

# Total budget (FD R3 / L4): cumulative across both stages of the same run.
DEFAULT_TOTAL_BUDGET_S: Final[float] = 300.0

# Returncode used when wrapping ``subprocess.TimeoutExpired`` into a
# ``SubprocessOutcome``. 124 is the conventional "timeout" exit code on
# Linux (``timeout(1)``); chosen to be non-zero (so the caller treats
# the outcome as a failure) and recognizable in logs.
_TIMEOUT_RETURNCODE: Final[int] = 124


class ClaudeRunner(Protocol):
    """Test-seam protocol for ``subprocess.run`` substitution.

    Production ``call_claude_code`` shells out to the real ``claude``
    CLI via ``_default_runner``. Tests inject ``FakeClaudeRunner``
    (Step 7) to replay recorded fixtures, isolating CI from the
    network and from the actual ``claude`` binary.
    """

    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]: ...


@dataclass(slots=True)
class RetryBudget:
    """Cumulative wall-clock budget shared across Stage 1 and Stage 2.

    Per FD L4 a single instance is passed by reference into both stages
    so Stage 2's retries don't get a fresh allowance after Stage 1 has
    consumed most of the budget.
    """

    total_budget_s: float = DEFAULT_TOTAL_BUDGET_S
    elapsed_s: float = 0.0

    def record(self, seconds: float) -> None:
        """Add ``seconds`` to the cumulative elapsed total."""
        self.elapsed_s += seconds

    def would_exceed(self, next_attempt_estimate_s: float) -> bool:
        """``True`` if one more attempt of ``next_attempt_estimate_s``
        seconds would push cumulative elapsed at or past
        ``total_budget_s``.

        Inclusive boundary: equality counts as exhausted (we don't
        dispatch a final attempt that would land exactly on the cap).
        """
        return self.elapsed_s + next_attempt_estimate_s >= self.total_budget_s

    def check_or_raise(self, *, stage: BriefingStage) -> None:
        """Raise ``BriefingGenerationError(stage="budget")`` if elapsed
        already meets or exceeds the budget.

        The ``stage`` parameter is the calling-stage context for
        documentation/logging; the BGE itself always carries
        ``stage="budget"`` since budget exhaustion is a distinct
        failure mode regardless of which stage observed it.
        """
        del stage  # context-only; budget is its own stage
        if self.elapsed_s >= self.total_budget_s:
            raise BriefingGenerationError(
                stage="budget",
                attempt_count=0,
                last_stderr=None,
                cause=None,
            )


def _default_runner(
    args: list[str],
    *,
    capture_output: bool,
    text: bool,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    """Default runner — invokes the real ``claude`` CLI via subprocess.

    List-form args + no ``shell=True`` per AC-7.1 / AC-7.6. Token
    handling is delegated to the binary itself (``CLAUDE_CODE_OAUTH_TOKEN``
    is read by the CLI, not by Python).
    """
    return subprocess.run(
        args,
        capture_output=capture_output,
        text=text,
        timeout=timeout,
        check=False,
    )


async def call_claude_code(
    prompt: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    runner: ClaudeRunner | None = None,
) -> SubprocessOutcome:
    """Invoke the ``claude`` CLI subprocess with ``prompt``.

    Returns a ``SubprocessOutcome`` carrying stdout / stderr /
    returncode / wall-clock ``elapsed_s``. **Does not raise** on
    non-zero returncode or timeout — both are surfaced via the
    outcome's fields and the caller (the retry loop) decides whether
    to retry (FD R3).

    On ``subprocess.TimeoutExpired`` the outcome has
    ``returncode == 124`` and a ``stderr`` of ``"<timeout after Ns>"``.

    ``runner`` is a test seam. When ``None``, the real ``claude`` CLI
    is invoked via ``asyncio.to_thread(subprocess.run, ...)`` so the
    event loop is not blocked.
    """
    actual_runner: ClaudeRunner = runner if runner is not None else _default_runner
    args = ["claude", "-p", prompt]

    start = time.monotonic()
    try:
        completed = await asyncio.to_thread(
            actual_runner,
            args,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        return SubprocessOutcome(
            stdout="",
            stderr=f"<timeout after {timeout_s}s>",
            returncode=_TIMEOUT_RETURNCODE,
            elapsed_s=elapsed,
        )

    elapsed = time.monotonic() - start
    return SubprocessOutcome(
        stdout=completed.stdout if completed.stdout is not None else "",
        stderr=completed.stderr if completed.stderr is not None else "",
        returncode=completed.returncode,
        elapsed_s=elapsed,
    )


__all__ = [
    "DEFAULT_TIMEOUT_S",
    "DEFAULT_TOTAL_BUDGET_S",
    "ClaudeRunner",
    "RetryBudget",
    "call_claude_code",
]
