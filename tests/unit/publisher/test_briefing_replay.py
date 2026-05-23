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
    status_label: str = "정상",
    failed: int = 0,
    body: str = (
        "## ⑥ 오늘의 관전 포인트\n\n"
        "- 확인 소스: FRED · 10Y 금리 4.5% 상회 시 변동성 부담 여부를 확인합니다.\n"
    ),
) -> None:
    path = (
        root / segment / f"{target.year:04d}" / f"{target.month:02d}" / f"{target.isoformat()}.md"
    )
    path.parent.mkdir(parents=True)
    path.write_text(
        "# title\n\n"
        "> **오늘의 결론**: 정상 결론입니다.\n"
        f"> **핵심 동인**: {driver}\n"
        "> **주의할 점**: 정상 주의입니다.\n\n"
        f"> **데이터 상태**: {status_label} — 설명입니다.\n"
        "> **소스 카운트**: 수집 대상 5 / 성공 1 / 0건 0 / "
        f"실패 {failed} / 본문 사용 2\n\n"
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


def test_replay_flags_quality_consistency_contradiction(tmp_path: Path) -> None:
    """u69 — a failed/limited body with a healthier history row fails replay."""
    target = date(2026, 5, 22)
    archive = tmp_path / "archive"
    for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO):
        _write_segment(archive, segment, target, status_label="실패", failed=3)
    history = archive / "_meta" / "quality_history.jsonl"
    history.parent.mkdir(parents=True)
    history.write_text(
        json.dumps(
            {
                "date": target.isoformat(),
                "worst_severity": "normal",
                "total_failed_sources": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    findings = replay_generated_briefing_quality(target, archive_root=archive)

    error_codes = {f.code for f in findings if f.severity == "error"}
    assert "quality.status_mismatch" in error_codes
    assert "quality.failed_count_mismatch" in error_codes


def test_replay_consistent_bundle_has_no_quality_consistency_errors(tmp_path: Path) -> None:
    target = date(2026, 5, 22)
    archive = tmp_path / "archive"
    for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO):
        _write_segment(archive, segment, target, status_label="정상", failed=0)
    history = archive / "_meta" / "quality_history.jsonl"
    history.parent.mkdir(parents=True)
    history.write_text(
        json.dumps(
            {
                "date": target.isoformat(),
                "worst_severity": "normal",
                "total_failed_sources": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    findings = replay_generated_briefing_quality(target, archive_root=archive)

    consistency_errors = {
        f.code for f in findings if f.severity == "error" and f.code.startswith("quality.")
    }
    assert consistency_errors == set()
    # quality_page absent → recorded as skipped warning, never an error.
    skipped = {f.code for f in findings if f.code == "quality.quality_page_missing"}
    assert skipped == {"quality.quality_page_missing"}
