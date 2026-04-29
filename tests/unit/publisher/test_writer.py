"""Tests for ``investo.publisher.writer.write_briefing`` (FR-003 + NFR-004).

Covered behaviors:

* Happy path — markdown lands at ``archive/YYYY/MM/YYYY-MM-DD.md``
  with byte-exact content.
* Disclaimer-missing block (NFR-004) — raises
  ``PublisherDisclaimerError`` and writes nothing.
* FR-006 same-day idempotent overwrite — second write with the same
  ``target_date`` replaces the first.
* Atomic-write contract — when ``os.replace`` raises ``OSError``,
  the destination file is unaffected and the tmp file is cleaned up.
* ``mkdir(parents=True)`` bootstraps a fresh year/month tree.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from investo.briefing.disclaimer import DISCLAIMER
from investo.models import Briefing
from investo.publisher import paths as paths_module
from investo.publisher.errors import PublisherDisclaimerError, PublisherIOError
from investo.publisher.writer import write_briefing

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TARGET_DATE = date(2026, 4, 25)


def _build_briefing(*, with_disclaimer: bool = True) -> Briefing:
    """Construct a `Briefing` whose rendered_markdown does or does not
    contain DISCLAIMER. All other fields are placeholder text that
    satisfies the model's ``min_length=1`` validators.
    """
    body = (
        "## ① 요약\n오늘 시장 요약\n\n"
        "## ② 전일 핵심 이슈\n핵심 이슈\n\n"
        "## ③ 섹터/수급 동향\n섹터 동향\n\n"
        "## ④ 지표·이벤트\n지표 이벤트\n\n"
        "## ⑤ 주요 종목\n종목 본문\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전 포인트\n\n"
    )
    rendered = body + (DISCLAIMER if with_disclaimer else "no disclaimer here")
    return Briefing(
        target_date=_TARGET_DATE,
        market_summary="요약",
        key_issues="이슈",
        sector_flow="섹터",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer=DISCLAIMER,
        rendered_markdown=rendered,
    )


@pytest.fixture
def archive_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ``paths.ARCHIVE_ROOT`` to a tmp directory for the
    duration of the test (Step 5.3 design decision option (a)).
    """
    root = tmp_path / "archive"
    monkeypatch.setattr(paths_module, "ARCHIVE_ROOT", root)
    return root


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_write_briefing_writes_markdown_to_archive_path(archive_root: Path) -> None:
    """Markdown lands at ``archive_root/2026/04/2026-04-25.md`` with
    byte-exact content.
    """
    briefing = _build_briefing()

    written_path = write_briefing(briefing, _TARGET_DATE)

    expected = archive_root / "2026" / "04" / "2026-04-25.md"
    assert written_path == expected
    assert written_path.exists()
    assert written_path.read_text(encoding="utf-8") == briefing.rendered_markdown


def test_write_briefing_creates_nested_year_month_dirs(
    archive_root: Path,
) -> None:
    """A fresh ``archive_root`` with no `2026/04/` tree → write
    succeeds; the year + month dirs are created by ``mkdir(parents=
    True)``.
    """
    assert not (archive_root / "2026").exists()

    briefing = _build_briefing()
    written_path = write_briefing(briefing, _TARGET_DATE)

    assert written_path.exists()
    assert (archive_root / "2026" / "04").is_dir()


def test_write_briefing_returns_path_for_orchestrator_to_stage(
    archive_root: Path,
) -> None:
    """The returned ``Path`` is what u5 orchestrator hands to
    ``commit_and_push`` as the file-to-stage. Pin the type contract.
    """
    briefing = _build_briefing()
    written_path = write_briefing(briefing, _TARGET_DATE)

    assert isinstance(written_path, Path)
    # Path is relative (production runs from repo root); the
    # archive_root fixture redirects to tmp_path, so the result is
    # absolute under tmp.
    assert written_path.is_absolute()


# ---------------------------------------------------------------------------
# NFR-004 disclaimer-missing hard block
# ---------------------------------------------------------------------------


def test_write_briefing_blocks_when_disclaimer_missing(
    archive_root: Path,
) -> None:
    """A briefing whose ``rendered_markdown`` lacks DISCLAIMER raises
    PublisherDisclaimerError and writes NOTHING. The model itself
    doesn't enforce the cross-field invariant (DEBT-001), so the
    runtime check is the safety net.
    """
    briefing = _build_briefing(with_disclaimer=False)

    with pytest.raises(PublisherDisclaimerError) as exc:
        write_briefing(briefing, _TARGET_DATE)

    assert exc.value.target_date == _TARGET_DATE
    # No archive file was created.
    expected = archive_root / "2026" / "04" / "2026-04-25.md"
    assert not expected.exists()
    # Year/month dirs may or may not be created — the contract is
    # only that the destination FILE is not written. Don't pin the
    # parent-dir state (mkdir runs after verify in the impl, but a
    # future refactor could swap that).


# ---------------------------------------------------------------------------
# FR-006 same-day idempotent overwrite
# ---------------------------------------------------------------------------


def test_write_briefing_same_day_overwrites_previous(archive_root: Path) -> None:
    """A second write with the same ``target_date`` replaces the
    first. Git history retains both versions; in-place backup is NOT
    a publisher concern.
    """
    first = _build_briefing()
    second_md = first.rendered_markdown.replace("오늘 시장 요약", "수정된 요약")
    second = first.model_copy(update={"rendered_markdown": second_md})

    path1 = write_briefing(first, _TARGET_DATE)
    path2 = write_briefing(second, _TARGET_DATE)

    assert path1 == path2
    assert path1.read_text(encoding="utf-8") == second_md
    assert "수정된 요약" in path1.read_text(encoding="utf-8")
    assert "오늘 시장 요약" not in path1.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Atomic-write contract
# ---------------------------------------------------------------------------


def test_write_briefing_atomicity_when_replace_fails(
    archive_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Monkeypatch ``os.replace`` to raise ``OSError`` mid-write.
    The destination file MUST NOT exist; the tmp sibling MUST be
    cleaned up; ``PublisherIOError`` is raised with the original
    cause attached.
    """
    briefing = _build_briefing()

    def boom(src: object, dst: object) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr("investo.publisher.writer.os.replace", boom)

    with pytest.raises(PublisherIOError) as exc:
        write_briefing(briefing, _TARGET_DATE)

    expected_path = archive_root / "2026" / "04" / "2026-04-25.md"
    assert not expected_path.exists()
    # tmp sibling must be cleaned up.
    tmp_path = expected_path.with_suffix(expected_path.suffix + ".tmp")
    assert not tmp_path.exists()
    # Error context preserved.
    assert exc.value.target_date == _TARGET_DATE
    assert exc.value.path == expected_path
    assert isinstance(exc.value.cause, OSError)


def test_write_briefing_atomicity_does_not_leave_destination_corrupted(
    archive_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If a previous successful write exists and a second write fails
    mid-replace, the destination keeps its prior content (atomic
    guarantee).
    """
    first = _build_briefing()
    write_briefing(first, _TARGET_DATE)

    # Now fail the second write.
    second_md = first.rendered_markdown.replace("오늘 시장 요약", "BROKEN — should not land")
    second = first.model_copy(update={"rendered_markdown": second_md})

    def boom(src: object, dst: object) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr("investo.publisher.writer.os.replace", boom)

    with pytest.raises(PublisherIOError):
        write_briefing(second, _TARGET_DATE)

    # Destination keeps the FIRST write's content.
    expected_path = archive_root / "2026" / "04" / "2026-04-25.md"
    assert expected_path.read_text(encoding="utf-8") == first.rendered_markdown


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def test_writer_module_exports_expected_names() -> None:
    from investo.publisher import writer as writer_module

    assert hasattr(writer_module, "write_briefing")


def test_write_briefing_uses_archive_root_at_call_time(archive_root: Path) -> None:
    """The function reads ``ARCHIVE_ROOT`` (via ``archive_path``) at
    call time, so the test fixture's ``monkeypatch.setattr`` takes
    effect. Confirms the Step 5.3 (a) testability claim works
    end-to-end through the writer too.
    """
    briefing = _build_briefing()
    written_path = write_briefing(briefing, _TARGET_DATE)

    # Path is under the redirected archive_root, NOT the production
    # ``Path("archive")`` default.
    assert str(written_path).startswith(str(archive_root))


# ---------------------------------------------------------------------------
# Sanity — verify-first ordering
# ---------------------------------------------------------------------------


def test_write_briefing_verify_runs_before_mkdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If verify fails, ``mkdir`` should NOT have run. We can detect
    this by pointing ``ARCHIVE_ROOT`` at a known-empty subtree and
    checking that no directory was created on the disclaimer-failure
    path.
    """
    fresh = tmp_path / "totally-fresh"
    monkeypatch.setattr(paths_module, "ARCHIVE_ROOT", fresh)
    briefing = _build_briefing(with_disclaimer=False)

    with pytest.raises(PublisherDisclaimerError):
        write_briefing(briefing, _TARGET_DATE)

    # No part of the archive tree should have been created.
    assert not fresh.exists()


# ---------------------------------------------------------------------------
# Cleanup safety — tmp file from prior crashed run
# ---------------------------------------------------------------------------


def test_write_briefing_succeeds_when_stale_tmp_exists(
    archive_root: Path,
) -> None:
    """If a prior run crashed and left a `.md.tmp` sibling, the next
    write must still succeed (the new tmp content overwrites and
    `os.replace` atomically promotes it).
    """
    expected = archive_root / "2026" / "04" / "2026-04-25.md"
    expected.parent.mkdir(parents=True, exist_ok=True)
    stale_tmp = expected.with_suffix(expected.suffix + ".tmp")
    stale_tmp.write_text("STALE CRASH RESIDUE", encoding="utf-8")

    briefing = _build_briefing()
    write_briefing(briefing, _TARGET_DATE)

    assert expected.read_text(encoding="utf-8") == briefing.rendered_markdown
    # The stale tmp was overwritten + replaced; no leftover.
    assert not stale_tmp.exists()
