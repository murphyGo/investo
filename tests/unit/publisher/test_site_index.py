"""Tests for latest briefing discovery page updates."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from investo.publisher.site_index import update_latest_index_pages


def test_update_latest_index_pages_refreshes_latest_links_and_legacy_label(
    tmp_path: Path,
) -> None:
    site_index = tmp_path / "site_docs/index.md"
    archive_index = tmp_path / "archive/index.md"
    legacy = tmp_path / "archive/2026/05/2026-05-06.md"
    site_index.parent.mkdir(parents=True)
    archive_index.parent.mkdir(parents=True)
    legacy.parent.mkdir(parents=True)
    legacy.write_text("# legacy", encoding="utf-8")
    site_index.write_text(
        "# Investo\n\n"
        "## 최신 시황\n\n"
        "현재 보관된 최신 묶음은 **2026-05-06**입니다.\n\n"
        "- old\n\n"
        "## 다음 섹션\n본문\n",
        encoding="utf-8",
    )
    archive_index.write_text(
        "# 시황 아카이브\n\n"
        "## 최신 시황\n\n"
        "- old\n\n"
        "## 과거 단일 시황\n\n"
        "- [2026-05-06 단일 시황](2026/05/2026-05-06.md)\n\n"
        "## 경로 안내\n본문\n",
        encoding="utf-8",
    )

    changed = update_latest_index_pages(
        date(2026, 5, 7),
        site_index_path=site_index,
        archive_index_path=archive_index,
    )

    assert changed == (site_index, archive_index)
    site = site_index.read_text(encoding="utf-8")
    assert "현재 보관된 최신 묶음은 **2026-05-07**입니다." in site
    assert "archive/domestic-equity/2026/05/2026-05-07.md" in site
    assert "## 다음 섹션" in site

    archive = archive_index.read_text(encoding="utf-8")
    assert "domestic-equity/2026/05/2026-05-07.md" in archive
    assert "과거 단일 시황은 세그먼트 분리 이전 형식입니다." in archive
    assert "2026-05-06 단일 시황 (레거시)" in archive
    assert "## 경로 안내" in archive
