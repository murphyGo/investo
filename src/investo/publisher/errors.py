"""Error types for u3 publisher.

References:
    aidlc-docs/inception/application-design/component-methods.md
        — `PublisherIOError`, `PublisherGitError` raise contracts
    docs/requirements.md NFR-004 — disclaimer enforcement is the
        publish-boundary hard block

Error contract:

* ``PublisherDisclaimerError`` is raised by ``write_briefing`` when
  ``verify_disclaimer`` returns False. The write does NOT happen.
* ``PublisherIOError`` wraps ``OSError`` raised during the atomic
  markdown write (mkdir / tmp file write / replace).
* ``PublisherGitError`` is raised by ``commit_and_push`` after the
  retry budget is exhausted. ``last_stderr`` is truncated to 1024
  UTF-8 bytes (mirrors u2 ``BriefingGenerationError`` AC-7.4 pattern
  so operator-alert excerpts are bounded uniformly across units).
* All four are subclasses of ``Exception`` (NOT ``RuntimeError``) —
  matches u1 ``SourceFetchError`` and u2 ``BriefingGenerationError``
  precedent so ``pytest.raises`` discipline stays consistent.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from investo._internal.surface_quality import SurfaceQualityIssue
from investo._internal.text import truncate_stderr


class PublisherError(Exception):
    """Base class for u3 publisher errors. Subclass before raising —
    a bare ``PublisherError`` carries no actionable context for the
    orchestrator's stage guard.
    """


class PublisherDisclaimerError(PublisherError):
    """Pre-publish disclaimer-missing block (NFR-004).

    Raised by ``write_briefing`` when ``verify_disclaimer`` returns
    False. The publish does NOT happen; no archive file is written.
    """

    target_date: date

    def __init__(self, *, target_date: date) -> None:
        super().__init__(
            f"refusing to publish briefing for {target_date.isoformat()}: "
            f"disclaimer missing from rendered_markdown (NFR-004)"
        )
        self.target_date = target_date


class PublisherIOError(PublisherError):
    """Atomic markdown write failed.

    Wraps the underlying ``OSError`` (mkdir / tmp write / replace).
    The destination archive file is guaranteed to be unaffected when
    this error is raised — the atomic-write contract from Step 5.1.

    ``cause`` is typed as ``OSError | None`` because the only writer
    catch site narrows to ``OSError``; tightening the annotation
    documents the contract.
    """

    target_date: date
    path: Path
    cause: OSError | None

    def __init__(
        self,
        *,
        target_date: date,
        path: Path,
        cause: OSError | None,
    ) -> None:
        super().__init__(
            f"archive write failed for {target_date.isoformat()} at {path}: "
            f"{type(cause).__name__ if cause is not None else 'no-cause'}"
        )
        self.target_date = target_date
        self.path = path
        self.cause = cause


class PublisherGitError(PublisherError):
    """``commit_and_push`` retry budget exhausted (US-006).

    Attributes
    ----------
    attempt_count:
        Total attempts of the full add/commit/push sequence (not
        per-step). ``1`` = single attempt; matches the ``retries``
        parameter contract: ``retries=2`` permits up to 3 attempts.
    last_stderr:
        Last subprocess stderr from the failing step, truncated to
        1024 UTF-8 bytes for safe inclusion in operator alerts.
    cause:
        Original exception (e.g. ``subprocess.CalledProcessError``).
    """

    attempt_count: int
    last_stderr: str | None
    cause: BaseException | None

    def __init__(
        self,
        *,
        attempt_count: int,
        last_stderr: str | None,
        cause: BaseException | None,
    ) -> None:
        super().__init__(f"git commit/push failed after {attempt_count} attempts")
        self.attempt_count = attempt_count
        self.last_stderr = truncate_stderr(last_stderr)
        self.cause = cause


class SurfaceQualityError(PublisherError):
    """Publish-boundary block for unrepaired first-viewport artifacts."""

    segment: str
    issues: tuple[SurfaceQualityIssue, ...]

    def __init__(self, *, segment: str, issues: tuple[SurfaceQualityIssue, ...]) -> None:
        codes = ", ".join(issue.code for issue in issues)
        super().__init__(f"surface quality blocked segment={segment}: {codes}")
        self.segment = segment
        self.issues = issues


class DailyThesisConsistencyError(PublisherError):
    """Publish-boundary block for repeated daily thesis lines across a bundle."""

    segments: tuple[str, ...]
    line: str

    def __init__(self, *, segments: tuple[str, ...], line: str) -> None:
        super().__init__(
            f"daily thesis consistency blocked segments={','.join(segments)}: repeated thesis line"
        )
        self.segments = segments
        self.line = line


__all__ = [
    "DailyThesisConsistencyError",
    "PublisherDisclaimerError",
    "PublisherError",
    "PublisherGitError",
    "PublisherIOError",
    "SurfaceQualityError",
]
