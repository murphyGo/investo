"""Tests for u44 monthly retrospective rendering."""

from __future__ import annotations

from pathlib import Path

from investo.briefing.monthly_retrospective import render_monthly_retrospective


def _write_day(root: Path, segment: str, day: int, conclusion: str) -> None:
    path = root / segment / "2026" / "04" / f"2026-04-{day:02d}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# test\n\n> **오늘의 결론**: {conclusion}\n", encoding="utf-8")


def test_monthly_retrospective_renders_rows_distribution_and_top_tickers(tmp_path: Path) -> None:
    archive = tmp_path / "archive"
    for day in range(1, 31):
        tag = "[강세]" if day % 2 else "[약세]"
        _write_day(archive, "us-equity", day, f"NVDA와 AAPL 중심 흐름 {tag}")

    body = render_monthly_retrospective(2026, 4, archive_root=archive)

    assert body.count("2026-04-") == 30
    assert "## 결론 톤 분포" in body
    assert "[강세]" in body
    assert "NVDA: 30회" in body
    assert "AAPL: 30회" in body


def test_monthly_retrospective_empty_month_placeholder(tmp_path: Path) -> None:
    body = render_monthly_retrospective(2026, 4, archive_root=tmp_path / "archive")

    assert "데이터 부족" in body


def test_monthly_retrospective_is_idempotent(tmp_path: Path) -> None:
    archive = tmp_path / "archive"
    for day in range(1, 8):
        _write_day(archive, "crypto", day, f"BTC 혼조 {day} [혼조]")

    first = render_monthly_retrospective(2026, 4, archive_root=archive)
    second = render_monthly_retrospective(2026, 4, archive_root=archive)

    assert first == second
