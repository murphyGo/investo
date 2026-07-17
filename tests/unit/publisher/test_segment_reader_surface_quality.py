"""u100 integration tests for segment reader-format surface quality."""

from __future__ import annotations

from datetime import date

import pytest

import investo.publisher.segment_reader_format as segment_reader_format
from investo._internal.summary_quality import repair_first_viewport_summary
from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.segments import US_EQUITY
from investo.models import Briefing
from investo.publisher.errors import SurfaceQualityError
from investo.publisher.reader_format import apply_reader_format, reflow_first_viewport
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


def test_legacy_watermark_bracket_is_removed_by_surface_artifact_repair_u132(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy_watermark = "**기준 시각**: 2026-06-30 NY · [2026-06-30T04:00Z, 2026-07-01T04:00Z)"
    malformed_watermark = legacy_watermark.replace("[", "")
    markdown = (
        "# title\n\n"
        f"{legacy_watermark}\n\n"
        "> **오늘의 결론**: 정책 변수 확인이 필요합니다.\n"
        "> **핵심 동인**: 금리 경로가 시장 방향을 좌우합니다.\n"
        "> **주의할 점**: 단기 변동성을 점검합니다.\n\n"
        "## ① 요약\n본문입니다."
    )

    reader_formatted = apply_reader_format(markdown, segment=US_EQUITY)
    reflowed = reflow_first_viewport(reader_formatted, segment=US_EQUITY)
    summary_repaired = repair_first_viewport_summary(reflowed)

    assert legacy_watermark in reader_formatted
    assert legacy_watermark in reflowed
    assert legacy_watermark in summary_repaired

    captured: dict[str, str] = {}
    real_repair = segment_reader_format.repair_surface_artifacts

    def traced_repair(text: str) -> str:
        captured["input"] = text
        captured["output"] = real_repair(text)
        return captured["output"]

    monkeypatch.setattr(segment_reader_format, "repair_surface_artifacts", traced_repair)

    with pytest.raises(SurfaceQualityError) as exc_info:
        apply_reader_format_to_segments(
            {US_EQUITY: _briefing(markdown)},
            anchors_by_segment={},
        )

    assert legacy_watermark in captured["input"]
    assert legacy_watermark not in captured["output"]
    assert malformed_watermark in captured["output"]
    assert any(issue.code == "watermark.window_bracket" for issue in exc_info.value.issues)


def test_segment_reader_repairs_u112_bad_particle_and_numeric_bold() -> None:
    briefing = _briefing(
        "# title\n\n"
        "> **오늘의 결론**: 시장 민감도을 점검하고 **-**0.04%**p** 둔화를 확인합니다.\n\n"
        "## ① 요약\n본문"
    )

    out = apply_reader_format_to_segments(
        {US_EQUITY: briefing},
        anchors_by_segment={},
    )[US_EQUITY].rendered_markdown

    assert "민감도을" not in out
    assert "민감도를" in out
    assert "**-0.04%p**" in out


def test_segment_reader_blocks_u112_href_ellipsis() -> None:
    briefing = _briefing(
        "# title\n\n> **오늘의 결론**: [자료](https://example.com/...)\n\n## ① 요약\n본문"
    )

    try:
        apply_reader_format_to_segments({US_EQUITY: briefing}, anchors_by_segment={})
    except SurfaceQualityError as exc:
        assert any(issue.code == "markdown.href_ellipsis" for issue in exc.issues)
    else:  # pragma: no cover - assertion clarity
        raise AssertionError("expected SurfaceQualityError")
