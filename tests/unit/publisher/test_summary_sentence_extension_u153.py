"""U153 caller and real finalizer/notification acceptance (Steps 1-6).

No production phase or terminal gate is stubbed; no publication or network I/O.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest
from hypothesis import given, seed, settings
from hypothesis import strategies as st

import investo.publisher.public_document as public_document_module
import investo.publisher.segment_reader_format as segment_reader_module
from investo._internal.briefing_extract import (
    CONCLUSION_PREFIX,
    DRIVER_PREFIX,
    FALLBACK_BY_PREFIX,
)
from investo._internal.disclaimer import DISCLAIMER
from investo._internal.public_summary_extract import clean_public_summary_text
from investo._internal.summary_quality import is_unsafe_summary_value
from investo._internal.surface_quality import find_surface_quality_issues, repair_surface_artifacts
from investo._internal.text import bound_at_sentence
from investo.models import Briefing
from investo.models.facts import VerifiedFactBundle
from investo.models.market_anchor import MarketAnchor
from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
    SegmentCoverage,
)
from investo.publisher.public_document import (
    FinalizedPublicDocument,
    PublicDocumentContext,
    finalize_public_bundle,
)
from investo.publisher.reader_format import (
    SNIPPET_MAX_CHARS,
    bound_summary_snippet,
    reflow_first_viewport,
)
from tests._helpers.briefings import build_briefing

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures/u153/summary-sentence-boundary.json"
_UNCHANGED_TAIL = (
    "## ⓪ 오늘의 매크로\n\n"
    "| 지표 | 값 |\n|---|---|\n| 합성 기준선 | 7,499.36 |\n\n"
    "주간 지표는 관측 기간과 발표 시각이 다르므로 기준 날짜를 먼저 확인하고 각 시장의 "
    "거래 시간과 발표 일정을 함께 비교한 뒤 통계가 무엇을 측정했는지 설명한다. "
    "이 문단은 요약이 아닌 매크로 본문이며 요약 길이 제한을 적용하지 않는다.\n\n"
    "## ① 요약\n\n본문의 수급 설명은 그대로 보존한다.\n\n"
    "## ② 전일 핵심 이슈\n\n"
    "[본문 근거](https://example.invalid/body)와 **1.25%**를 확인했다.\n"
    "기관의 본문 참고.\n\n"
    f"## ⑦ 면책조항\n\n{DISCLAIMER}\n"
)


@dataclass(frozen=True)
class SummaryCase:
    id: str
    segment: str
    surface: str
    source: str
    input: str
    expected: str
    pending: str | None


def _load_cases() -> tuple[SummaryCase, ...]:
    data = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    return tuple(SummaryCase(**entry) for entry in data["cases"])


_CASES = _load_cases()


def _document(case: SummaryCase) -> str:
    conclusion = case.input if case.surface == "conclusion" else "시장 흐름을 확인했다."
    driver = case.input if case.surface == "driver" else "금리 흐름을 확인했다."
    tldr = case.input if case.surface.startswith("tldr_") else "수급 방향을 확인했다."
    marker = "" if case.surface == "tldr_plain" else "- "
    return (
        "# 합성 시황\n\n"
        f"{CONCLUSION_PREFIX} {conclusion}\n"
        f"{DRIVER_PREFIX} {driver}\n"
        "> **주의할 점**: 변동성을 확인해야 합니다.\n\n"
        "## 한눈에 보기\n\n"
        f"{marker}{tldr}\n"
        "- 지표 흐름을 확인했다.\n"
        "- 추가 발표를 확인해야 합니다.\n\n"
        f"{_UNCHANGED_TAIL}"
    )


def _target_value(markdown: str, surface: str) -> str:
    if surface.startswith("tldr_"):
        block = markdown.split("## 한눈에 보기\n", 1)[1].split("\n## ", 1)[0]
        return block.strip().splitlines()[0].removeprefix("- ").strip()
    prefix = {"conclusion": CONCLUSION_PREFIX, "driver": DRIVER_PREFIX}[surface]
    for line in markdown.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    raise ValueError(f"missing fixture target: {surface}")


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.id)
def test_summary_sentence_target_contract(case: SummaryCase) -> None:
    rendered = reflow_first_viewport(_document(case), segment=case.segment)
    actual = _target_value(rendered, case.surface)

    assert actual == case.expected
    assert case.pending is None


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.id)
def test_incident_reflow_preserves_non_summary_regions_and_is_stable(case: SummaryCase) -> None:
    rendered = reflow_first_viewport(_document(case), segment=case.segment)

    assert rendered.endswith(_UNCHANGED_TAIL)
    assert reflow_first_viewport(rendered, segment=case.segment) == rendered


@pytest.mark.parametrize(
    "unsafe_sentence",
    (
        "**후속 문장을 확인했다. 계속되는 설명**",
        "[후속 문장을 확인했다. 계속되는 설명](https://example.invalid/a)",
        "(후속 문장을 확인했다. 계속되는 설명)",
        "금리 변화와.",
        "금리 변화와 충돌...",
    ),
)
def test_candidate_rolls_back_to_safe_sentence(unsafe_sentence: str) -> None:
    first = "가격은 **7,499.36**으로 확인했다."
    text = f"{first} {unsafe_sentence} " + "추가 수급 설명 " * 15
    # Put the cap inside the construct or directly after its unsafe ending.
    cap = len(first) + 1 + len(unsafe_sentence.split(" 계속", 1)[0]) + len(" 본문 참고.")

    result = bound_summary_snippet(text, max_chars=cap)

    assert result == first + " 본문 참고."
    assert not is_unsafe_summary_value(result)
    assert bound_summary_snippet(result, max_chars=cap) == result


@pytest.mark.parametrize(
    "text, expected",
    (
        ("시장을 확인했다. 본문 참고. 본문 참고.", "시장을 확인했다. 본문 참고."),
        ("기관의 본문 참고. 본문 참고.", ""),
        ("기관의 ...본문 참고.", ""),
        ("시장을 확인했다. 아직 이어지는 본문 참고.", "시장을 확인했다. 본문 참고."),
        ("본문 참고.", ""),
        ("", ""),
    ),
)
def test_continuation_is_complete_and_not_repeated(text: str, expected: str) -> None:
    assert bound_summary_snippet(text) == expected


@pytest.mark.parametrize("surface", ("conclusion", "driver", "tldr_bullet", "tldr_plain"))
@pytest.mark.parametrize(
    "defect, code",
    (
        ("[링크](https://example.invalid/very...)", "markdown.href_ellipsis"),
        ("[링크](https://example.invalid/unclosed", "markdown.unmatched_link"),
        ("[미완성 링크", "markdown.unmatched_link"),
    ),
)
@pytest.mark.parametrize("padding", ("", " 추가적인 수급 설명" * 15))
def test_existing_link_findings_reach_the_original_owner(
    surface: str, defect: str, code: str, padding: str
) -> None:
    value = f"시장을 확인했다.{padding} {defect}"
    case = replace(_CASES[0], surface=surface, input=value)
    document = _document(case)
    rendered = reflow_first_viewport(document)

    assert _target_value(rendered, surface) == value
    before = [
        issue.evidence for issue in find_surface_quality_issues(document) if issue.code == code
    ]
    after = [
        issue.evidence for issue in find_surface_quality_issues(rendered) if issue.code == code
    ]
    assert before and after == before
    assert reflow_first_viewport(rendered) == rendered


@pytest.mark.parametrize("surface", ("conclusion", "driver", "tldr_bullet"))
@pytest.mark.parametrize(
    "defect, code",
    (
        ("[링크](https://example.invalid/a...)", "markdown.href_ellipsis"),
        ("[미완성 링크", "markdown.unmatched_link"),
    ),
)
def test_pipe_leading_summary_is_not_a_protected_table(
    surface: str, defect: str, code: str
) -> None:
    value = "| 시장을 확인했다. " + "후속 설명 " * 30 + defect
    case = replace(_CASES[0], surface=surface, input=value)
    document = _document(case)
    rendered = reflow_first_viewport(document)

    assert _target_value(rendered, surface) == value
    before = [issue for issue in find_surface_quality_issues(document) if issue.code == code]
    after = [issue for issue in find_surface_quality_issues(rendered) if issue.code == code]
    assert before and after == before


@pytest.mark.parametrize("indent", ("    ", "\t"))
@pytest.mark.parametrize("marker", ("", "- "))
def test_indented_code_heading_does_not_change_tldr_ownership(indent: str, marker: str) -> None:
    long = "시장을 확인했다. " + "후속 수급 설명 " * 15
    protected = f"{indent}## 인용된 제목\n"
    document = f"## 한눈에 보기\n\n{protected}\n{marker}{long}\n## ① 요약\n"

    assert reflow_first_viewport(document) == (
        f"## 한눈에 보기\n\n{protected}\n{marker}시장을 확인했다. 본문 참고.\n## ① 요약\n"
    )


@pytest.mark.parametrize("indent", ("", "   "))
@pytest.mark.parametrize("suffix", ("", "..."))
def test_reference_definition_preserves_body_link_target(indent: str, suffix: str) -> None:
    definition = f"{indent}[source]: https://example.invalid/" + "x" * 100 + suffix
    tail = "## ① 요약\n[본문 근거][source]\n"
    document = f"## 한눈에 보기\n\n{definition}\n{tail}"

    assert reflow_first_viewport(document) == document
    codes = {issue.code for issue in find_surface_quality_issues(document)}
    assert ("markdown.href_ellipsis" in codes) == bool(suffix)


def test_plain_reference_link_definition_keeps_anchored_finding() -> None:
    reference = "[ref]: https://example.invalid/" + "x" * 1600 + "..."
    document = f"## 한눈에 보기\n\n{reference}\n## ① 요약\n"

    assert reflow_first_viewport(document) == document
    assert any(
        issue.code == "markdown.href_ellipsis" for issue in find_surface_quality_issues(document)
    )


@pytest.mark.parametrize("surface", ("conclusion", "driver", "tldr_bullet", "tldr_plain"))
@pytest.mark.parametrize("padding_size", (1540, 1560, 1590))
@pytest.mark.parametrize(
    "link",
    (
        "<https://example.invalid/path...>",
        "[근거](https://example.invalid/path...)",
    ),
)
def test_link_spanning_scanner_fallback_window_remains_visible(
    surface: str, padding_size: int, link: str
) -> None:
    value = "시장을 확인했다. " + "가" * padding_size + " " + link
    case = replace(_CASES[0], surface=surface, input=value)
    document = _document(case)
    rendered = reflow_first_viewport(document)

    assert rendered == document
    assert any(
        issue.code == "markdown.href_ellipsis" for issue in find_surface_quality_issues(rendered)
    )


@pytest.mark.parametrize("indent", ("    ", "\t"))
def test_indented_details_close_restores_summary_ownership(indent: str) -> None:
    long = "시장을 확인했다. " + "후속 수급 설명 " * 15
    protected = f"<details>\n{long}\n{indent}</details>\n"
    document = f"## 한눈에 보기\n{protected}{long}\n## ① 요약\n"

    assert reflow_first_viewport(document) == (
        f"## 한눈에 보기\n{protected}시장을 확인했다. 본문 참고.\n## ① 요약\n"
    )


@pytest.mark.parametrize("surface", ("conclusion", "driver", "tldr_bullet"))
def test_empty_summary_values_use_surface_fallback(surface: str) -> None:
    case = replace(_CASES[0], surface=surface, input="")
    expected = {
        "conclusion": FALLBACK_BY_PREFIX[CONCLUSION_PREFIX],
        "driver": FALLBACK_BY_PREFIX[DRIVER_PREFIX],
        "tldr_bullet": "요약은 본문을 참고하세요.",
    }[surface]

    assert _target_value(reflow_first_viewport(_document(case)), surface) == expected


@pytest.mark.parametrize(
    "next_h2", ("## ⓪ 매크로", "## 출처 진단", "## ① 요약", "##", "## 한눈에 보기")
)
@pytest.mark.parametrize("ending", ("\n", "\r\n"))
def test_next_h2_ends_summary_ownership_without_requiring_section_one(
    next_h2: str, ending: str
) -> None:
    long = "시장을 확인했다. " + "후속 수급 설명 " * 15
    tail = f"{next_h2}\n- {long}\n{long}\n{CONCLUSION_PREFIX} {long}\n"
    document = f"## 한눈에 보기\n{long}\n{tail}".replace("\n", ending)
    rendered = reflow_first_viewport(document)

    assert rendered == (
        f"## 한눈에 보기\n시장을 확인했다. 본문 참고.\n{tail}".replace("\n", ending)
    )


@pytest.mark.parametrize("marker", ("- ", "* ", "+ ", ""))
def test_only_owned_tldr_lines_are_bounded(marker: str) -> None:
    long = "시장을 확인했다. " + "후속 수급 설명 " * 15
    protected = (
        f"| 지표 | {long} |\n"
        f"**기준 시각**: {long}\n**세그먼트**: {long}\n\n"
        "<details><summary>수집/품질 진단</summary>\n"
        f"<details>\n{CONCLUSION_PREFIX} {long}\n</details>\n{long}\n</details>\n"
        f"````markdown\n{CONCLUSION_PREFIX} {long}\n```\n{long}\n````\n"
        f"~~~markdown\n## 인용된 제목\n{long}\n~~~\n"
        f"> 참고: {long}\n![설명](https://example.invalid/diagram)\n"
    )
    document = f"# 시황\n- {long}\n## 한눈에 보기\n{protected}{marker}{long}\n"
    rendered = reflow_first_viewport(document)

    assert rendered == (
        f"# 시황\n- {long}\n## 한눈에 보기\n{protected}{marker}시장을 확인했다. 본문 참고.\n"
    )
    assert reflow_first_viewport(rendered) == rendered


@seed(15320260907)
@settings(max_examples=100, print_blob=True)
@given(
    value=st.decimals(
        min_value="0.01", max_value="99999.99", places=2, allow_nan=False, allow_infinity=False
    ),
    surface=st.sampled_from(("conclusion", "driver", "tldr_bullet", "tldr_plain")),
    style=st.sampled_from(("plain", "bold", "link")),
    repeats=st.integers(min_value=8, max_value=20),
)
def test_long_summary_sentence_cap_safety_and_idempotence_property(
    value: Decimal, surface: str, style: str, repeats: int
) -> None:
    price = f"{value:,.2f}"
    if style == "bold":
        price = f"**{price}**"
    elif style == "link":
        price = f"[{price}](https://example.invalid/a)"
    first = f"가격은 {price} 수준으로 확인했다."
    text = first + " 후속 수급 설명" * repeats
    case = replace(_CASES[0], surface=surface, input=text)
    rendered = reflow_first_viewport(_document(case))
    actual = _target_value(rendered, surface)

    assert len(text) > SNIPPET_MAX_CHARS
    assert actual == first + " 본문 참고."
    assert len(actual) <= SNIPPET_MAX_CHARS
    assert not is_unsafe_summary_value(actual)
    assert actual.count("본문 참고.") == 1
    assert reflow_first_viewport(rendered) == rendered
    assert rendered.endswith(_UNCHANGED_TAIL)


@seed(15320260907)
@settings(max_examples=60, print_blob=True)
@given(
    value=st.decimals(
        min_value="0.01",
        max_value="99999.99",
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    surface=st.sampled_from(("conclusion", "driver", "tldr_bullet", "tldr_plain")),
)
def test_short_decimal_sentence_preservation_property(value: Decimal, surface: str) -> None:
    """PBT-03/07/08: realistic decimal sentences stay intact on every surface."""
    sentence = f"가격은 **{value:,.2f}**로 확인했다."
    case = replace(
        _CASES[0],
        id="generated-decimal",
        surface=surface,
        source="synthetic",
        input=sentence,
        expected=sentence,
        pending=None,
    )
    rendered = reflow_first_viewport(_document(case), segment=case.segment)

    assert _target_value(rendered, surface) == sentence
    assert len(sentence) <= SNIPPET_MAX_CHARS
    assert reflow_first_viewport(rendered, segment=case.segment) == rendered
    assert rendered.endswith(_UNCHANGED_TAIL)


_FINAL_DATE = date(2026, 9, 4)
_SEGMENTS: tuple[MarketSegment, ...] = (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)
_FINAL_BODY = (
    "## ① 요약\n\n본문의 수급 설명은 그대로 보존한다.\n\n"
    "## ② 전일 핵심 이슈\n\n"
    "[본문 근거](https://example.invalid/body)를 확인했다.\n\n"
    "> **그래서 의미는?** 수급 흐름을 함께 확인해야 합니다.\n\n"
    "## ③ 섹터/수급 동향\n\n수급 흐름을 확인했다.\n\n"
    "## ④ 지표·이벤트\n\n발표 일정을 확인했다.\n\n"
    "## ⑤ 주요 종목\n\n주요 자산을 확인했다.\n\n"
    "## ⑥ 오늘의 관전 포인트\n\n추가 발표를 확인한다.\n\n"
    "<details><summary>수집/품질 진단</summary>\n정상 수집\n</details>\n\n"
    f"{DISCLAIMER}\n"
)


def _finalizer_briefing(case: SummaryCase, *, tldr_position: int = 0) -> Briefing:
    markdown = _document(case).replace(_UNCHANGED_TAIL, _FINAL_BODY)
    if case.surface.startswith("tldr_") and tldr_position:
        marker = "" if case.surface == "tldr_plain" else "- "
        block = f"{marker}{case.input}\n- 지표 흐름을 확인했다.\n- 추가 발표를 확인해야 합니다."
        values = ["- 지표 흐름을 확인했다.", "- 추가 발표를 확인해야 합니다."]
        values.insert(tldr_position, f"{marker}{case.input}")
        markdown = markdown.replace(block, "\n".join(values))
    return build_briefing(target_date=_FINAL_DATE).model_copy(
        update={
            # This generated field must never replace terminal-layout derivation.
            "market_summary": "기관의 본문 참고. GENERATED_ONLY_SENTINEL",
            "rendered_markdown": markdown,
        }
    )


def _acceptance_context(*, missing: tuple[MarketSegment, ...] = ()) -> PublicDocumentContext:
    return PublicDocumentContext(
        target_date=_FINAL_DATE,
        expected_segments=_SEGMENTS,
        input_absences={segment: "generation_failed" for segment in missing},
        anchors_by_segment={},
        items_by_segment={},
        coverage_by_segment={
            segment: SegmentCoverage(
                segment=segment,
                status="normal",
                item_count=1,
                source_count=1,
                categories=("news",),
                missing_categories=(),
            )
            for segment in _SEGMENTS
            if segment not in missing
        },
        source_outcomes=(),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=_FINAL_DATE),
        entity_observed_at_utc=datetime(2026, 9, 5, tzinfo=UTC),
    )


def _assert_sealed_summary(document: FinalizedPublicDocument) -> None:
    markdown = document.briefing.rendered_markdown
    conclusion = _target_value(markdown, "conclusion")
    summary = document.notification_summary
    assert summary.segment == document.segment
    assert summary.target_date == _FINAL_DATE
    assert summary.conclusion == clean_public_summary_text(conclusion)
    assert summary.coverage_status == "normal"
    assert len(summary.conclusion) <= SNIPPET_MAX_CHARS
    assert not is_unsafe_summary_value(summary.conclusion)
    assert "GENERATED_ONLY_SENTINEL" not in repr(summary)
    assert document.markdown_sha256 == sha256(markdown.encode("utf-8")).hexdigest()
    assert not any(
        issue.code == "summary.truncated_mid_token"
        for issue in find_surface_quality_issues(markdown)
    )
    for surface in ("conclusion", "driver"):
        assert len(_target_value(markdown, surface)) <= SNIPPET_MAX_CHARS


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.id)
def test_finalized_incident_and_boundary_contract(case: SummaryCase) -> None:
    segment = cast(MarketSegment, case.segment)
    original = _finalizer_briefing(case)
    snapshot = original.model_dump()
    context = _acceptance_context(missing=tuple(s for s in _SEGMENTS if s != segment))
    if case.id == "short-complete-sentence":
        # Synthetic numeric support for the existing literal 1.20% control;
        # do not bypass u149's terminal numeric gate to test text preservation.
        context = replace(
            context,
            anchors_by_segment={
                DOMESTIC_EQUITY: (
                    MarketAnchor(
                        ticker="^KOSPI",
                        close=Decimal("3036"),
                        prev_close=Decimal("3000"),
                        pct=Decimal("1.20"),
                        is_ath=False,
                    ),
                ),
            },
        )

    result = finalize_public_bundle({segment: original}, context=context)

    assert len(result.documents) == 1
    document = result.documents[0]
    assert _target_value(document.briefing.rendered_markdown, case.surface) == case.expected
    _assert_sealed_summary(document)
    assert original.model_dump() == snapshot
    repeated = finalize_public_bundle({segment: document.briefing}, context=context)
    assert repeated.documents[0].briefing.rendered_markdown == document.briefing.rendered_markdown
    assert repeated.documents[0].markdown_sha256 == document.markdown_sha256
    assert repeated.documents[0].notification_summary == document.notification_summary
    control = finalize_public_bundle(
        {segment: _finalizer_briefing(replace(case, input=case.expected))}, context=context
    ).documents[0]
    # Isolate u153 from existing reader transforms: all other final bytes agree.
    assert document.briefing.rendered_markdown == control.briefing.rendered_markdown


@pytest.mark.parametrize("segment", _SEGMENTS)
@pytest.mark.parametrize("surface", ("tldr_bullet", "tldr_plain"))
@pytest.mark.parametrize("position", (0, 1, 2))
def test_finalized_all_three_tldr_positions(
    segment: MarketSegment, surface: str, position: int
) -> None:
    case = replace(
        _CASES[0],
        segment=segment,
        surface=surface,
        input="흐름을 확인했다. " + "이후 발표와 수급 방향을 비교하며 " * 10,
    )
    context = _acceptance_context(missing=tuple(s for s in _SEGMENTS if s != segment))
    result = finalize_public_bundle(
        {segment: _finalizer_briefing(case, tldr_position=position)}, context=context
    )
    document = result.documents[0]
    block = document.briefing.rendered_markdown.split("## 한눈에 보기\n", 1)[1]
    values = [
        line.removeprefix("- ").strip()
        for line in block.split("\n## ", 1)[0].strip().splitlines()
        if line.strip() and not line.startswith(">")
    ]
    assert values[position] == "흐름을 확인했다. 본문 참고."
    assert len(values) == 3
    assert all(len(value) <= SNIPPET_MAX_CHARS for value in values)
    _assert_sealed_summary(document)


@pytest.mark.parametrize("surface", ("conclusion", "driver", "tldr_bullet", "tldr_plain"))
@pytest.mark.parametrize(
    "value",
    ("", "후속 수급 설명 " * 20, "후속 수급 설명 " * 20 + "확인했다."),
    ids=("empty", "no-boundary", "overlong-first"),
)
def test_finalized_fallbacks_and_unrelated_regions(surface: str, value: str) -> None:
    case = replace(_CASES[0], segment=CRYPTO, surface=surface, input=value)
    expected = {
        "conclusion": FALLBACK_BY_PREFIX[CONCLUSION_PREFIX],
        "driver": FALLBACK_BY_PREFIX[DRIVER_PREFIX],
        "tldr_bullet": "요약은 본문을 참고하세요.",
        "tldr_plain": "요약은 본문을 참고하세요.",
    }[surface]
    context = _acceptance_context(missing=(DOMESTIC_EQUITY, US_EQUITY))
    document = finalize_public_bundle(
        {CRYPTO: _finalizer_briefing(case)}, context=context
    ).documents[0]
    if surface == "tldr_plain" and not value:
        # An empty unbulleted line is a separator, not an owned item. Cardinality
        # repair belongs to u154; u153 must not manufacture a new summary here.
        assert (
            _target_value(document.briefing.rendered_markdown, surface) == "지표 흐름을 확인했다."
        )
        assert expected not in document.briefing.rendered_markdown
        _assert_sealed_summary(document)
        return
    control = finalize_public_bundle(
        {CRYPTO: _finalizer_briefing(replace(case, input=expected))}, context=context
    ).documents[0]

    assert _target_value(document.briefing.rendered_markdown, surface) == expected
    assert document.briefing.rendered_markdown == control.briefing.rendered_markdown
    assert document.markdown_sha256 == control.markdown_sha256
    _assert_sealed_summary(document)


@pytest.mark.parametrize("missing", ((), (DOMESTIC_EQUITY,), (US_EQUITY, CRYPTO)))
def test_finalized_complete_and_partial_bundle_repeatability(
    missing: tuple[MarketSegment, ...],
) -> None:
    active = tuple(segment for segment in _SEGMENTS if segment not in missing)
    originals = {
        segment: _finalizer_briefing(
            replace(_CASES[0], segment=segment, input="흐름을 확인했다. " + "후속 설명 " * 30)
        )
        for segment in active
    }
    context = _acceptance_context(missing=missing)
    result = finalize_public_bundle(originals, context=context)
    repeated = finalize_public_bundle(
        {document.segment: document.briefing for document in result.documents}, context=context
    )

    assert tuple(document.segment for document in result.documents) == active
    assert [(outcome.segment, outcome.state) for outcome in result.segment_outcomes] == [
        (segment, "generation_absent" if segment in missing else "finalized")
        for segment in _SEGMENTS
    ]
    for document, again in zip(result.documents, repeated.documents, strict=True):
        _assert_sealed_summary(document)
        assert document.briefing.rendered_markdown == again.briefing.rendered_markdown
        assert document.markdown_sha256 == again.markdown_sha256
        assert document.notification_summary == again.notification_summary
        assert _target_value(document.briefing.rendered_markdown, "conclusion") == (
            "흐름을 확인했다. 본문 참고."
        )


@pytest.mark.parametrize("surface", ("conclusion", "driver", "tldr_bullet", "tldr_plain"))
@pytest.mark.parametrize(
    "defect,code",
    (
        ("[근거](https://example.invalid/a...)", "markdown.href_ellipsis"),
        ("[미완성 근거", "markdown.unmatched_link"),
    ),
)
def test_finalized_original_link_policy_keeps_good_siblings(
    surface: str, defect: str, code: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = "흐름을 확인했다. " + "후속 설명 " * 30 + defect
    case = replace(_CASES[0], surface=surface, input=value)
    bad = _finalizer_briefing(case)
    good = _finalizer_briefing(replace(case, surface="conclusion", input="흐름을 확인했다."))
    context = _acceptance_context(missing=(DOMESTIC_EQUITY,))
    observed: list[str] = []

    def observe_repair(markdown: str) -> str:
        if any(issue.code == code for issue in find_surface_quality_issues(markdown)):
            observed.append(markdown)
        return repair_surface_artifacts(markdown)

    monkeypatch.setattr(segment_reader_module, "repair_surface_artifacts", observe_repair)

    result = finalize_public_bundle({US_EQUITY: bad, CRYPTO: good}, context=context)

    # Raw link evidence survives reflow and cosmetic repair. Integrated u150
    # repairs recoverable targets, then applies the shared u153 bound; residual
    # unmatched syntax uses u150's canonical owned-region replacement instead.
    assert observed
    assert tuple(document.segment for document in result.documents) == (US_EQUITY, CRYPTO)
    assert result.segment_outcomes[1].state == "finalized"
    assert defect not in result.documents[0].briefing.rendered_markdown
    outcome = next(
        outcome for outcome in result.documents[0].block_outcomes if code in outcome.issue_codes
    )
    if code == "markdown.href_ellipsis":
        assert outcome.disposition == "repaired"
        assert _target_value(result.documents[0].briefing.rendered_markdown, surface) == (
            "흐름을 확인했다. 본문 참고."
        )
    else:
        assert outcome.disposition == "replaced"
        assert result.documents[0].notification_summary.conclusion == (
            "시장 흐름을 확인했다."
            if surface.startswith("tldr_")
            else "검증된 입력이 부족해 시장 방향 판단을 보류합니다."
        )
    for document in result.documents:
        _assert_sealed_summary(document)
    assert defect in bad.rendered_markdown


@pytest.mark.parametrize(
    "body,code",
    (
        ("input_hash=redacted", "trace.fragment"),
        ("### S&P 500 **+1.20%** 상승", "numeric.anchor_assertion"),
    ),
    ids=("trace", "numeric"),
)
def test_finalized_non_summary_hard_gates_survive_bounding(body: str, code: str) -> None:
    case = replace(_CASES[0], input="흐름을 확인했다. " + "후속 설명 " * 30)
    source = _finalizer_briefing(case)
    bad = source.model_copy(
        update={
            "rendered_markdown": source.rendered_markdown.replace("주요 자산을 확인했다.", body),
        }
    )
    context = _acceptance_context(missing=(DOMESTIC_EQUITY,))

    result = finalize_public_bundle({US_EQUITY: bad, CRYPTO: source}, context=context)

    assert tuple(document.segment for document in result.documents) == (CRYPTO,)
    assert result.segment_outcomes[1].state == "trust_blocked"
    assert code in result.segment_outcomes[1].issue_codes
    _assert_sealed_summary(result.documents[0])


@seed(15320260907)
@settings(max_examples=60, print_blob=True, deadline=None)
@given(
    value=st.decimals(
        min_value="0.01", max_value="99999.99", places=2, allow_nan=False, allow_infinity=False
    ),
    segment=st.sampled_from(_SEGMENTS),
    surface=st.sampled_from(("conclusion", "driver", "tldr_bullet", "tldr_plain")),
    style=st.sampled_from(("plain", "bold", "link")),
    repeats=st.integers(min_value=15, max_value=25),
)
def test_finalized_decimal_markdown_and_notification_property(
    value: Decimal, segment: MarketSegment, surface: str, style: str, repeats: int
) -> None:
    number = f"{value:,.2f}"
    if style == "bold":
        number = f"**{number}**"
    elif style == "link":
        number = f"[{number}](https://example.invalid/a)"
    first = f"지표는 {number} 수준으로 확인했다."
    case = replace(
        _CASES[0], segment=segment, surface=surface, input=first + " 후속 설명" * repeats
    )
    context = _acceptance_context(missing=tuple(s for s in _SEGMENTS if s != segment))

    document = finalize_public_bundle(
        {segment: _finalizer_briefing(case)}, context=context
    ).documents[0]
    actual = _target_value(document.briefing.rendered_markdown, surface)

    assert actual == first + " 본문 참고."
    assert len(actual) <= SNIPPET_MAX_CHARS
    assert actual.count("본문 참고.") == 1
    _assert_sealed_summary(document)
    repeated = finalize_public_bundle({segment: document.briefing}, context=context).documents[0]
    assert repeated.briefing.rendered_markdown == document.briefing.rendered_markdown
    assert repeated.markdown_sha256 == document.markdown_sha256
    assert repeated.notification_summary == document.notification_summary


@pytest.mark.parametrize("segment", _SEGMENTS)
@pytest.mark.parametrize("no_fitting_sentence", (False, True), ids=("bounded", "fallback"))
def test_finalized_notification_cleanup_expansion_keeps_markdown_bytes(
    segment: MarketSegment, no_fitting_sentence: bool
) -> None:
    if no_fitting_sentence:
        raw = "상황을 살피며 " * 8 + "price mi**ssing**"
        expected = FALLBACK_BY_PREFIX[CONCLUSION_PREFIX]
    else:
        raw = ("price mi**ssing** " + "상황을 살핍니다. " * 6).strip()
        expected = (
            "핵심 가격 근거가 확인되지 않아 정확한 가격 서술은 줄였습니다. "
            + "상황을 살핍니다. " * 4
            + "본문 참고."
        )
        assert len(raw) == 77
        assert len(clean_public_summary_text(raw)) == 95
    assert len(raw) <= SNIPPET_MAX_CHARS
    assert len(clean_public_summary_text(raw)) > SNIPPET_MAX_CHARS
    case = replace(_CASES[0], segment=segment, input=raw)
    context = _acceptance_context(missing=tuple(s for s in _SEGMENTS if s != segment))

    document = finalize_public_bundle(
        {segment: _finalizer_briefing(case)}, context=context
    ).documents[0]

    markdown = document.briefing.rendered_markdown
    assert _target_value(markdown, "conclusion") == raw
    assert document.notification_summary.conclusion == expected
    assert len(expected) <= SNIPPET_MAX_CHARS
    assert document.markdown_sha256 == sha256(markdown.encode("utf-8")).hexdigest()
    repeated = finalize_public_bundle({segment: document.briefing}, context=context).documents[0]
    assert repeated.briefing.rendered_markdown == markdown
    assert repeated.markdown_sha256 == document.markdown_sha256
    assert repeated.notification_summary == document.notification_summary


def test_finalized_unsafe_cleaned_summary_is_rejected_before_bounding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = "price mi**ssing** " + "상황을 살핍니다. " * 5 + "boundary-**term**."
    assert len(raw) == 86
    cleaned = clean_public_summary_text(raw)
    assert len(cleaned) > SNIPPET_MAX_CHARS
    assert is_unsafe_summary_value(cleaned)
    calls: list[str] = []

    def reject_bounding(value: str) -> str:
        calls.append(value)
        raise AssertionError("unsafe cleaned summary must fail before length repair")

    monkeypatch.setattr(public_document_module, "bound_summary_snippet", reject_bounding)
    bad = _finalizer_briefing(replace(_CASES[0], input=raw))
    good = _finalizer_briefing(replace(_CASES[0], input="흐름을 확인했다."))
    context = _acceptance_context(missing=(DOMESTIC_EQUITY,))

    result = finalize_public_bundle({US_EQUITY: bad, CRYPTO: good}, context=context)

    assert not calls
    assert tuple(document.segment for document in result.documents) == (CRYPTO,)
    assert result.segment_outcomes[1].state == "trust_blocked"
    assert result.segment_outcomes[1].issue_codes == ("summary.invalid_conclusion",)
    _assert_sealed_summary(result.documents[0])


@seed(15320260907)
@settings(max_examples=60, print_blob=True, deadline=None)
@given(
    fragment=st.sampled_from(
        (
            "price mi**ssing**",
            "price `mi`ssing",
            "price mi~~ss~~ing",
            "source **missing**",
            "데이터 **부족**",
        )
    ),
    sentence_count=st.integers(min_value=0, max_value=12),
    prelude_count=st.integers(min_value=0, max_value=8),
    segment=st.sampled_from(_SEGMENTS),
)
def test_finalized_notification_projection_cap_property(
    fragment: str, sentence_count: int, prelude_count: int, segment: MarketSegment
) -> None:
    raw = (
        "상황을 살피며 " * prelude_count + fragment + " 상황을 살핍니다." * sentence_count
    ).strip()
    case = replace(_CASES[0], segment=segment, input=raw)
    context = _acceptance_context(missing=tuple(s for s in _SEGMENTS if s != segment))
    document = finalize_public_bundle(
        {segment: _finalizer_briefing(case)}, context=context
    ).documents[0]
    markdown = document.briefing.rendered_markdown
    final_value = _target_value(markdown, "conclusion")
    cleaned = clean_public_summary_text(final_value)
    conclusion = document.notification_summary.conclusion

    assert len(final_value) <= SNIPPET_MAX_CHARS
    assert len(conclusion) <= SNIPPET_MAX_CHARS
    assert not is_unsafe_summary_value(conclusion)
    if len(cleaned) <= SNIPPET_MAX_CHARS:
        assert conclusion == cleaned
    elif conclusion != FALLBACK_BY_PREFIX[CONCLUSION_PREFIX]:
        assert conclusion.endswith(" 본문 참고.")
        kept = conclusion.removesuffix(" 본문 참고.")
        assert cleaned.startswith(kept)
        assert bound_at_sentence(kept, len(kept), require_complete=True) == kept
        assert conclusion.count("본문 참고.") == 1
    repeated = finalize_public_bundle({segment: document.briefing}, context=context).documents[0]
    assert repeated.briefing.rendered_markdown == markdown
    assert repeated.markdown_sha256 == document.markdown_sha256
    assert repeated.notification_summary == document.notification_summary
