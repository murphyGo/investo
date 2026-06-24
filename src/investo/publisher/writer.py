"""Atomic markdown write to ``archive/YYYY/MM/YYYY-MM-DD.md`` (FR-003).

The publish-boundary contract:

1. **Verify disclaimer first** (NFR-004 hard block). If
   ``verify_disclaimer`` returns False, raise
   ``PublisherDisclaimerError`` and write NOTHING.
2. **Compute archive path** via ``archive_path(target_date)`` (FR-006).
3. **Create year/month directories** with ``mkdir(parents=True,
   exist_ok=True)`` so a fresh archive tree bootstraps cleanly.
4. **Write atomically** — dump bytes to a tmp sibling, then
   ``os.replace`` to the final path. A SIGINT mid-write cannot leave
   a half-written file at the destination. Pattern mirrors u2's
   ``FakeClaudeRunner`` fixture write (Step 7 review M1).
5. **Return the final path** so the caller (orchestrator → Step 6
   ``commit_and_push``) knows what to stage.

Same-day re-run idempotence (FR-006): a second write with the same
``target_date`` overwrites the first. Git history retains the
previous version; no in-place backup.

Reference:
    docs/requirements.md FR-003 (정적 게시) + FR-006 (영구 보관)
        + NFR-004 (disclaimer enforcement)
    aidlc-docs/inception/application-design/component-methods.md
        — `write_briefing(briefing, target_date) -> Path`
"""

from __future__ import annotations

import contextlib
from datetime import date
from pathlib import Path

from investo._internal._io import write_atomic
from investo.models import Briefing
from investo.models.segments import MarketSegment
from investo.publisher.errors import PublisherDisclaimerError, PublisherIOError
from investo.publisher.paths import archive_path
from investo.publisher.verifier import verify_disclaimer


def write_briefing(
    briefing: Briefing,
    target_date: date,
    *,
    segment: MarketSegment | None = None,
) -> Path:
    """Verify disclaimer, then atomically write the briefing markdown
    to ``archive_path(target_date)``. Return the written path.

    Raises
    ------
    PublisherDisclaimerError:
        ``verify_disclaimer(briefing.rendered_markdown)`` returned
        False. The publish does NOT happen; no archive file is
        touched.
    PublisherIOError:
        ``mkdir`` / tmp write / ``os.replace`` raised ``OSError``.
        The destination archive file is unchanged from its prior
        state (atomic guarantee).
    """
    if not verify_disclaimer(briefing.rendered_markdown, segment):
        raise PublisherDisclaimerError(target_date=target_date)

    path = archive_path(target_date, segment=segment)

    try:
        write_atomic(path, briefing.rendered_markdown)
    except OSError as exc:
        # Best-effort cleanup of the tmp file. Swallow secondary
        # errors during cleanup so the original cause is what bubbles
        # up to the operator alert.
        with contextlib.suppress(OSError):
            path.with_suffix(path.suffix + ".tmp").unlink(missing_ok=True)
        raise PublisherIOError(target_date=target_date, path=path, cause=exc) from exc

    return path


__all__ = ["write_briefing"]
