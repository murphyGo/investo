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

# Repo-root-relative archive directory. Tests redirect this via
# ``monkeypatch.setattr(paths, "ARCHIVE_ROOT", tmp_path)`` per the
# Step 5.3 design decision (option a). u5 orchestrator is responsible
# for invoking the pipeline from the repo root so this path resolves
# correctly in production.
ARCHIVE_ROOT: Final[Path] = Path("archive")


def archive_path(target_date: date) -> Path:
    """Return the archive markdown path for ``target_date`` (FR-006).

    The format is ``ARCHIVE_ROOT / YYYY / MM / YYYY-MM-DD.md`` — year
    and month directories are zero-padded. The ``.md`` extension is
    fixed (mkdocs consumes it as Markdown).

    Pure: no filesystem I/O. The caller (``write_briefing`` in Step 5)
    is responsible for ensuring ``path.parent`` exists before writing.
    """
    return (
        ARCHIVE_ROOT
        / f"{target_date.year:04d}"
        / f"{target_date.month:02d}"
        / f"{target_date.isoformat()}.md"
    )


__all__ = ["ARCHIVE_ROOT", "archive_path"]
