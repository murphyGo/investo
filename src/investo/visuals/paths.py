"""Path helpers for markdown-adjacent briefing visual assets."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Final

from investo._internal.archive_layout import ArchiveLayout
from investo.models.segments import MarketSegment

_SAFE_ASSET_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_ALLOWED_EXTENSIONS: Final[frozenset[str]] = frozenset({".svg", ".png", ".jpg", ".jpeg"})


def visual_asset_dir(
    target_date: date,
    segment: MarketSegment,
    *,
    archive_layout: ArchiveLayout | None = None,
) -> Path:
    """Return the markdown-adjacent asset directory for a segmented briefing.

    The path shape and root are supplied through :class:`ArchiveLayout`.
    Production callers pass the layout assembled at the publish/orchestrator
    boundary; standalone callers default to the repo-relative archive root.
    """
    layout = archive_layout or ArchiveLayout()
    return layout.asset_dir(target_date, segment)


def visual_asset_path(
    target_date: date,
    segment: MarketSegment,
    name: str,
    *,
    extension: str = ".svg",
    archive_layout: ArchiveLayout | None = None,
) -> Path:
    """Return a generated visual asset path under the segment/date asset directory."""
    if not _SAFE_ASSET_NAME.fullmatch(name):
        raise ValueError(f"unsafe visual asset name: {name!r}")
    if extension not in _ALLOWED_EXTENSIONS:
        raise ValueError(f"unsupported visual asset extension: {extension!r}")
    return (
        visual_asset_dir(target_date, segment, archive_layout=archive_layout) / f"{name}{extension}"
    )


def visual_asset_relative_path(asset_path: Path, markdown_path: Path) -> str:
    """Return a POSIX relative path suitable for a markdown image link."""
    return asset_path.relative_to(markdown_path.parent).as_posix()


__all__ = ["visual_asset_dir", "visual_asset_path", "visual_asset_relative_path"]
