"""U144 Step 2.1 phase-one text producer composition."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from investo._internal.briefing_extract import CONCLUSION_PREFIX
from investo._internal.disclaimer import DISCLAIMER_CRYPTO
from investo.models import Briefing
from investo.models.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.publisher.errors import SurfaceQualityError
from investo.publisher.public_document import (
    _assemble_phase_one_body_evidence,
    _assemble_phase_one_presentation_briefings,
    _assemble_phase_one_reader_briefings,
)
from investo.publisher.verifier import SHORT_DISCLAIMER_CRYPTO
from investo.publisher.watchpoint_matrix import WatchpointRenderResult
from tests._helpers.briefings import build_briefing

_TARGET_DATE = date(2026, 7, 21)


def _phase_one_briefing() -> Briefing:
    base = build_briefing(target_date=_TARGET_DATE)
    markdown = (
        f"# {_TARGET_DATE.isoformat()} 크립토 시황\n\n"
        "**세그먼트**: [국내 증시](old) | [미국 증시](old) | [크립토](old)\n\n"
        f"{CONCLUSION_PREFIX} -\n"
        "> **핵심 동인**: 금리 경로를 확인합니다.\n"
        "> **주의할 점**: 변동성을 점검합니다.\n"
        "> **소스 카운트**: 수집 대상 1 / 성공 1 / 0건 0 / 실패 0 / 본문 사용 미집계\n\n"
        "## ① 요약\n\n"
        "[FRED](https://fred.stlouisfed.org/series/DGS10) 근거를 확인했습니다.\n\n"
        "## ② 전일 핵심 이슈\n이슈\n\n"
        "## ③ 섹터/수급 동향\n수급\n\n"
        "## ④ 지표·이벤트\n이벤트\n\n"
        "## ⑤ 주요 종목\n종목\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전\n\n"
        "## ⑦ 면책조항\n비표준 면책 문구\n"
    )
    return base.model_copy(update={"rendered_markdown": markdown})


def test_phase_one_presentation_orders_nav_disclaimers_and_summary_repair() -> None:
    briefing = _phase_one_briefing()

    assembled = _assemble_phase_one_presentation_briefings(
        {CRYPTO: briefing},
        target_date=_TARGET_DATE,
        active_segments=(CRYPTO,),
    )[CRYPTO]

    markdown = assembled.rendered_markdown
    assert (
        "**세그먼트**: 국내 증시(미발행) | 미국 증시(미발행) | "
        f"[크립토]({_TARGET_DATE.isoformat()}.md)"
    ) in markdown
    assert SHORT_DISCLAIMER_CRYPTO in markdown.splitlines()[:30]
    assert DISCLAIMER_CRYPTO in markdown
    assert "비표준 면책 문구" not in markdown
    assert f"{CONCLUSION_PREFIX} -" not in markdown

    repeated = _assemble_phase_one_presentation_briefings(
        {CRYPTO: assembled},
        target_date=_TARGET_DATE,
        active_segments=(CRYPTO,),
    )[CRYPTO]
    assert repeated is assembled


def test_phase_one_body_evidence_renders_after_presentation() -> None:
    assembled = _assemble_phase_one_presentation_briefings(
        {CRYPTO: _phase_one_briefing()},
        target_date=_TARGET_DATE,
        active_segments=(CRYPTO,),
    )[CRYPTO]

    with_evidence = _assemble_phase_one_body_evidence(
        assembled,
        segment=CRYPTO,
        source_outcomes=(),
        verified_facts=(),
    )

    assert "본문 사용 1" in with_evidence.rendered_markdown
    assert (
        _assemble_phase_one_body_evidence(
            with_evidence,
            segment=CRYPTO,
            source_outcomes=(),
            verified_facts=(),
        )
        is with_evidence
    )


@pytest.mark.parametrize(
    "active_segments",
    (
        (),
        (US_EQUITY, DOMESTIC_EQUITY),
        (CRYPTO, CRYPTO),
    ),
)
def test_phase_one_rejects_invalid_active_segment_sets(
    active_segments: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError, match="active_segments"):
        _assemble_phase_one_presentation_briefings(
            {},
            target_date=_TARGET_DATE,
            active_segments=active_segments,  # type: ignore[arg-type]
        )


def test_segment_reader_is_internal_phase_one_collaborator() -> None:
    source = Path("src/investo/publisher/segment_reader_format.py").read_text(encoding="utf-8")
    pipeline_source = Path("src/investo/orchestrator/pipeline.py").read_text(encoding="utf-8")

    assert "SurfaceQualityError" not in source
    assert "find_surface_quality_issues" not in source
    assert "investo.publisher.segment_reader_format" not in pipeline_source


def test_phase_one_reader_boundary_preserves_surface_fail_close() -> None:
    base = _phase_one_briefing()
    briefing = base.model_copy(
        update={
            "rendered_markdown": base.rendered_markdown.replace(
                "금리 경로를 확인합니다.",
                "[자료](https://example.com/...)",
                1,
            )
        }
    )

    with pytest.raises(SurfaceQualityError) as exc_info:
        _assemble_phase_one_reader_briefings(
            {CRYPTO: briefing},
            anchors_by_segment={},
        )

    assert {issue.code for issue in exc_info.value.issues} == {"markdown.href_ellipsis"}


def test_phase_one_reader_boundary_reports_typed_watchpoint_result() -> None:
    observed: list[tuple[str, WatchpointRenderResult]] = []

    rewritten = _assemble_phase_one_reader_briefings(
        {CRYPTO: _phase_one_briefing()},
        anchors_by_segment={},
        _watchpoint_result_observer=lambda segment, result: observed.append((segment, result)),
    )

    assert set(rewritten) == {CRYPTO}
    assert len(observed) == 1
    segment, result = observed[0]
    assert segment == CRYPTO
    assert result.state == "limited"
    assert result.usable_card_count == 0
    assert result.limitation_reasons == ("watchpoint_unavailable",)
