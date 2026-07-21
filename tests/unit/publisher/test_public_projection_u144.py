"""U144 Step 3.1 terminal public-language projection tests."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from investo.models import Briefing
from investo.models.facts import VerifiedFactBundle
from investo.models.segments import DOMESTIC_EQUITY, SegmentCoverage
from investo.publisher.public_document import (
    PublicDocumentContext,
    PublicDocumentLayout,
    PublicRegionExpectation,
    _new_generated_draft,
    _project_assembled_draft,
    _transition_draft,
)
from investo.publisher.reader_format.public_projection import project_public_markdown

_TARGET_DATE = date(2026, 7, 21)


def _expectation() -> PublicRegionExpectation:
    return PublicRegionExpectation(
        target_date=_TARGET_DATE,
        segment=DOMESTIC_EQUITY,
        segmented_mode=True,
        supplement_ids=(),
        shared_macro_required=False,
        crypto_indicators_required=False,
        channel_anchors_required=False,
        daily_thesis_required=False,
        anchor_table_required=False,
    )


def _markdown(*, newline: str = "\n") -> str:
    lines = (
        f"# {_TARGET_DATE.isoformat()} 국내 증시 시황",
        "",
        "**세그먼트**: [국내](/domestic)",
        "",
        "> 정보 제공용 자동 시황이며 매매 권유가 아닙니다.",
        "",
        "## ① 요약",
        "",
        "데이터 부족입니다.",
        "",
        "```text",
        "```not-a-close",
        "데이터 부족",
        "```",
        "",
        "## ② 전일 핵심 이슈",
        "",
        "이슈 본문",
        "",
        "## ③ 섹터/수급 동향",
        "",
        "수급 본문",
        "",
        "## ④ 지표·이벤트",
        "",
        "이벤트 본문",
        "",
        "## ⑤ 주요 종목",
        "",
        "종목 본문",
        "",
        "## ⑥ 오늘의 관전 포인트",
        "",
        "| 구분 | 상태 |",
        "|---|---|",
        "| 상방 | 상방 데이터 부족 |",
        "",
        "<details><summary>수집/품질 진단</summary>",
        "데이터 부족",
        "</details>",
        "",
        "## ⑦ 면책조항",
        "",
        "데이터 부족 원문은 면책조항 byte 보존 대상입니다.",
    )
    return newline.join(lines) + newline


def _layout(*, newline: str = "\n") -> PublicDocumentLayout:
    return PublicDocumentLayout.reindex(_markdown(newline=newline), expectation=_expectation())


def _context() -> PublicDocumentContext:
    return PublicDocumentContext(
        target_date=_TARGET_DATE,
        expected_segments=(DOMESTIC_EQUITY,),
        input_absences={},
        anchors_by_segment={},
        items_by_segment={},
        coverage_by_segment={
            DOMESTIC_EQUITY: SegmentCoverage(
                segment=DOMESTIC_EQUITY,
                status="normal",
                item_count=1,
                source_count=1,
                categories=(),
                missing_categories=(),
            )
        },
        source_outcomes=(),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=_TARGET_DATE),
        entity_observed_at_utc=datetime(2026, 7, 21, tzinfo=UTC),
    )


def test_projection_uses_region_policy_and_projects_reader_visible_tables() -> None:
    layout = _layout()
    diagnostics = next(
        region for region in layout.regions if region.region_id == "diagnostics:quality"
    )
    disclaimer = next(
        region for region in layout.regions if region.region_id == "disclaimer:canonical"
    )
    protected_before = (
        layout.markdown[diagnostics.start : diagnostics.end],
        layout.markdown[disclaimer.start : disclaimer.end],
    )

    projected = project_public_markdown(layout, limitation_reasons=("limited_coverage",))

    assert "데이터 부족입니다" not in projected.markdown
    assert "| 상방 | 상방 데이터 부족 |" not in projected.markdown
    assert "| 상방 | 상방 수집 근거가 제한적입니다 |" in projected.markdown
    assert "```text\n```not-a-close\n데이터 부족\n```" in projected.markdown
    projected_diagnostics = next(
        region for region in projected.regions if region.region_id == "diagnostics:quality"
    )
    assert (
        projected.markdown[projected_diagnostics.start : projected_diagnostics.end]
        == protected_before[0]
    )
    projected_disclaimer = next(
        region for region in projected.regions if region.region_id == "disclaimer:canonical"
    )
    assert (
        projected.markdown[projected_disclaimer.start : projected_disclaimer.end]
        == protected_before[1]
    )


def test_projection_is_byte_idempotent_and_preserves_crlf() -> None:
    layout = _layout(newline="\r\n")

    projected = project_public_markdown(layout, limitation_reasons=("limited_coverage",))
    repeated = project_public_markdown(projected, limitation_reasons=("limited_coverage",))

    assert repeated is projected
    assert "\r\n" in projected.markdown
    assert "\n" not in projected.markdown.replace("\r\n", "")


@pytest.mark.parametrize(
    ("opening", "not_a_close", "closing"),
    (("```text", "```not-a-close", "```"), ("~~~text", "~~~not-a-close", "~~~")),
)
def test_projection_preserves_fenced_body_lines_with_nonclosing_marker_suffix(
    opening: str,
    not_a_close: str,
    closing: str,
) -> None:
    markdown = _markdown().replace(
        "```text\n```not-a-close\n데이터 부족\n```",
        f"{opening}\n{not_a_close}\n데이터 부족\n{closing}",
    )
    layout = PublicDocumentLayout.reindex(markdown, expectation=_expectation())

    projected = project_public_markdown(layout, limitation_reasons=("limited_coverage",))

    assert f"{opening}\n{not_a_close}\n데이터 부족\n{closing}" in projected.markdown


def test_projection_rejects_duplicate_typed_reasons() -> None:
    with pytest.raises(ValueError, match="unique and ordered"):
        project_public_markdown(
            _layout(),
            limitation_reasons=("limited_coverage", "limited_coverage"),
        )


def test_phase_two_handler_projects_only_after_assembled_transition() -> None:
    layout = _layout()
    briefing = Briefing(
        target_date=_TARGET_DATE,
        market_summary="요약",
        key_issues="이슈",
        sector_flow="수급",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer="데이터 부족 원문은 면책조항 byte 보존 대상입니다.",
        rendered_markdown=layout.markdown,
    )
    generated = _new_generated_draft(
        briefing,
        segment=DOMESTIC_EQUITY,
        layout=layout,
    )
    assembled = _transition_draft(
        generated,
        next_phase="assembled",
        limitation_reasons=("limited_coverage",),
    )

    projected = _project_assembled_draft(assembled, _context())

    assert projected.phase == "projected"
    assert projected.limitation_reasons == ("limited_coverage",)
    assert "데이터 부족입니다" not in projected.layout.markdown
    with pytest.raises(ValueError, match="invalid public-document phase transition"):
        _project_assembled_draft(projected, _context())
