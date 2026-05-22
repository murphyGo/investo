"""Tests for offline generated-briefing replay checks."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.publisher.briefing_replay import replay_generated_briefing_quality


def _write_segment(
    root: Path,
    segment: str,
    target: date,
    *,
    driver: str = "정상 동인입니다.",
    body: str = (
        "## ⑥ 오늘의 관전 포인트\n\n"
        "- 확인 소스: FRED · 10Y 금리 4.5% 상회 시 변동성 부담 여부를 확인합니다.\n"
    ),
) -> None:
    path = (
        root
        / segment
        / f"{target.year:04d}"
        / f"{target.month:02d}"
        / f"{target.isoformat()}.md"
    )
    path.parent.mkdir(parents=True)
    path.write_text(
        "# title\n\n"
        "> **오늘의 결론**: 정상 결론입니다.\n"
        f"> **핵심 동인**: {driver}\n"
        "> **주의할 점**: 정상 주의입니다.\n\n"
        "**세그먼트**: [국내 증시](x) | [미국 증시](x) | [크립토](x)\n\n"
        f"{body}\n\n{DISCLAIMER}",
        encoding="utf-8",
    )


def test_replay_reports_first_viewport_and_watchlist_errors(tmp_path: Path) -> None:
    target = date(2026, 5, 21)
    archive = tmp_path / "archive"
    _write_segment(
        archive,
        US_EQUITY,
        target,
        driver="### S&P 흐름",
        body="## ⑥ 오늘의 관전 포인트\n\n- BTC: BTM earnings 확인\n",
    )
    history = archive / "_meta" / "quality_history.jsonl"
    history.parent.mkdir(parents=True)
    history.write_text(json.dumps({"date": target.isoformat()}) + "\n", encoding="utf-8")

    findings = replay_generated_briefing_quality(
        target,
        archive_root=archive,
        segments=(US_EQUITY,),
    )

    codes = {finding.code for finding in findings}
    assert "first-viewport" in codes
    assert "watchlist-btc-btm" in codes


def test_replay_reports_missing_segments_and_missing_history(tmp_path: Path) -> None:
    target = date(2026, 5, 21)
    archive = tmp_path / "archive"
    _write_segment(archive, DOMESTIC_EQUITY, target)

    findings = replay_generated_briefing_quality(
        target,
        archive_root=archive,
        segments=(DOMESTIC_EQUITY, CRYPTO),
    )

    codes = {finding.code for finding in findings}
    assert "segment-missing" in codes
    assert "quality-history-missing" in codes
