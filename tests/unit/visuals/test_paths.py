"""Tests for u19 visual asset path helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from investo._internal.archive_layout import ArchiveLayout
from investo.visuals.paths import visual_asset_dir, visual_asset_path, visual_asset_relative_path


def test_visual_asset_dir_is_markdown_adjacent_for_segment() -> None:
    target_date = date(2026, 5, 7)

    assert visual_asset_dir(target_date, "crypto") == Path(
        "archive/crypto/2026/05/2026-05-07.assets"
    )


def test_visual_asset_path_uses_safe_name_and_allowed_extension() -> None:
    target_date = date(2026, 5, 7)

    assert visual_asset_path(target_date, "us-equity", "data-confidence") == Path(
        "archive/us-equity/2026/05/2026-05-07.assets/data-confidence.svg"
    )
    assert visual_asset_path(
        target_date,
        "us-equity",
        "data-confidence",
        extension=".png",
    ) == Path("archive/us-equity/2026/05/2026-05-07.assets/data-confidence.png")
    assert visual_asset_path(
        target_date,
        "us-equity",
        "external-context-image",
        extension=".jpg",
    ) == Path("archive/us-equity/2026/05/2026-05-07.assets/external-context-image.jpg")
    with pytest.raises(ValueError):
        visual_asset_path(target_date, "us-equity", "../data-confidence")
    with pytest.raises(ValueError):
        visual_asset_path(target_date, "us-equity", "data-confidence", extension=".webp")


def test_visual_asset_path_uses_explicit_archive_layout() -> None:
    target_date = date(2026, 5, 7)
    layout = ArchiveLayout(Path("/tmp/investo-archive"))

    assert visual_asset_dir(target_date, "crypto", archive_layout=layout) == Path(
        "/tmp/investo-archive/crypto/2026/05/2026-05-07.assets"
    )
    assert visual_asset_path(
        target_date,
        "crypto",
        "data-confidence",
        archive_layout=layout,
    ) == Path("/tmp/investo-archive/crypto/2026/05/2026-05-07.assets/data-confidence.svg")


def test_visual_asset_relative_path_is_posix_markdown_safe() -> None:
    markdown_path = Path("archive/us-equity/2026/05/2026-05-07.md")
    asset_path = Path("archive/us-equity/2026/05/2026-05-07.assets/data-confidence.svg")

    assert visual_asset_relative_path(asset_path, markdown_path) == (
        "2026-05-07.assets/data-confidence.svg"
    )
