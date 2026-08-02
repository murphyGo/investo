"""u130 Step 5 rendered regression for the 2026-06-30 KOSPI level incident."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.segments import DOMESTIC_EQUITY
from investo.models import Briefing
from investo.publisher.anchor_assertion_gate import scan_anchor_assertions
from investo.publisher.segment_reader_format import apply_reader_format_to_segments

_FIXTURE = (
    Path(__file__).parents[2] / "fixtures" / "u130" / "domestic-stage2-2026-06-30-kospi-level.md"
)
_TARGET = date(2026, 6, 30)


def _raw_stage2_briefing() -> Briefing:
    markdown = _FIXTURE.read_text(encoding="utf-8").rstrip()
    return Briefing(
        target_date=_TARGET,
        market_summary="코스피·코스닥 동시 마감",
        key_issues="외국인 순매도 기조",
        sector_flow="수급 주체별 흐름",
        indicators_events="정책 지표 관찰",
        notable_tickers="공시와 수급 변화",
        today_watch="공개 자료 후속 확인",
        disclaimer=DISCLAIMER,
        rendered_markdown=f"{markdown}\n\n{DISCLAIMER}\n",
    )


def test_2026_06_30_reader_chain_removes_all_unsupported_kospi_levels() -> None:
    raw = _raw_stage2_briefing()
    assert raw.rendered_markdown.count("150.00") == 4

    rendered = apply_reader_format_to_segments(
        {DOMESTIC_EQUITY: raw},
        anchors_by_segment={DOMESTIC_EQUITY: ()},
    )[DOMESTIC_EQUITY].rendered_markdown

    assert "150.00" not in rendered
    assert "코스피 관련 정밀 수치는 이번 회차 코어 데이터 미수집으로 확정할 수 없습니다." in (
        rendered
    )
    assert "외국인 순매도 기조가 이어졌다." in rendered
    assert "지원되는 수급 흐름은 유지됩니다." in rendered
    assert (
        scan_anchor_assertions(
            rendered,
            segment=DOMESTIC_EQUITY,
            available_symbols=(),
        )
        == ()
    )
