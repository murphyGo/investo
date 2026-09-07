"""U144 Step 2.1 phase-one text producer composition."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given, seed, settings
from hypothesis import strategies as st

import investo.publisher.public_document as public_document_module
from investo._internal.briefing_extract import CONCLUSION_PREFIX, DRIVER_PREFIX, extract_conclusion
from investo._internal.disclaimer import DISCLAIMER_CRYPTO
from investo._internal.public_quality_language import project_public_quality_language
from investo._internal.summary_quality import repair_first_viewport_summary
from investo._internal.surface_quality import find_surface_quality_issues
from investo.models import Briefing, SourceOutcome
from investo.models.facts import VerifiedFactBundle
from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
    SegmentCoverage,
)
from investo.publisher.errors import SurfaceQualityError
from investo.publisher.public_document import (
    FinalizedPublicDocument,
    PublicDocumentContext,
    PublicDocumentDraft,
    _assemble_phase_one_body_evidence,
    _assemble_phase_one_presentation_briefings,
    _assemble_phase_one_reader_briefings,
    finalize_public_bundle,
)
from investo.publisher.reader_format import (
    bound_first_viewport_summary_lines,
    reflow_first_viewport,
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


def _summary_briefing(value: str, *, surface: str = "conclusion") -> Briefing:
    briefing = _phase_one_briefing()
    markdown = briefing.rendered_markdown
    if surface == "conclusion":
        markdown = markdown.replace(f"{CONCLUSION_PREFIX} -", f"{CONCLUSION_PREFIX} {value}")
    elif surface == "driver":
        markdown = markdown.replace("금리 경로를 확인합니다.", value, 1)
    else:
        marker = "- " if surface == "tldr_list" else ""
        markdown = markdown.replace(
            "## ① 요약",
            f"## 한눈에 보기\n\n{marker}{value}\n- 추가 발표 확인\n- 수급 확인\n\n## ① 요약",
        )
    return briefing.model_copy(update={"rendered_markdown": markdown})


def _summary_value(markdown: str, surface: str) -> str:
    if surface.startswith("tldr"):
        return (
            markdown.split("## 한눈에 보기\n", 1)[1]
            .strip()
            .splitlines()[0]
            .removeprefix("- ")
            .strip()
        )
    prefix = CONCLUSION_PREFIX if surface == "conclusion" else DRIVER_PREFIX
    return next(
        line.removeprefix(prefix).strip()
        for line in markdown.splitlines()
        if line.startswith(prefix)
    )


def _finalizer_context() -> PublicDocumentContext:
    return PublicDocumentContext(
        target_date=_TARGET_DATE,
        expected_segments=(CRYPTO,),
        input_absences={},
        anchors_by_segment={},
        items_by_segment={},
        coverage_by_segment={
            CRYPTO: SegmentCoverage(
                segment=CRYPTO,
                status="normal",
                item_count=1,
                source_count=1,
                categories=("news",),
                missing_categories=(),
            )
        },
        source_outcomes=(),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=_TARGET_DATE),
        entity_observed_at_utc=datetime(2026, 7, 21, tzinfo=UTC),
    )


def _with_finalizer_diagnostics(briefing: Briefing) -> Briefing:
    markdown = briefing.rendered_markdown.replace(
        "## ⑦ 면책조항",
        "<details><summary>수집/품질 진단</summary>\n정상 수집\n</details>\n\n## ⑦ 면책조항",
    )
    return briefing.model_copy(update={"rendered_markdown": markdown})


@pytest.mark.parametrize("surface", ["conclusion", "driver", "tldr_list", "tldr_plain"])
@pytest.mark.parametrize("segment", [DOMESTIC_EQUITY, US_EQUITY, CRYPTO])
def test_u153_presentation_bounds_all_owned_surfaces_after_summary_repair(
    surface: str, segment: MarketSegment
) -> None:
    first = "가격은 **3.14%** 상승으로 확인했습니다."
    value = first + " " + "후속 수급과 지표 확인 " * 20
    briefing = _summary_briefing(value, surface=surface)
    original = briefing.rendered_markdown
    assembled = _assemble_phase_one_presentation_briefings(
        {segment: briefing}, target_date=_TARGET_DATE, active_segments=(segment,)
    )[segment]
    assert _summary_value(assembled.rendered_markdown, surface) == first + " 본문 참고."
    assert briefing.rendered_markdown == original
    assert (
        _assemble_phase_one_presentation_briefings(
            {segment: assembled}, target_date=_TARGET_DATE, active_segments=(segment,)
        )[segment]
        is assembled
    )


def test_u153_bounding_consumes_repair_output_not_its_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repair = repair_first_viewport_summary
    first = "정상 요약을 확인했습니다."
    long_repair = first + " " + "추가 설명 " * 30
    calls: list[str] = []

    def repair_with_long_result(markdown: str) -> str:
        calls.append("repair")
        return repair(markdown).replace("확인된 요약이 부족합니다.", long_repair)

    monkeypatch.setattr(
        public_document_module, "repair_first_viewport_summary", repair_with_long_result
    )
    assembled = _assemble_phase_one_presentation_briefings(
        {CRYPTO: _phase_one_briefing()}, target_date=_TARGET_DATE, active_segments=(CRYPTO,)
    )[CRYPTO]
    assert calls == ["repair"]
    assert extract_conclusion(assembled.rendered_markdown) == first + " 본문 참고."


@pytest.mark.parametrize("surface", ["conclusion", "driver"])
def test_u153_real_summary_repair_cleanup_is_bounded(surface: str) -> None:
    first = "정상 요약을 확인했습니다."
    malformed = "**" + first + " " + "추가 설명 " * 30
    briefing = _summary_briefing(malformed, surface=surface)
    repaired = repair_first_viewport_summary(briefing.rendered_markdown)
    assert len(_summary_value(repaired, surface)) > 90
    assembled = _assemble_phase_one_presentation_briefings(
        {CRYPTO: briefing}, target_date=_TARGET_DATE, active_segments=(CRYPTO,)
    )[CRYPTO]
    assert _summary_value(assembled.rendered_markdown, surface) == first + " 본문 참고."


def test_u153_late_bounding_preserves_caution_body_and_diagnostics() -> None:
    first = "시장 흐름을 확인했습니다."
    briefing = _summary_briefing(first + " " + "후속 설명 " * 30)
    caution = "주의 문구를 확인했습니다. " + "변동성을 점검합니다. " * 15
    markdown = briefing.rendered_markdown.replace("변동성을 점검합니다.", caution, 1)
    protected = "<details><summary>수집/품질 진단</summary>\n기관의 본문 참고.\n</details>\n\n"
    markdown = markdown.replace("## ① 요약", protected + "## ① 요약", 1)
    briefing = briefing.model_copy(update={"rendered_markdown": markdown})
    assembled = _assemble_phase_one_presentation_briefings(
        {CRYPTO: briefing}, target_date=_TARGET_DATE, active_segments=(CRYPTO,)
    )[CRYPTO]
    rendered = assembled.rendered_markdown
    assert f"> **주의할 점**: {caution}" in rendered
    assert protected in rendered
    assert (
        rendered.split("## ① 요약", 1)[1].split("## ⑦", 1)[0]
        == markdown.split("## ① 요약", 1)[1].split("## ⑦", 1)[0]
    )


def test_u153_shared_bounding_helper_preserves_legacy_reflow_caution_default() -> None:
    value = "주의 문구를 확인했습니다. " + "후속 수급 설명 " * 20
    markdown = f"> **주의할 점**: {value}\n## ① 요약\n본문"
    assert bound_first_viewport_summary_lines(markdown, final_assembly=True) == markdown
    assert bound_first_viewport_summary_lines(markdown) == reflow_first_viewport(markdown)
    assert "> **주의할 점**: 주의 문구를 확인했습니다. 본문 참고." in reflow_first_viewport(
        markdown
    )


@pytest.mark.parametrize("surface", ["conclusion", "driver", "tldr_list", "tldr_plain"])
def test_u153_late_bounding_preserves_unrepaired_link_findings(surface: str) -> None:
    # The typed repair historically sees a pipe-leading value as protected;
    # late bounding must not discard its actual callout/list link finding.
    value = "| [자료](https://example.com/...) " + "추가 설명 " * 30
    assembled = _assemble_phase_one_presentation_briefings(
        {CRYPTO: _summary_briefing(value, surface=surface)},
        target_date=_TARGET_DATE,
        active_segments=(CRYPTO,),
    )[CRYPTO]
    assert _summary_value(assembled.rendered_markdown, surface) == value.rstrip()


@pytest.mark.parametrize("surface", ["conclusion", "driver", "tldr_list", "tldr_plain"])
@pytest.mark.parametrize(
    "value, code",
    [
        ("| input_hash=redacted 기관의 본문 참고.", "trace.fragment"),
        ("| alias:issuer 기관의 본문 참고.", "watchlist.matcher_reason.public"),
        ("| 금리 **+**3% 기관의 본문 참고.", "markdown.broken_numeric_bold"),
        ("| " + "추가 설명 " * 350 + "input_hash=redacted 기관의 본문 참고.", "trace.fragment"),
        ("| price missing input_hash=redacted 기관의 본문 참고.", "trace.fragment"),
        (
            "| price missing [자료](https://example.com/...) 기관의 본문 참고.",
            "markdown.href_ellipsis",
        ),
    ],
)
def test_u153_late_bounding_does_not_erase_other_retained_blockers(
    surface: str, value: str, code: str
) -> None:
    assembled = _assemble_phase_one_presentation_briefings(
        {CRYPTO: _summary_briefing(value, surface=surface)},
        target_date=_TARGET_DATE,
        active_segments=(CRYPTO,),
    )[CRYPTO]
    assert _summary_value(assembled.rendered_markdown, surface) == value
    assert code in {
        issue.code for issue in find_surface_quality_issues(f"{CONCLUSION_PREFIX} {value}\n## ①")
    }


def test_u153_real_finalizer_keeps_repair_output_bounded_until_seal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = "시장 방향을 확인했습니다."
    expected = first + " 본문 참고."
    long_repair = first + " " + "추가 수급 설명 " * 30
    repair = repair_first_viewport_summary
    evidence = public_document_module._assemble_phase_one_body_evidence
    seal = public_document_module._seal_document
    stages: list[str] = []

    def repair_with_long_result(markdown: str) -> str:
        stages.append("summary_repair")
        return repair(markdown).replace("확인된 요약이 부족합니다.", long_repair)

    def check_accounting_input(
        briefing: Briefing,
        *,
        segment: MarketSegment,
        source_outcomes: Sequence[SourceOutcome],
        verified_facts: Sequence[object],
    ) -> Briefing:
        assert extract_conclusion(briefing.rendered_markdown) == expected
        stages.append("accounting")
        return evidence(
            briefing,
            segment=segment,
            source_outcomes=source_outcomes,
            verified_facts=verified_facts,
        )

    def observe_phase(
        label: str,
        handler: Callable[[PublicDocumentDraft, PublicDocumentContext], PublicDocumentDraft],
    ) -> Callable[[PublicDocumentDraft, PublicDocumentContext], PublicDocumentDraft]:
        def observed(
            draft: PublicDocumentDraft, context: PublicDocumentContext
        ) -> PublicDocumentDraft:
            assert extract_conclusion(draft.layout.markdown) == expected
            result = handler(draft, context)
            assert extract_conclusion(result.layout.markdown) == expected
            stages.append(label)
            return result

        return observed

    def observe_seal(
        draft: PublicDocumentDraft,
        *,
        staged_artifact_ids: Sequence[str] = (),
        warnings: Sequence[str] = (),
    ) -> FinalizedPublicDocument:
        assert draft.phase == "validated"
        before = draft.layout.markdown
        result = seal(draft, staged_artifact_ids=staged_artifact_ids, warnings=warnings)
        assert result.briefing.rendered_markdown == before
        assert extract_conclusion(before) == expected
        stages.append("seal")
        return result

    monkeypatch.setattr(
        public_document_module, "repair_first_viewport_summary", repair_with_long_result
    )
    monkeypatch.setattr(
        public_document_module, "_assemble_phase_one_body_evidence", check_accounting_input
    )
    for name, label in (
        ("_project_assembled_draft", "project"),
        ("_repair_projected_draft", "containment"),
        ("_validate_repaired_draft", "validate"),
    ):
        monkeypatch.setattr(
            public_document_module,
            name,
            observe_phase(label, getattr(public_document_module, name)),
        )
    monkeypatch.setattr(public_document_module, "_seal_document", observe_seal)
    briefing = _with_finalizer_diagnostics(_phase_one_briefing())
    result = finalize_public_bundle({CRYPTO: briefing}, context=_finalizer_context())
    assert len(result.documents) == 1
    assert stages == ["summary_repair", "accounting", "project", "containment", "validate", "seal"]


@pytest.mark.parametrize("surface", ["conclusion", "driver"])
@pytest.mark.parametrize("protected", ["", "수집/품질 진단", "투자 자문이 아닙니다"])
def test_u153_real_finalizer_cannot_expand_repair_exposed_public_label(
    surface: str, protected: str
) -> None:
    value = "| price mi**ssing** " + "상황을 살핍니다. " * (5 if protected else 6)
    value += f"{protected} ROS" if protected else "ROS"
    assert len(value) <= 90
    briefing = _with_finalizer_diagnostics(_summary_briefing(value, surface=surface))
    # Pin the actual late-repair expansion, not a synthetic phase stub.
    repaired_value = _summary_value(
        repair_first_viewport_summary(briefing.rendered_markdown), surface
    )
    assert len(project_public_quality_language(repaired_value)) > 90
    document = finalize_public_bundle({CRYPTO: briefing}, context=_finalizer_context()).documents[0]
    actual = _summary_value(document.briefing.rendered_markdown, surface)
    assert len(actual) <= 90
    assert "price missing" not in actual
    assert actual.endswith("본문 참고.")


@seed(15320260907)
@settings(max_examples=60, print_blob=True)
@given(
    fragment=st.sampled_from(("price mi**ssing**", "source mi**ssing**", "확인 소스 미**상**")),
    sentence_count=st.integers(min_value=2, max_value=12),
    surface=st.sampled_from(("conclusion", "driver")),
    protected=st.sampled_from(("", "수집/품질 진단", "투자 자문이 아닙니다")),
)
def test_u153_repair_exposed_projection_is_stable_after_bounding_property(
    fragment: str, sentence_count: int, surface: str, protected: str
) -> None:
    value = f"| {fragment} " + "상황을 살핍니다. " * sentence_count + f"{protected} ROS"
    assembled = _assemble_phase_one_presentation_briefings(
        {CRYPTO: _summary_briefing(value, surface=surface)},
        target_date=_TARGET_DATE,
        active_segments=(CRYPTO,),
    )[CRYPTO]
    actual = _summary_value(assembled.rendered_markdown, surface)
    assert len(actual) <= 90
    assert project_public_quality_language(actual) == actual
    assert (
        _assemble_phase_one_presentation_briefings(
            {CRYPTO: assembled}, target_date=_TARGET_DATE, active_segments=(CRYPTO,)
        )[CRYPTO]
        is assembled
    )


@seed(15320260907)
@settings(max_examples=60, print_blob=True)
@given(
    number=st.decimals(
        min_value="0.01", max_value="999.99", places=2, allow_nan=False, allow_infinity=False
    ),
    surface=st.sampled_from(("conclusion", "driver", "tldr_list", "tldr_plain")),
    tail_size=st.integers(min_value=15, max_value=35),
)
def test_u153_phase_one_bounding_property(number: Decimal, surface: str, tail_size: int) -> None:
    first = f"가격은 **{number}%** 상승으로 확인했습니다."
    value = first + " " + "추가 설명 " * tail_size
    assembled = _assemble_phase_one_presentation_briefings(
        {CRYPTO: _summary_briefing(value, surface=surface)},
        target_date=_TARGET_DATE,
        active_segments=(CRYPTO,),
    )[CRYPTO]
    actual = _summary_value(assembled.rendered_markdown, surface)
    assert len(actual) <= 90
    assert actual == first + " 본문 참고."
    assert (
        _assemble_phase_one_presentation_briefings(
            {CRYPTO: assembled}, target_date=_TARGET_DATE, active_segments=(CRYPTO,)
        )[CRYPTO]
        is assembled
    )
