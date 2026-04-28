"""Error types and the subprocess-outcome value object for u2 briefing.

References:
    Functional Design E4 (`u2-briefing/functional-design/domain-entities.md`)
        — `BriefingGenerationError`
    Functional Design E5 (same)
        — `SubprocessOutcome` value object
    Functional Design L5 (`business-logic-model.md`)
        — failure-classification matrix
    NFR Requirements AC-7.4 — `last_stderr` truncated to 1024 bytes

Error contract:

* ``BriefingGenerationError`` (BGE) is raised when the failure is
  traceable to **the LLM's response or the budget** (R3 R5 R6 + L5).
* Programmer errors (`KeyError`, `AttributeError`, `pydantic.ValidationError`,
  ...) propagate as-is — u5 orchestrator's stage guard converts them to
  a separate "PROGRAMMER_ERROR" alert. This is enforced by NEVER
  wrapping arbitrary exceptions; ``BGE.cause`` holds the originating
  LLM-level cause when relevant.
* BGE is a subclass of ``Exception`` (not ``RuntimeError``) — matches
  u1's ``SourceFetchError`` decision so ``pytest.raises`` discipline
  stays consistent across units.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

# Cap on the ``last_stderr`` payload (UTF-8 bytes). FD E4 / NFR AC-7.4.
# Operator alerts include this excerpt — bounding it prevents a 10 MB
# stderr from landing in the alert text. The truncation is byte-safe:
# a multi-byte sequence cut mid-codepoint is repaired by decoding with
# ``errors="ignore"``.
_STDERR_BYTE_CAP: Final[int] = 1024


BriefingStage = Literal["classification", "synthesis", "post_validation", "budget"]
"""Stage at which a `BriefingGenerationError` was raised (E4)."""


@dataclass(frozen=True, slots=True)
class SubprocessOutcome:
    """The result of one ``call_claude_code`` subprocess invocation (E5).

    ``elapsed_s`` is the wall-clock duration; the retry helper compares
    cumulative elapsed against ``RetryBudget.total_budget_s`` to fire
    ``BriefingGenerationError(stage="budget")`` without spending another
    round-trip when there is no time left.
    """

    stdout: str
    stderr: str
    returncode: int
    elapsed_s: float


def _truncate_stderr(value: str | None) -> str | None:
    """Truncate ``value`` to ``_STDERR_BYTE_CAP`` UTF-8 bytes.

    Returns ``None`` for ``None`` input. For non-None strings, the cap
    is enforced on the encoded UTF-8 length (not codepoint count); a
    cut that lands mid-codepoint is recovered by re-decoding with
    ``errors="ignore"``, which drops the partial sequence cleanly.
    """
    if value is None:
        return None
    encoded = value.encode("utf-8")
    if len(encoded) <= _STDERR_BYTE_CAP:
        return value
    return encoded[:_STDERR_BYTE_CAP].decode("utf-8", errors="ignore")


class BriefingGenerationError(Exception):
    """Terminal failure raised by ``generate_briefing`` (E4).

    Surfaces when the LLM's response cannot be coerced into a ``Briefing``
    after retries are exhausted, when the post-validation leak guard
    matches, or when the shared retry budget is exceeded.

    Attributes
    ----------
    stage:
        Which step of the pipeline failed. Routes the operator-alert
        message format in u4 notifier.
    attempt_count:
        Retries actually consumed. ``1`` = single attempt;
        ``MAX_ATTEMPTS`` = exhausted under default config.
    last_stderr:
        Last subprocess stderr (truncated to ``_STDERR_BYTE_CAP`` UTF-8
        bytes). ``None`` for ``post_validation`` and ``budget`` stages
        where no subprocess returned an error stream.
    cause:
        Original exception when wrapping (e.g. ``json.JSONDecodeError``,
        ``subprocess.TimeoutExpired``). May be ``None``.
    """

    stage: BriefingStage
    attempt_count: int
    last_stderr: str | None
    cause: BaseException | None

    def __init__(
        self,
        *,
        stage: BriefingStage,
        attempt_count: int,
        last_stderr: str | None,
        cause: BaseException | None,
    ) -> None:
        message = f"briefing failed at stage={stage} after {attempt_count} attempts"
        super().__init__(message)
        self.stage = stage
        self.attempt_count = attempt_count
        self.last_stderr = _truncate_stderr(last_stderr)
        self.cause = cause


__all__ = [
    "BriefingGenerationError",
    "BriefingStage",
    "SubprocessOutcome",
]
