"""Tests for latest briefing discovery page updates (u29 site-discovery-v2)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.models import Briefing
from investo.publisher.site_index import (
    HEATMAP_BEGIN,
    HEATMAP_END,
    HERO_BEGIN,
    HERO_END,
    extract_conclusion,
    update_archive_heatmap_section,
    update_index_hero,
    update_latest_index_pages,
    update_segment_archive_index,
)


def _briefing(target_date: date, conclusion: str) -> Briefing:
    body = (
        f"> **오늘의 결론**: {conclusion}\n> **핵심 동인**: x\n> **주의할 점**: y\n\n## ① 요약\nA\n"
    )
    rendered = body + "\n\n" + DISCLAIMER
    return Briefing(
        target_date=target_date,
        market_summary="A",
        key_issues="A",
        sector_flow="A",
        indicators_events="A",
        notable_tickers="A",
        today_watch="A",
        disclaimer=DISCLAIMER,
        rendered_markdown=rendered,
    )


def _seed_index_pages(tmp_path: Path) -> tuple[Path, Path]:
    site_index = tmp_path / "site_docs/index.md"
    archive_index = tmp_path / "archive/index.md"
    legacy = tmp_path / "archive/2026/05/2026-05-06.md"
    site_index.parent.mkdir(parents=True)
    archive_index.parent.mkdir(parents=True)
    legacy.parent.mkdir(parents=True)
    legacy.write_text("# legacy", encoding="utf-8")
    site_index.write_text(
        f"{HERO_BEGIN}\n# placeholder\n{HERO_END}\n\n"
        "## 최신 시황\n\n"
        "현재 보관된 최신 묶음은 **2026-05-06**입니다.\n\n"
        "- old\n\n"
        "## 다음 섹션\n본문\n",
        encoding="utf-8",
    )
    archive_index.write_text(
        f"{HEATMAP_BEGIN}\n## 발행 캘린더\nplaceholder\n{HEATMAP_END}\n\n"
        "## 최신 시황\n\n"
        "- old\n\n"
        "## 과거 단일 시황\n\n"
        "- [2026-05-06 단일 시황](2026/05/2026-05-06.md)\n\n"
        "## 경로 안내\n본문\n",
        encoding="utf-8",
    )
    return site_index, archive_index


def test_update_latest_index_pages_refreshes_legacy_section(tmp_path: Path) -> None:
    site_index, archive_index = _seed_index_pages(tmp_path)

    changed = update_latest_index_pages(
        date(2026, 5, 7),
        site_index_path=site_index,
        archive_index_path=archive_index,
    )

    # site_index + archive_index + 3 segment-archive index pages = 5
    assert site_index in changed
    assert archive_index in changed
    site = site_index.read_text(encoding="utf-8")
    assert "현재 보관된 최신 묶음은 **2026-05-07**입니다." in site
    assert "archive/domestic-equity/2026/05/2026-05-07.md" in site
    assert "## 다음 섹션" in site

    archive = archive_index.read_text(encoding="utf-8")
    assert "domestic-equity/2026/05/2026-05-07.md" in archive
    assert "과거 단일 시황은 세그먼트 분리 이전 형식입니다." in archive
    assert "2026-05-06 단일 시황 (레거시)" in archive
    assert "## 경로 안내" in archive


def test_update_index_hero_inlines_segment_conclusions(tmp_path: Path) -> None:
    site_index, _ = _seed_index_pages(tmp_path)
    target = date(2026, 5, 7)
    briefings = {
        DOMESTIC_EQUITY: _briefing(target, "코스피 단단함."),
        US_EQUITY: _briefing(target, "S&P 강세."),
        CRYPTO: _briefing(target, "BTC 횡보."),
    }

    update_index_hero(target, briefings, site_index_path=site_index)
    body = site_index.read_text(encoding="utf-8")
    assert HERO_BEGIN in body
    assert HERO_END in body
    assert "오늘의 시황 (2026-05-07)" in body
    assert "코스피 단단함." in body
    assert "S&P 강세." in body
    assert "BTC 횡보." in body
    assert "archive/domestic-equity/2026/05/2026-05-07.md" in body


def test_update_latest_index_pages_omits_missing_partial_segments(tmp_path: Path) -> None:
    site_index, archive_index = _seed_index_pages(tmp_path)
    target = date(2026, 5, 7)
    briefings = {
        CRYPTO: _briefing(target, "BTC 횡보."),
    }

    update_latest_index_pages(
        target,
        site_index_path=site_index,
        archive_index_path=archive_index,
        segment_briefings=briefings,
    )

    site = site_index.read_text(encoding="utf-8")
    assert "archive/crypto/2026/05/2026-05-07.md" in site
    assert "archive/domestic-equity/2026/05/2026-05-07.md" not in site
    assert "archive/us-equity/2026/05/2026-05-07.md" not in site

    archive = archive_index.read_text(encoding="utf-8")
    assert "crypto/2026/05/2026-05-07.md" in archive
    assert "domestic-equity/2026/05/2026-05-07.md" not in archive
    assert "us-equity/2026/05/2026-05-07.md" not in archive


def test_update_index_hero_is_idempotent(tmp_path: Path) -> None:
    site_index, _ = _seed_index_pages(tmp_path)
    target = date(2026, 5, 7)
    briefings = {
        DOMESTIC_EQUITY: _briefing(target, "C1"),
        US_EQUITY: _briefing(target, "C2"),
        CRYPTO: _briefing(target, "C3"),
    }
    update_index_hero(target, briefings, site_index_path=site_index)
    a = site_index.read_text(encoding="utf-8")
    update_index_hero(target, briefings, site_index_path=site_index)
    b = site_index.read_text(encoding="utf-8")
    assert a == b


def test_update_archive_heatmap_section_replaces_block(tmp_path: Path) -> None:
    _, archive_index = _seed_index_pages(tmp_path)
    update_archive_heatmap_section(
        '<svg><rect class="u29-cell-normal"/></svg>',
        archive_index_path=archive_index,
    )
    body = archive_index.read_text(encoding="utf-8")
    assert HEATMAP_BEGIN in body
    assert HEATMAP_END in body
    assert "u29-cell-normal" in body
    assert body.index(HEATMAP_BEGIN) < body.index(HEATMAP_END)


def test_update_segment_archive_index_lists_archive_files(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive" / "us-equity"
    (archive_root / "2026" / "05").mkdir(parents=True)
    (archive_root / "2026" / "05" / "2026-05-07.md").write_text("# 2026-05-07", encoding="utf-8")
    (archive_root / "2026" / "05" / "2026-05-06.md").write_text("# 2026-05-06", encoding="utf-8")

    written = update_segment_archive_index(
        US_EQUITY,
        segment_index_path=archive_root / "index.md",
    )
    body = written.read_text(encoding="utf-8")
    assert "# 미국 증시 시황 아카이브" in body
    # Newest first.
    assert body.index("2026-05-07") < body.index("2026-05-06")
    assert "[전체 Archive로 돌아가기](../index.md)" in body


def test_update_segment_archive_index_handles_empty_dir(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive" / "crypto"
    archive_root.mkdir(parents=True)
    written = update_segment_archive_index(
        CRYPTO,
        segment_index_path=archive_root / "index.md",
    )
    assert "현재 표시할 시황이 없습니다." in written.read_text(encoding="utf-8")


def test_extract_conclusion_returns_first_match() -> None:
    body = "> **오늘의 결론**: 결론 본문입니다.\n> **핵심 동인**: x\n"
    assert extract_conclusion(body) == "결론 본문입니다."


def test_extract_conclusion_falls_back_when_missing() -> None:
    assert extract_conclusion("# title\n\nbody") == "결론 인용을 추출하지 못했습니다."
