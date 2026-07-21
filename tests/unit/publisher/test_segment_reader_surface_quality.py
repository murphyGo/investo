"""u100 integration tests for segment reader-format surface quality."""

from __future__ import annotations

from datetime import date

import pytest

import investo.publisher.public_document as public_document
import investo.publisher.segment_reader_format as segment_reader_format
from investo._internal.summary_quality import repair_first_viewport_summary
from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.segments import DOMESTIC_EQUITY, US_EQUITY, MarketSegment
from investo.models import Briefing
from investo.publisher.compliance_language import ComplianceHit, ComplianceLanguageError
from investo.publisher.errors import SurfaceQualityError
from investo.publisher.public_document import _assemble_phase_one_reader_briefings
from investo.publisher.reader_format import apply_reader_format, reflow_first_viewport
from investo.publisher.segment_reader_format import apply_reader_format_to_segments


def _briefing(markdown: str, *, target_date: date = date(2026, 6, 11)) -> Briefing:
    full = f"{markdown}\n\n{DISCLAIMER}\n"
    return Briefing(
        target_date=target_date,
        market_summary="요약 [혼재]",
        key_issues="핵심",
        sector_flow="섹터",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer=DISCLAIMER,
        rendered_markdown=full,
    )


def _watermarked_markdown(watermark: str) -> str:
    return (
        "# title\n\n"
        f"{watermark}\n\n"
        "> **오늘의 결론**: 정책 변수 확인이 필요합니다. [혼재]\n"
        "> **핵심 동인**: 금리 경로가 시장 방향을 좌우합니다.\n"
        "> **주의할 점**: 단기 변동성을 점검합니다.\n\n"
        "## ① 요약\n본문입니다."
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
        _assemble_phase_one_reader_briefings(
            {US_EQUITY: _briefing(markdown, target_date=date(2026, 6, 30))},
            anchors_by_segment={},
        )

    assert legacy_watermark in captured["input"]
    assert legacy_watermark not in captured["output"]
    assert malformed_watermark in captured["output"]
    assert any(issue.code == "watermark.window_bracket" for issue in exc_info.value.issues)


def test_segment_reader_accepts_u132_watermark_contract() -> None:
    watermark = (
        "**기준 시각**: 2026-06-30 NY · 수집창 2026-06-30T04:00Z ~ 2026-07-01T04:00Z (종료 미포함)"
    )

    output = apply_reader_format_to_segments(
        {
            US_EQUITY: _briefing(
                _watermarked_markdown(watermark),
                target_date=date(2026, 6, 30),
            )
        },
        anchors_by_segment={},
    )[US_EQUITY].rendered_markdown

    assert output.count(watermark) == 1


@pytest.mark.parametrize(
    "watermark",
    (
        "**기준 시각**: 2026-06-30 NY · 2026-06-30T04:00Z, 2026-07-01T04:00Z)",
        (
            "**기준 시각**: 2026-06-30 NY · "
            "수집창 2026-06-30T04:00Z ~ 2026-07-01T04:00Z (종료 미포함"
        ),
    ),
    ids=("legacy-dangling-parenthesis", "unbalanced-new-contract"),
)
def test_segment_reader_blocks_u132_invalid_watermarks(watermark: str) -> None:
    with pytest.raises(SurfaceQualityError) as exc_info:
        _assemble_phase_one_reader_briefings(
            {
                US_EQUITY: _briefing(
                    _watermarked_markdown(watermark),
                    target_date=date(2026, 6, 30),
                )
            },
            anchors_by_segment={},
        )

    issues = [issue for issue in exc_info.value.issues if issue.code == "watermark.window_bracket"]
    assert len(issues) == 1
    assert issues[0].evidence == watermark


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


def test_compliance_scans_only_raw_and_rendered_watchpoint_shapes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[str] = []
    real_scan = segment_reader_format.scan_compliance
    markdown = (
        "# title\n\n"
        "> **오늘의 결론**: 정책 변수 확인이 필요합니다.\n"
        "> **핵심 동인**: 금리 경로를 확인합니다.\n"
        "> **주의할 점**: 변동성을 점검합니다.\n\n"
        "## ① 요약\n본문입니다.\n\n"
        "## ⑥ 오늘의 관전 포인트\n\n"
        "- 확인 소스: FRED · 10Y 금리가 4.5%를 상회하면 변동성 확대를 관찰; "
        "4.3%를 이탈하면 완화를 확인. 관심 영향: 성장주 민감도를 점검.\n"
    )

    def observe_scan(text: str, segment: MarketSegment) -> object:
        observed.append(text)
        return real_scan(text, segment)

    monkeypatch.setattr(segment_reader_format, "scan_compliance", observe_scan)

    apply_reader_format_to_segments(
        {US_EQUITY: _briefing(markdown)},
        anchors_by_segment={},
    )

    assert len(observed) == 2
    assert "- 확인 소스: FRED" in observed[0]
    assert "#### 관찰 신호:" in observed[1]


def test_public_document_boundary_scans_reader_output_before_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    briefing = _briefing("# title\n\n> **오늘의 결론**: 정책 변수를 확인합니다.\n\n## ① 요약\n본문")
    unsafe = briefing.model_copy(
        update={
            "rendered_markdown": briefing.rendered_markdown.replace(
                "## ① 요약\n본문",
                "## ① 요약\n오늘은 매수 검토가 필요합니다.",
            )
        }
    )

    def unsafe_reader(*args: object, **kwargs: object) -> dict[MarketSegment, Briefing]:
        del args, kwargs
        return {US_EQUITY: unsafe}

    monkeypatch.setattr(public_document, "apply_reader_format_to_segments", unsafe_reader)

    with pytest.raises(ComplianceLanguageError):
        _assemble_phase_one_reader_briefings(
            {US_EQUITY: briefing},
            anchors_by_segment={},
        )


def test_segment_reader_blocks_u112_href_ellipsis() -> None:
    briefing = _briefing(
        "# title\n\n> **오늘의 결론**: [자료](https://example.com/...)\n\n## ① 요약\n본문"
    )

    try:
        _assemble_phase_one_reader_briefings({US_EQUITY: briefing}, anchors_by_segment={})
    except SurfaceQualityError as exc:
        assert any(issue.code == "markdown.href_ellipsis" for issue in exc.issues)
    else:  # pragma: no cover - assertion clarity
        raise AssertionError("expected SurfaceQualityError")


def test_phase_one_surface_block_precedes_later_segment_hard_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_scan = segment_reader_format.scan_compliance
    later_segment_scanned = False

    def fail_later_segment(markdown: str, segment: MarketSegment) -> object:
        nonlocal later_segment_scanned
        if segment == US_EQUITY:
            later_segment_scanned = True
            raise ComplianceLanguageError(
                segment=US_EQUITY,
                hits=(
                    ComplianceHit(
                        phrase="매수 검토",
                        severity="P0",
                        line_no=1,
                        category="action",
                    ),
                ),
            )
        return real_scan(markdown, segment)

    monkeypatch.setattr(segment_reader_format, "scan_compliance", fail_later_segment)
    blocked_first = _briefing(
        "# title\n\n> **오늘의 결론**: [자료](https://example.com/...)\n\n## ① 요약\n본문"
    )
    later_hard_error = _briefing(
        "# title\n\n> **오늘의 결론**: 정책 변수를 확인합니다.\n\n## ① 요약\n본문"
    )

    with pytest.raises(SurfaceQualityError) as exc_info:
        _assemble_phase_one_reader_briefings(
            {
                DOMESTIC_EQUITY: blocked_first,
                US_EQUITY: later_hard_error,
            },
            anchors_by_segment={},
        )

    assert exc_info.value.segment == DOMESTIC_EQUITY
    assert later_segment_scanned is False
