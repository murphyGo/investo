"""Tests for ``briefing.errors`` (FD E4, E5; NFR-007 AC-7.4)."""

from __future__ import annotations

import dataclasses
import json

import pytest

from investo.briefing.errors import (
    BriefingGenerationError,
    BriefingStage,
    SubprocessOutcome,
)

_STDERR_BYTE_CAP = 1024


# --- BriefingGenerationError class shape ------------------------------------


def test_bge_is_exception_not_runtime_error() -> None:
    """E4 — BGE is `Exception`, not `RuntimeError`. Matches u1's
    ``SourceFetchError`` decision so ``pytest.raises`` stays consistent.
    """
    assert issubclass(BriefingGenerationError, Exception)
    assert not issubclass(BriefingGenerationError, RuntimeError)


@pytest.mark.parametrize(
    "stage",
    ["classification", "synthesis", "post_validation", "budget"],
)
def test_bge_constructs_for_all_stages(stage: BriefingStage) -> None:
    err = BriefingGenerationError(
        stage=stage,
        attempt_count=1,
        last_stderr=None,
        cause=None,
    )
    assert err.stage == stage
    assert err.attempt_count == 1
    assert err.last_stderr is None
    assert err.cause is None


def test_bge_message_includes_stage_and_attempt_count() -> None:
    err = BriefingGenerationError(
        stage="classification",
        attempt_count=3,
        last_stderr=None,
        cause=None,
    )
    assert "classification" in str(err)
    assert "3" in str(err)


def test_bge_round_trips_attributes() -> None:
    cause = json.JSONDecodeError("expecting value", "", 0)
    err = BriefingGenerationError(
        stage="classification",
        attempt_count=2,
        last_stderr="something went wrong",
        cause=cause,
    )
    assert err.stage == "classification"
    assert err.attempt_count == 2
    assert err.last_stderr == "something went wrong"
    assert err.cause is cause


def test_bge_preserves_cause_chain() -> None:
    """``raise BGE(...) from <origin>`` preserves ``__cause__``."""
    origin = ValueError("oops")
    try:
        try:
            raise origin
        except ValueError as exc:
            raise BriefingGenerationError(
                stage="synthesis",
                attempt_count=3,
                last_stderr="",
                cause=exc,
            ) from exc
    except BriefingGenerationError as bge:
        assert bge.__cause__ is origin
        assert bge.cause is origin


# --- AC-7.4: stderr truncation to 1024 UTF-8 bytes --------------------------


def test_stderr_at_cap_passes_through_unchanged() -> None:
    text = "x" * _STDERR_BYTE_CAP  # 1024 ASCII chars = 1024 UTF-8 bytes
    err = BriefingGenerationError(
        stage="classification",
        attempt_count=1,
        last_stderr=text,
        cause=None,
    )
    assert err.last_stderr == text
    assert err.last_stderr is not None
    assert len(err.last_stderr.encode("utf-8")) == _STDERR_BYTE_CAP


def test_stderr_just_over_cap_is_truncated() -> None:
    text = "x" * (_STDERR_BYTE_CAP + 1)
    err = BriefingGenerationError(
        stage="classification",
        attempt_count=1,
        last_stderr=text,
        cause=None,
    )
    assert err.last_stderr is not None
    assert len(err.last_stderr.encode("utf-8")) <= _STDERR_BYTE_CAP


def test_stderr_far_over_cap_is_truncated() -> None:
    """AC-7.4 — 10 KB stderr → ≤ 1024 UTF-8 bytes after construction."""
    text = "y" * 10_000
    err = BriefingGenerationError(
        stage="classification",
        attempt_count=1,
        last_stderr=text,
        cause=None,
    )
    assert err.last_stderr is not None
    assert len(err.last_stderr.encode("utf-8")) <= _STDERR_BYTE_CAP


def test_stderr_truncation_is_utf8_safe() -> None:
    """A truncation that lands mid-codepoint must NOT produce invalid
    UTF-8 (no UnicodeDecodeError on access).
    """
    # 한 = U+D55C = 3 UTF-8 bytes (0xED 0x95 0x9C). Build a string
    # whose byte length lands the cap mid-codepoint.
    # We want the byte at position 1024 to be partway through a
    # multi-byte sequence.
    # Each "한" is 3 bytes. 1023 / 3 = 341, so 341 "한"s = 1023 bytes,
    # then one more "한" pushes to 1026 bytes — cut at 1024 is mid-char.
    text = "한" * 342 + "x"  # 342*3 + 1 = 1027 bytes
    err = BriefingGenerationError(
        stage="classification",
        attempt_count=1,
        last_stderr=text,
        cause=None,
    )
    assert err.last_stderr is not None
    # Cap respected
    assert len(err.last_stderr.encode("utf-8")) <= _STDERR_BYTE_CAP
    # Decoding-on-access does not raise — implicitly, the truncation
    # produced a valid UTF-8 string. Re-encode + decode round-trip:
    err.last_stderr.encode("utf-8").decode("utf-8")  # no exception


def test_stderr_none_remains_none() -> None:
    """E4 — ``post_validation`` and ``budget`` stages carry ``None``
    stderr (no subprocess returned).
    """
    err = BriefingGenerationError(
        stage="post_validation",
        attempt_count=1,
        last_stderr=None,
        cause=None,
    )
    assert err.last_stderr is None


# --- SubprocessOutcome ------------------------------------------------------


def test_subprocess_outcome_constructs_with_all_fields() -> None:
    outcome = SubprocessOutcome(
        stdout="hello",
        stderr="warn",
        returncode=0,
        elapsed_s=1.234,
    )
    assert outcome.stdout == "hello"
    assert outcome.stderr == "warn"
    assert outcome.returncode == 0
    assert outcome.elapsed_s == 1.234


def test_subprocess_outcome_is_frozen() -> None:
    """E5 — frozen dataclass (no post-construction mutation)."""
    outcome = SubprocessOutcome(stdout="", stderr="", returncode=0, elapsed_s=0.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        outcome.returncode = 1  # type: ignore[misc]


def test_subprocess_outcome_uses_slots() -> None:
    """E5 — slots=True prevents accidental attribute injection.

    On a frozen+slots dataclass, assigning an unknown attribute raises
    one of TypeError / AttributeError / FrozenInstanceError depending
    on Python version (frozen-check happens before slots-check). We
    accept any of them — the contract is "no silent attribute add".
    """
    outcome = SubprocessOutcome(stdout="", stderr="", returncode=0, elapsed_s=0.0)
    with pytest.raises((TypeError, AttributeError, dataclasses.FrozenInstanceError)):
        outcome.unknown = "value"  # type: ignore[attr-defined]


# --- Construction examples from FD E4 ---------------------------------------


def test_bge_classification_example() -> None:
    """E4 example: Stage 1 output not parseable as JSON after 3
    attempts.
    """
    cause = json.JSONDecodeError("expecting value", "{", 0)
    err = BriefingGenerationError(
        stage="classification",
        attempt_count=3,
        last_stderr="...",
        cause=cause,
    )
    assert err.stage == "classification"
    assert err.attempt_count == 3
    assert isinstance(err.cause, json.JSONDecodeError)


def test_bge_synthesis_empty_example() -> None:
    """E4 example: Stage 2 produced empty markdown."""
    err = BriefingGenerationError(
        stage="synthesis",
        attempt_count=2,
        last_stderr="",
        cause=None,
    )
    assert err.stage == "synthesis"
    assert err.last_stderr == ""
    assert err.cause is None


def test_bge_post_validation_example() -> None:
    """E4 example: PII regex matched in synthesized output."""
    err = BriefingGenerationError(
        stage="post_validation",
        attempt_count=1,
        last_stderr=None,
        cause=None,
    )
    assert err.stage == "post_validation"
    assert err.attempt_count == 1


def test_bge_budget_example() -> None:
    """E4 example: total budget exceeded."""
    err = BriefingGenerationError(
        stage="budget",
        attempt_count=2,
        last_stderr=None,
        cause=TimeoutError("budget exhausted"),
    )
    assert err.stage == "budget"
    assert isinstance(err.cause, TimeoutError)
