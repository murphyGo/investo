"""Tests for ``investo.publisher.weekly_digest`` (u29 site-discovery-v2)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from investo.briefing.disclaimer import DISCLAIMER
from investo.publisher import weekly_digest as weekly_digest_module
from investo.publisher.errors import PublisherDisclaimerError
from investo.publisher.weekly_digest import (
    publish_weekly_digest,
    update_weekly_index,
    weekly_digest_opt_in,
    weekly_path,
)


@pytest.fixture
def archive_root(tmp_path: Path) -> Path:
    root = tmp_path / "archive"
    (root / "weekly").mkdir(parents=True)
    return root


def _seed_segment_briefing(
    archive_root: Path,
    *,
    segment: str,
    day: date,
    conclusion: str,
) -> None:
    path = archive_root / segment / f"{day.year:04d}" / f"{day.month:02d}" / f"{day.isoformat()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        f"# {day.isoformat()}\n\n"
        f"> **오늘의 결론**: {conclusion}\n"
        f"> **핵심 동인**: x\n"
        f"> **주의할 점**: y\n\n"
        f"## ① 요약\n본문\n\n"
    )
    path.write_text(body + DISCLAIMER, encoding="utf-8")


def test_publish_weekly_digest_aggregates_five_days(archive_root: Path) -> None:
    week_end = date(2026, 5, 8)  # Friday
    # Seed Mon-Fri (5 days) with all three segments.
    week_days = [date(2026, 5, 4 + offset) for offset in range(5)]
    for day in week_days:
        for segment in ("domestic-equity", "us-equity", "crypto"):
            _seed_segment_briefing(
                archive_root,
                segment=segment,
                day=day,
                conclusion=f"{segment} {day.isoformat()} 결론",
            )

    written = publish_weekly_digest(week_end, archive_root=archive_root)

    expected = archive_root / "weekly" / "2026-W19.md"
    assert written == expected
    assert written.exists()
    content = written.read_text(encoding="utf-8")
    # Header + range + per-day section.
    assert "# 2026-W19 주차별 회고" in content
    assert "2026-05-04 ~ 2026-05-08" in content
    for day in week_days:
        assert f"## {day.isoformat()}" in content
        assert f"domestic-equity {day.isoformat()} 결론" in content
        assert f"us-equity {day.isoformat()} 결론" in content
        assert f"crypto {day.isoformat()} 결론" in content
    # Disclaimer footer.
    assert DISCLAIMER in content


def test_publish_weekly_digest_handles_missing_days(archive_root: Path) -> None:
    week_end = date(2026, 5, 8)
    # Only seed Wednesday so Mon/Tue/Thu/Fri report (미발행).
    _seed_segment_briefing(
        archive_root,
        segment="us-equity",
        day=date(2026, 5, 6),
        conclusion="수요일 결론",
    )

    written = publish_weekly_digest(week_end, archive_root=archive_root)
    content = written.read_text(encoding="utf-8")
    assert "수요일 결론" in content
    assert "(미발행)" in content


def test_publish_weekly_digest_is_idempotent(archive_root: Path) -> None:
    week_end = date(2026, 5, 8)
    _seed_segment_briefing(
        archive_root,
        segment="us-equity",
        day=date(2026, 5, 6),
        conclusion="동일 결론",
    )
    a = publish_weekly_digest(week_end, archive_root=archive_root).read_text(encoding="utf-8")
    b = publish_weekly_digest(week_end, archive_root=archive_root).read_text(encoding="utf-8")
    assert a == b


def test_update_weekly_index_lists_known_files_newest_first(
    archive_root: Path,
) -> None:
    weekly_dir = archive_root / "weekly"
    (weekly_dir / "2026-W18.md").write_text("# 18", encoding="utf-8")
    (weekly_dir / "2026-W19.md").write_text("# 19", encoding="utf-8")
    (weekly_dir / "2026-W17.md").write_text("# 17", encoding="utf-8")

    written = update_weekly_index(archive_root=archive_root)
    body = written.read_text(encoding="utf-8")
    lines = [line for line in body.splitlines() if line.startswith("- [2026-")]
    assert lines == [
        "- [2026-W19](2026-W19.md)",
        "- [2026-W18](2026-W18.md)",
        "- [2026-W17](2026-W17.md)",
    ]


def test_update_weekly_index_handles_empty_directory(archive_root: Path) -> None:
    written = update_weekly_index(archive_root=archive_root)
    assert "아직 발행된 회고가 없습니다" in written.read_text(encoding="utf-8")


def test_weekly_path_uses_iso_year_week() -> None:
    assert weekly_path(date(2026, 5, 8)).name == "2026-W19.md"


def test_weekly_digest_opt_in_reads_env_flag() -> None:
    assert weekly_digest_opt_in({"INVESTO_PUBLISH_WEEKLY": "1"}) is True
    assert weekly_digest_opt_in({"INVESTO_PUBLISH_WEEKLY": "0"}) is False
    assert weekly_digest_opt_in({"INVESTO_PUBLISH_WEEKLY": " 1 "}) is True
    assert weekly_digest_opt_in({}) is False


def test_publish_weekly_digest_blocks_when_disclaimer_missing(
    archive_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NFR-004 — the weekly digest must NOT publish if the rendered body
    is missing the canonical disclaimer. This pins the verifier gate that
    mirrors ``write_briefing``'s pre-write check, so a future refactor that
    silently drops the footer (e.g. a renderer change) raises instead of
    publishing a non-compliant retrospective.
    """
    week_end = date(2026, 5, 8)
    _seed_segment_briefing(
        archive_root,
        segment="us-equity",
        day=date(2026, 5, 8),
        conclusion="결론",
    )

    # Force the renderer to emit a body with no disclaimer footer.
    def render_without_disclaimer(week_end_date: date, *, archive_root: Path) -> str:
        return f"# {week_end_date.isoformat()} broken\n\nno footer here\n"

    monkeypatch.setattr(
        weekly_digest_module,
        "_render_weekly_digest",
        render_without_disclaimer,
    )

    with pytest.raises(PublisherDisclaimerError):
        publish_weekly_digest(week_end, archive_root=archive_root)
    # No file written.
    assert not (archive_root / "weekly" / "2026-W19.md").exists()
