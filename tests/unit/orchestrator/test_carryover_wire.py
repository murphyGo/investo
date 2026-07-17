"""u52 — orchestrator-level integration pins.

C7 — segment isolation: a parser failure for one segment yields an
empty :class:`BriefingCarryover` for that segment without affecting
the others.

C8 — idempotent same-day re-run: calling
:func:`_inject_carryover_into_segments` twice with the same input
yields byte-equal output (FR-006).

These tests target the orchestrator helpers directly (no
``run_pipeline`` setup) so they stay fast and the assertion surface
is unambiguous.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from investo.briefing.disclaimer import DISCLAIMER, append_disclaimer
from investo.briefing.pipeline import _render_timestamp_watermark
from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY, MarketSegment
from investo.models import Briefing, BriefingCarryover, CarryoverItem
from investo.orchestrator.pipeline import (
    _inject_carryover_into_segments,
    _load_carryover_for_run,
)
from investo.publisher.carryover import CARRYOVER_BLOCK_HEADING


def _write_archive(
    archive_root: Path,
    segment: str,
    day: date,
    body: str,
) -> Path:
    path = archive_root / segment / f"{day.year:04d}" / f"{day.month:02d}" / f"{day.isoformat()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


_HEADER = (
    "# 2026-05-07 시황\n\n"
    "**기준 시각**: 2026-05-07 NY · "
    "수집창 2026-05-07T04:00Z ~ 2026-05-08T04:00Z (종료 미포함)\n\n"
    "> **오늘의 결론**: 보합. [관망]\n"
    "> **핵심 동인**: 거시.\n"
    "> **주의할 점**: FOMC.\n\n"
)


def _briefing_md() -> str:
    return _HEADER + "## ⑥ 오늘의 관전 포인트\n\n" + "1. **ARM 어닝**: 분기 실적 발표 예고.\n"


def _stub_briefing_body(target_date: date, segment: MarketSegment) -> str:
    return (
        f"# {target_date.isoformat()} 시황\n\n"
        f"{_render_timestamp_watermark(target_date, segment)}\n\n"
        "> **오늘의 결론**: 강세 마감. [강세]\n"
        "> **핵심 동인**: 거시.\n"
        "> **주의할 점**: 메모.\n\n"
        "## ① 요약\n\n①본문.\n\n"
        "---\n\n"
        "## ② 전일 핵심 이슈\n\n②본문.\n\n"
        "---\n\n"
        "## ③ 섹터/수급 동향\n\n③.\n\n"
        "---\n\n"
        "## ④ 지표·이벤트\n\n④.\n\n"
        "---\n\n"
        "## ⑤ 주요 종목\n\n⑤.\n\n"
        "---\n\n"
        "## ⑥ 오늘의 관전 포인트\n\n⑥.\n\n"
    )


def _stub_briefing(
    target_date: date,
    segment: MarketSegment = US_EQUITY,
) -> Briefing:
    body = _stub_briefing_body(target_date, segment)
    full = append_disclaimer(body)
    return Briefing(
        target_date=target_date,
        market_summary="①본문.",
        key_issues="②본문.",
        sector_flow="③.",
        indicators_events="④.",
        notable_tickers="⑤.",
        today_watch="⑥.",
        disclaimer=DISCLAIMER,
        rendered_markdown=full,
    )


@pytest.fixture
def archive_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "archive"
    monkeypatch.setattr("investo.publisher.paths.ARCHIVE_ROOT", root)
    return root


def test_load_carryover_for_run_isolates_segments(archive_root: Path) -> None:
    """Only us-equity carries a prior file → other segments stay empty."""
    yesterday = date(2026, 5, 7)
    today = date(2026, 5, 8)
    _write_archive(archive_root, "us-equity", yesterday, _briefing_md())

    candidates_by_segment: dict[MarketSegment, tuple] = {
        DOMESTIC_EQUITY: (),
        US_EQUITY: (),
        CRYPTO: (),
    }
    result = _load_carryover_for_run(today, candidates_by_segment)
    assert set(result.keys()) == {DOMESTIC_EQUITY, US_EQUITY, CRYPTO}
    assert not result[US_EQUITY].is_empty
    assert result[DOMESTIC_EQUITY].is_empty
    assert result[CRYPTO].is_empty


def test_inject_carryover_into_segments_idempotent_same_day_rerun(
    archive_root: Path,
) -> None:
    """C8 — twice through the injector yields byte-equal markdown."""
    today = date(2026, 5, 8)
    bundle = BriefingCarryover(
        prior_resolved=(
            CarryoverItem(
                event_type="earnings",
                ticker_or_topic="ARM",
                originated_date=date(2026, 5, 6),
                expected_date=date(2026, 5, 7),
                status="resolved",
                note=None,
            ),
        ),
        prior_unresolved=(),
        lookback_days=1,
    )
    carryover_by_segment = {
        DOMESTIC_EQUITY: BriefingCarryover(prior_resolved=(), prior_unresolved=(), lookback_days=0),
        US_EQUITY: bundle,
        CRYPTO: BriefingCarryover(prior_resolved=(), prior_unresolved=(), lookback_days=0),
    }
    briefings = {
        segment: _stub_briefing(today, segment) for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)
    }
    once = _inject_carryover_into_segments(
        briefings,
        carryover_by_segment=carryover_by_segment,
    )
    twice = _inject_carryover_into_segments(
        once,
        carryover_by_segment=carryover_by_segment,
    )
    for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO):
        assert once[segment].rendered_markdown == twice[segment].rendered_markdown


def test_inject_carryover_into_segments_empty_bundle_leaves_markdown_unchanged(
    archive_root: Path,
) -> None:
    """An empty :class:`BriefingCarryover` skips injection."""
    today = date(2026, 5, 8)
    empty_bundle = BriefingCarryover(prior_resolved=(), prior_unresolved=(), lookback_days=0)
    carryover_by_segment = {US_EQUITY: empty_bundle}
    briefings = {US_EQUITY: _stub_briefing(today)}
    out = _inject_carryover_into_segments(
        briefings,
        carryover_by_segment=carryover_by_segment,
    )
    assert out[US_EQUITY].rendered_markdown == briefings[US_EQUITY].rendered_markdown
    assert CARRYOVER_BLOCK_HEADING not in out[US_EQUITY].rendered_markdown


def test_inject_carryover_into_segments_populated_bundle_injects_block(
    archive_root: Path,
) -> None:
    """Populated bundle → block appears between §② and §③."""
    today = date(2026, 5, 8)
    bundle = BriefingCarryover(
        prior_resolved=(
            CarryoverItem(
                event_type="earnings",
                ticker_or_topic="ARM",
                originated_date=date(2026, 5, 6),
                expected_date=date(2026, 5, 7),
                status="resolved",
                note=None,
            ),
        ),
        prior_unresolved=(),
        lookback_days=1,
    )
    carryover_by_segment = {US_EQUITY: bundle}
    briefings = {US_EQUITY: _stub_briefing(today)}
    out = _inject_carryover_into_segments(
        briefings,
        carryover_by_segment=carryover_by_segment,
    )
    markdown = out[US_EQUITY].rendered_markdown
    block_idx = markdown.find(CARRYOVER_BLOCK_HEADING)
    section_two_idx = markdown.find("## ② 전일 핵심 이슈")
    section_three_idx = markdown.find("## ③ 섹터/수급 동향")
    assert -1 < section_two_idx < block_idx < section_three_idx
    # Disclaimer preserved (not touched by injection).
    assert DISCLAIMER.strip() in markdown
