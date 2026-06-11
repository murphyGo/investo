"""u100 integration tests for segment reader-format surface quality."""

from __future__ import annotations

from datetime import date

from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.segments import US_EQUITY
from investo.models import Briefing
from investo.publisher.segment_reader_format import apply_reader_format_to_segments


def _briefing(markdown: str) -> Briefing:
    full = f"{markdown}\n\n{DISCLAIMER}\n"
    return Briefing(
        target_date=date(2026, 6, 11),
        market_summary="요약 [혼재]",
        key_issues="핵심",
        sector_flow="섹터",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer=DISCLAIMER,
        rendered_markdown=full,
    )


def test_segment_reader_repairs_bad_token_before_publish() -> None:
    briefing = _briefing(
        "# title\n\n> **오늘의 결론**: 불강한성 확대 ...\n\n## ① 요약\n본문입니다.\n"
    )

    out = apply_reader_format_to_segments(
        {US_EQUITY: briefing},
        anchors_by_segment={},
    )[US_EQUITY].rendered_markdown

    assert "불강한성" not in out
    assert "불확실성" in out


def test_segment_reader_repairs_recoverable_first_viewport_link_fragment() -> None:
    briefing = _briefing(
        "# title\n\n> **오늘의 결론**: [broken link](https://example.com\n\n## ① 요약\n본문"
    )

    out = apply_reader_format_to_segments(
        {US_EQUITY: briefing},
        anchors_by_segment={},
    )[US_EQUITY].rendered_markdown

    assert "[broken link](" not in out
    assert "broken link" in out


def test_segment_reader_repairs_first_viewport_trace_fragments() -> None:
    briefing = _briefing(
        "# title\n\n"
        "> **오늘의 결론**: 정책 변수 확인 필요\n"
        "- `input_hash`: `1ee42e89b281`\n"
        "stage1_hash=abcdef123456\n\n"
        "## ① 요약\n본문"
    )

    out = apply_reader_format_to_segments(
        {US_EQUITY: briefing},
        anchors_by_segment={},
    )[US_EQUITY].rendered_markdown

    assert "input_hash" not in out
    assert "stage1_hash" not in out
    assert "정책 변수 확인 필요" in out


def test_segment_reader_repairs_unrecoverable_first_viewport_link_marker() -> None:
    briefing = _briefing("# title\n\n> **오늘의 결론**: [broken link\n\n## ① 요약\n본문")

    out = apply_reader_format_to_segments(
        {US_EQUITY: briefing},
        anchors_by_segment={},
    )[US_EQUITY].rendered_markdown

    assert "[broken link" not in out
    assert "broken link" in out
