"""Single source of truth for the archive directory convention.

The ``archive/{segment}/YYYY/MM/YYYY-MM-DD.md`` layout was encoded
implicitly in two places: ``publisher/paths.py::archive_path`` and
``visuals/paths.py::visual_asset_dir`` (the latter reconstructed the
shape by deriving from the former). That made ``visuals`` import
``publisher`` — a sibling adapter→adapter edge — and meant a layout
change had to be mirrored across two modules.

:class:`ArchiveLayout` homes the convention in the ``_internal`` shared
layer. Both ``publisher`` and ``visuals`` now depend *inward* on this
stable primitive, dissolving the ``visuals → publisher`` edge entirely.

Pure path arithmetic — no filesystem I/O. ``MarketSegment`` comes from
``investo.models`` (a shared layer), so this module introduces no
adapter dependency.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Final

from investo.models.segments import MarketSegment

# Default repo-root-relative archive directory. The *live, patchable*
# root binding stays in ``publisher.paths.ARCHIVE_ROOT`` (the seam the
# orchestrator reads at call time and tests monkeypatch); this class is
# pure path-shape arithmetic with the root injected, so the layout
# convention is single-homed here without owning the mutable seam.
DEFAULT_ARCHIVE_ROOT: Final[Path] = Path("archive")


class ArchiveLayout:
    """Derives briefing and asset paths from an archive root.

    The historical unsegmented format is ``root / YYYY / MM /
    YYYY-MM-DD.md``. Segmented (u7) runs pass ``segment`` and land at
    ``root / segment / YYYY / MM / YYYY-MM-DD.md``. Year and month
    directories are zero-padded; the ``.md`` extension is fixed.

    The ``root`` is injected so this class owns the *shape*, not the
    mutable root seam (which lives in ``publisher.paths.ARCHIVE_ROOT``).
    """

    def __init__(self, root: Path = DEFAULT_ARCHIVE_ROOT) -> None:
        self._root = root

    def briefing_path(self, target_date: date, segment: MarketSegment | None = None) -> Path:
        """Return the archive markdown path for ``target_date``."""
        root = self._root if segment is None else self._root / segment
        return (
            root
            / f"{target_date.year:04d}"
            / f"{target_date.month:02d}"
            / f"{target_date.isoformat()}.md"
        )

    def asset_dir(self, target_date: date, segment: MarketSegment) -> Path:
        """Return the markdown-adjacent asset directory for a segment."""
        return self.briefing_path(target_date, segment).with_suffix(".assets")


__all__ = ["DEFAULT_ARCHIVE_ROOT", "ArchiveLayout"]
