"""Anchor tests for ``investo.publisher.paths`` (FR-006).

Pins the ``archive/YYYY/MM/YYYY-MM-DD.md`` directory contract. The
function is pure — every test compares against an expected ``Path``
literal; no filesystem state is consulted.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from investo.briefing.segments import CRYPTO, US_EQUITY
from investo.publisher.paths import ARCHIVE_ROOT, archive_path, normalize_archive_publish_path

# ---------------------------------------------------------------------------
# Constant + signature
# ---------------------------------------------------------------------------


def test_archive_root_is_relative_path() -> None:
    """``ARCHIVE_ROOT`` is a repo-root-relative ``Path`` (no leading
    separator, no absolute prefix). Production deployment runs from
    the repo root, so a relative root is correct.
    """
    assert Path("archive") == ARCHIVE_ROOT
    assert not ARCHIVE_ROOT.is_absolute()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_archive_path_typical_date() -> None:
    """The canonical example: 2026-04-25 → archive/2026/04/2026-04-25.md."""
    assert archive_path(date(2026, 4, 25)) == Path("archive/2026/04/2026-04-25.md")


def test_archive_path_pads_single_digit_month() -> None:
    """Month is zero-padded to 2 digits (FR-006 directory contract)."""
    assert archive_path(date(2026, 1, 1)) == Path("archive/2026/01/2026-01-01.md")


def test_archive_path_pads_single_digit_day_in_filename() -> None:
    """``date.isoformat()`` already pads the day; pin the round-trip."""
    assert archive_path(date(2026, 3, 9)) == Path("archive/2026/03/2026-03-09.md")


def test_archive_path_supports_segment_prefix_for_new_runs() -> None:
    """u7 segmented runs add ``archive/{segment}`` before year/month."""
    assert archive_path(date(2026, 4, 25), segment=US_EQUITY) == Path(
        "archive/us-equity/2026/04/2026-04-25.md"
    )


def test_archive_path_keeps_unsegmented_history_readable() -> None:
    """Default path remains the historical FR-006 layout."""
    assert archive_path(date(2026, 4, 25), segment=None) == Path("archive/2026/04/2026-04-25.md")


def test_archive_path_segment_uses_archive_root_constant(monkeypatch: object) -> None:
    from investo.publisher import paths as paths_module

    custom_root = Path("/tmp/custom-archive")
    assert hasattr(monkeypatch, "setattr")
    monkeypatch.setattr(paths_module, "ARCHIVE_ROOT", custom_root)  # type: ignore[attr-defined]

    assert paths_module.archive_path(date(2026, 4, 25), segment=CRYPTO) == (
        custom_root / "crypto" / "2026" / "04" / "2026-04-25.md"
    )


# ---------------------------------------------------------------------------
# Boundaries
# ---------------------------------------------------------------------------


def test_archive_path_year_start_boundary() -> None:
    """January 1 — minimum month + day."""
    assert archive_path(date(2026, 1, 1)) == Path("archive/2026/01/2026-01-01.md")


def test_archive_path_year_end_boundary() -> None:
    """December 31 — maximum month + day."""
    assert archive_path(date(2026, 12, 31)) == Path("archive/2026/12/2026-12-31.md")


def test_archive_path_leap_day() -> None:
    """Feb 29 of a leap year — ``date(2024, 2, 29)`` is valid."""
    assert archive_path(date(2024, 2, 29)) == Path("archive/2024/02/2024-02-29.md")


def test_archive_path_pre_2000_pass_through() -> None:
    """Year < 2000 is not clamped; u3 trusts upstream date validation
    (DEBT-002 tracks the model-side bounds enforcement).
    """
    assert archive_path(date(1999, 12, 31)) == Path("archive/1999/12/1999-12-31.md")


def test_archive_path_far_future_pass_through() -> None:
    """Year >> current is not clamped — same DEBT-002 trust contract."""
    assert archive_path(date(9999, 12, 31)) == Path("archive/9999/12/9999-12-31.md")


# ---------------------------------------------------------------------------
# Purity
# ---------------------------------------------------------------------------


def test_archive_path_is_pure_no_filesystem_check() -> None:
    """``archive_path`` does NOT verify that the directory exists or
    that the file is writable. It is path arithmetic only — no I/O.
    Pinning this lets callers safely use the result inside `assert`s
    or test fixtures without filesystem precondition setup.
    """
    # If the path were stat-checked, this would either fail (path is
    # not absolute and the cwd has no `archive/...` tree) or succeed
    # spuriously. We don't care which — we care that NO exception is
    # raised on a path that very probably does not exist on disk.
    result = archive_path(date(1999, 12, 31))
    # Sanity: the result is a Path object.
    assert isinstance(result, Path)


def test_archive_path_uses_archive_root_constant(monkeypatch: object) -> None:
    """The function reads ``ARCHIVE_ROOT`` at call time. Tests can
    redirect by monkeypatching the module attribute (Step 5.3 design
    decision option (a)).
    """
    from investo.publisher import paths as paths_module

    # Local import so the monkeypatch landing site is the module-level
    # constant, not this file's import-time copy.
    custom_root = Path("/tmp/custom-archive")
    # ``monkeypatch`` is a pytest fixture — typed as ``object`` here
    # so the helper stays runtime-introspectable; type-narrow inside.
    assert hasattr(monkeypatch, "setattr")
    monkeypatch.setattr(paths_module, "ARCHIVE_ROOT", custom_root)  # type: ignore[attr-defined]

    assert paths_module.archive_path(date(2026, 4, 25)) == (
        custom_root / "2026" / "04" / "2026-04-25.md"
    )


def test_normalize_archive_publish_path_keeps_relative_path() -> None:
    path = Path("archive/us-equity/2026/04/2026-04-25.md")

    assert normalize_archive_publish_path(path, archive_root=Path("/tmp/run/archive")) == path


def test_normalize_archive_publish_path_converts_absolute_under_archive_root() -> None:
    archive_root = Path("/tmp/run/archive")

    assert normalize_archive_publish_path(
        archive_root / "us-equity" / "2026" / "04" / "2026-04-25.md",
        archive_root=archive_root,
    ) == Path("archive/us-equity/2026/04/2026-04-25.md")


def test_normalize_archive_publish_path_rejects_absolute_outside_archive_root() -> None:
    with pytest.raises(ValueError, match="outside archive root"):
        normalize_archive_publish_path(
            Path("/tmp/other/archive/us-equity/2026/04/2026-04-25.md"),
            archive_root=Path("/tmp/run/archive"),
        )


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def test_paths_module_exports_expected_names() -> None:
    from investo.publisher import paths as paths_module

    assert hasattr(paths_module, "ARCHIVE_ROOT")
    assert hasattr(paths_module, "archive_path")
    assert hasattr(paths_module, "normalize_archive_publish_path")
