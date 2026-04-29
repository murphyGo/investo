"""Anchor tests for ``investo.publisher.errors``.

Pins the exception-class contract for u3 publisher:

* All four classes subclass ``Exception`` (NOT ``RuntimeError``) — match
  u1 / u2 precedent so ``pytest.raises`` discipline stays consistent.
* ``PublisherGitError.last_stderr`` is truncated to **1024 UTF-8 bytes**
  (4 boundary tests: at-cap / just-over / far-over / multi-byte
  mid-character). Mirrors u2 ``BriefingGenerationError`` AC-7.4 pattern.
* Field round-trip on access; ``from``-chain preserves ``__cause__``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from investo.publisher.errors import (
    PublisherDisclaimerError,
    PublisherError,
    PublisherGitError,
    PublisherIOError,
)

# ---------------------------------------------------------------------------
# Inheritance — Exception, NOT RuntimeError
# ---------------------------------------------------------------------------


def test_publisher_error_is_exception_not_runtime_error() -> None:
    assert issubclass(PublisherError, Exception)
    assert not issubclass(PublisherError, RuntimeError)


def test_publisher_disclaimer_error_subclasses_publisher_error() -> None:
    assert issubclass(PublisherDisclaimerError, PublisherError)


def test_publisher_io_error_subclasses_publisher_error() -> None:
    assert issubclass(PublisherIOError, PublisherError)


def test_publisher_git_error_subclasses_publisher_error() -> None:
    assert issubclass(PublisherGitError, PublisherError)


# ---------------------------------------------------------------------------
# PublisherDisclaimerError — NFR-004 hard block
# ---------------------------------------------------------------------------


def test_disclaimer_error_carries_target_date() -> None:
    err = PublisherDisclaimerError(target_date=date(2026, 4, 25))
    assert err.target_date == date(2026, 4, 25)


def test_disclaimer_error_message_mentions_date_and_nfr() -> None:
    err = PublisherDisclaimerError(target_date=date(2026, 4, 25))
    msg = str(err)
    assert "2026-04-25" in msg
    assert "NFR-004" in msg


# ---------------------------------------------------------------------------
# PublisherIOError — atomic-write failure context
# ---------------------------------------------------------------------------


def test_io_error_round_trips_target_date_path_cause() -> None:
    cause = OSError("disk full")
    err = PublisherIOError(
        target_date=date(2026, 4, 25),
        path=Path("archive/2026/04/2026-04-25.md"),
        cause=cause,
    )
    assert err.target_date == date(2026, 4, 25)
    assert err.path == Path("archive/2026/04/2026-04-25.md")
    assert err.cause is cause


def test_io_error_with_none_cause() -> None:
    err = PublisherIOError(
        target_date=date(2026, 4, 25),
        path=Path("archive/foo.md"),
        cause=None,
    )
    assert err.cause is None
    assert "no-cause" in str(err)


def test_io_error_message_mentions_cause_class_name() -> None:
    err = PublisherIOError(
        target_date=date(2026, 4, 25),
        path=Path("archive/foo.md"),
        cause=PermissionError("denied"),
    )
    assert "PermissionError" in str(err)


def test_io_error_preserves_from_chain() -> None:
    cause = OSError("disk full")
    try:
        try:
            raise cause
        except OSError as e:
            raise PublisherIOError(
                target_date=date(2026, 4, 25),
                path=Path("archive/foo.md"),
                cause=e,
            ) from e
    except PublisherIOError as bge:
        assert bge.__cause__ is cause


# ---------------------------------------------------------------------------
# PublisherGitError — retry exhaustion + 1024-byte stderr truncation
# ---------------------------------------------------------------------------


def test_git_error_round_trip() -> None:
    err = PublisherGitError(
        attempt_count=3,
        last_stderr="git push failed: connection reset",
        cause=None,
    )
    assert err.attempt_count == 3
    assert err.last_stderr == "git push failed: connection reset"


def test_git_error_message_includes_attempt_count() -> None:
    err = PublisherGitError(attempt_count=3, last_stderr=None, cause=None)
    assert "3 attempts" in str(err)


def test_git_error_with_none_stderr() -> None:
    err = PublisherGitError(attempt_count=3, last_stderr=None, cause=None)
    assert err.last_stderr is None


def test_git_error_stderr_at_cap_passes_through_unchanged() -> None:
    """1024-byte input is exactly at the cap — preserved as-is."""
    payload = "a" * 1024
    err = PublisherGitError(attempt_count=3, last_stderr=payload, cause=None)
    assert err.last_stderr == payload
    assert err.last_stderr is not None
    assert len(err.last_stderr.encode("utf-8")) == 1024


def test_git_error_stderr_just_over_cap_is_truncated() -> None:
    """1025-byte input → truncated to 1024 bytes."""
    payload = "a" * 1025
    err = PublisherGitError(attempt_count=3, last_stderr=payload, cause=None)
    assert err.last_stderr is not None
    assert len(err.last_stderr.encode("utf-8")) <= 1024


def test_git_error_stderr_far_over_cap_is_truncated() -> None:
    """10 KB input → truncated to ≤ 1024 bytes (AC-7.4 mirror)."""
    payload = "a" * 10240
    err = PublisherGitError(attempt_count=3, last_stderr=payload, cause=None)
    assert err.last_stderr is not None
    assert len(err.last_stderr.encode("utf-8")) <= 1024


def test_git_error_stderr_multibyte_boundary_safe() -> None:
    """A truncation that lands mid-codepoint must NOT yield a string
    that fails to decode. Korean ``가`` is 3 bytes in UTF-8; padding to
    1023 bytes of ASCII + one ``가`` (3 bytes) lands the cut at byte
    1024 inside the Korean character.
    """
    payload = ("a" * 1022) + "가가"
    err = PublisherGitError(attempt_count=3, last_stderr=payload, cause=None)
    assert err.last_stderr is not None
    # Must be valid UTF-8 (no decode error).
    err.last_stderr.encode("utf-8").decode("utf-8")
    assert len(err.last_stderr.encode("utf-8")) <= 1024


def test_git_error_preserves_from_chain() -> None:
    import subprocess as _sp

    cause = _sp.CalledProcessError(returncode=1, cmd=["git", "push"])
    try:
        try:
            raise cause
        except _sp.CalledProcessError as e:
            raise PublisherGitError(
                attempt_count=3,
                last_stderr=str(e),
                cause=e,
            ) from e
    except PublisherGitError as ge:
        assert ge.__cause__ is cause
        assert ge.cause is cause


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def test_errors_module_exports_expected_names() -> None:
    from investo.publisher import errors as errors_module

    assert hasattr(errors_module, "PublisherError")
    assert hasattr(errors_module, "PublisherDisclaimerError")
    assert hasattr(errors_module, "PublisherIOError")
    assert hasattr(errors_module, "PublisherGitError")


def test_disclaimer_error_can_be_raised_and_caught() -> None:
    """Smoke: raise/catch path works through ``pytest.raises``."""
    with pytest.raises(PublisherDisclaimerError) as exc:
        raise PublisherDisclaimerError(target_date=date(2026, 4, 25))
    assert exc.value.target_date == date(2026, 4, 25)
