"""Archive directory contract for u3 publisher (FR-006).

Files land at ``archive/YYYY/MM/YYYY-MM-DD.md`` relative to the repo
root. The orchestrator (u5) is responsible for cwd alignment when
invoking the pipeline; this module is pure path arithmetic with no
filesystem I/O.

Reference:
    docs/requirements.md FR-006 acceptance criteria
        — `archive/YYYY/MM/YYYY-MM-DD.md`
    aidlc-docs/inception/application-design/component-methods.md
        — `archive_path(target_date) -> Path`
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Final

from investo._internal.archive_layout import ArchiveLayout
from investo.models.segments import MarketSegment

# Repo-root-relative archive directory — the live, patchable seam. Tests
# redirect this via ``monkeypatch.setattr(paths, "ARCHIVE_ROOT", tmp_path)``
# per the Step 5.3 design decision (option a). u5 orchestrator is
# responsible for invoking the pipeline from the repo root so this path
# resolves correctly in production. ``archive_path`` reads this at call
# time and delegates the path *shape* to ``_internal.ArchiveLayout``.
ARCHIVE_ROOT: Final[Path] = Path("archive")


def archive_path(target_date: date, *, segment: MarketSegment | None = None) -> Path:
    """Return the archive markdown path for ``target_date`` (FR-006).

    The historical unsegmented format is ``ARCHIVE_ROOT / YYYY / MM /
    YYYY-MM-DD.md``. New u7 segmented runs pass ``segment`` and land at
    ``ARCHIVE_ROOT / segment / YYYY / MM / YYYY-MM-DD.md``. Year and
    month directories are zero-padded. The ``.md`` extension is fixed
    (mkdocs consumes it as Markdown).

    Pure: no filesystem I/O. The caller (``write_briefing`` in Step 5)
    is responsible for ensuring ``path.parent`` exists before writing.
    The path *shape* is single-homed in :class:`ArchiveLayout`; the root
    binding stays here so the existing monkeypatch seam is preserved.
    """
    return ArchiveLayout(ARCHIVE_ROOT).briefing_path(target_date, segment)


__all__ = ["ARCHIVE_ROOT", "archive_path"]
