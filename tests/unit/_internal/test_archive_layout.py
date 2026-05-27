"""Unit tests for the shared archive-layout source of truth (u78).

These pin that :class:`ArchiveLayout` reproduces the exact pre-refactor
path shapes that ``publisher.paths.archive_path`` and
``visuals.paths.visual_asset_dir`` produced, for the combined
(``segment=None``) case and every market segment.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from investo._internal.archive_layout import DEFAULT_ARCHIVE_ROOT, ArchiveLayout
from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY, MarketSegment

_TARGET = date(2026, 4, 25)


def test_default_root_is_repo_relative_archive() -> None:
    assert Path("archive") == DEFAULT_ARCHIVE_ROOT
    assert not DEFAULT_ARCHIVE_ROOT.is_absolute()


def test_briefing_path_combined_segment_none() -> None:
    layout = ArchiveLayout()
    assert layout.briefing_path(_TARGET, None) == Path("archive/2026/04/2026-04-25.md")


@pytest.mark.parametrize("segment", [DOMESTIC_EQUITY, US_EQUITY, CRYPTO])
def test_briefing_path_per_segment(segment: MarketSegment) -> None:
    layout = ArchiveLayout()
    assert layout.briefing_path(_TARGET, segment) == Path(
        f"archive/{segment}/2026/04/2026-04-25.md"
    )


@pytest.mark.parametrize("segment", [DOMESTIC_EQUITY, US_EQUITY, CRYPTO])
def test_asset_dir_per_segment(segment: MarketSegment) -> None:
    layout = ArchiveLayout()
    assert layout.asset_dir(_TARGET, segment) == Path(
        f"archive/{segment}/2026/04/2026-04-25.assets"
    )


def test_custom_root_propagates_to_both_derivations(tmp_path: Path) -> None:
    layout = ArchiveLayout(tmp_path / "arc")
    assert layout.briefing_path(_TARGET, CRYPTO) == (
        tmp_path / "arc" / "crypto" / "2026" / "04" / "2026-04-25.md"
    )
    assert layout.asset_dir(_TARGET, CRYPTO) == (
        tmp_path / "arc" / "crypto" / "2026" / "04" / "2026-04-25.assets"
    )


def test_publisher_archive_path_matches_layout() -> None:
    """``publisher.paths.archive_path`` must produce byte-identical paths
    to the layout it now delegates to (parity, not behavior change).
    """
    from investo.publisher.paths import archive_path

    layout = ArchiveLayout()
    assert archive_path(_TARGET, segment=None) == layout.briefing_path(_TARGET, None)
    for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO):
        assert archive_path(_TARGET, segment=segment) == layout.briefing_path(_TARGET, segment)


def test_visuals_asset_dir_matches_layout() -> None:
    """``visuals.paths.visual_asset_dir`` parity with the layout."""
    from investo.visuals.paths import visual_asset_dir

    layout = ArchiveLayout()
    for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO):
        assert visual_asset_dir(_TARGET, segment) == layout.asset_dir(_TARGET, segment)


def test_visuals_asset_dir_honors_monkeypatched_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A patched ``publisher.paths.ARCHIVE_ROOT`` flows through to the
    visuals asset directory (preserves the orchestrator/visuals seam).
    """
    from investo.visuals.paths import visual_asset_dir

    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", tmp_path / "archive")
    assert visual_asset_dir(_TARGET, CRYPTO) == (
        tmp_path / "archive" / "crypto" / "2026" / "04" / "2026-04-25.assets"
    )
