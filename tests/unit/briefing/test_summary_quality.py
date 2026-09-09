"""Tests for publish-time first-viewport summary quality validation."""

from __future__ import annotations

import pytest
from hypothesis import given, seed, settings
from hypothesis import strategies as st

from investo._internal.briefing_extract import CONCLUSION_PREFIX, DRIVER_PREFIX, FALLBACK_BY_PREFIX
from investo._internal.surface_quality import find_surface_quality_issues
from investo.briefing._assembly.summary_extraction import _build_summary_header, _summary_sentence
from investo.briefing.summary_quality import (
    SummaryQualityError,
    is_unsafe_summary_value,
    repair_first_viewport_summary,
    validate_first_viewport_summary,
)


def _markdown(
    *,
    conclusion: str = "미국 증시는 실적 일정을 앞두고 방향성 확인이 필요합니다.",
    driver: str = "입법 가속화 vs. 정치적 마찰",
    caution: str = "ARM 가이던스",
) -> str:
    return (
        "# 2026-05-07 미국 증시 시황\n\n"
        f"> **오늘의 결론**: {conclusion}\n"
        f"> **핵심 동인**: {driver}\n"
        f"> **주의할 점**: {caution}\n\n"
        "## ① 요약\n본문\n"
    )


def test_validate_first_viewport_summary_accepts_clean_summary_lines() -> None:
    validate_first_viewport_summary(_markdown())
    assert not is_unsafe_summary_value("미국 증시는 실적 일정을 앞두고 방향성 확인이 필요합니다.")


@pytest.mark.parametrize(
    "value",
    [
        "",
        "1.",
        "-",
        "정책과.",
        "**입법 가속화",
        "[미국 증시",
        "### KOSPI 가격 흐름",
        "금리 **-**0.10%**p** 변동",
        "미국 증시 변동성 ROS",
        (
            "비트코인 가격은 정책 이벤트와 ETF 자금 흐름 사이에서 방향성을 탐색하고 "
            "있으며 단기 수급은 아직 확인되지 않은 기관"
        ),
        "policy and.",
    ],
)
def test_is_unsafe_summary_value_matches_publish_gate_rejects(value: str) -> None:
    assert is_unsafe_summary_value(value)

    with pytest.raises(SummaryQualityError):
        validate_first_viewport_summary(_markdown(caution=value))


@pytest.mark.parametrize("caution", ["1.", "-", "*", ""])
def test_validate_first_viewport_summary_rejects_empty_or_list_marker_only(
    caution: str,
) -> None:
    with pytest.raises(SummaryQualityError):
        validate_first_viewport_summary(_markdown(caution=caution))


def test_validate_first_viewport_summary_rejects_unbalanced_bold_marker() -> None:
    with pytest.raises(SummaryQualityError, match="unbalanced bold"):
        validate_first_viewport_summary(_markdown(driver="**입법 가속화 vs."))


def test_validate_first_viewport_summary_rejects_unbalanced_markdown_link() -> None:
    with pytest.raises(SummaryQualityError, match="unbalanced markdown link"):
        validate_first_viewport_summary(_markdown(conclusion="[미국 증시(https://example.com)"))


def test_validate_first_viewport_summary_rejects_heading_residue() -> None:
    with pytest.raises(SummaryQualityError, match="heading residue"):
        validate_first_viewport_summary(_markdown(driver="### KOSPI 가격 흐름"))


def test_validate_first_viewport_summary_rejects_generator_residue_tail() -> None:
    with pytest.raises(SummaryQualityError, match="generator residue"):
        validate_first_viewport_summary(_markdown(caution="미국 증시 변동성 ROS"))


def test_validate_first_viewport_summary_rejects_broken_numeric_bold() -> None:
    with pytest.raises(SummaryQualityError, match="broken numeric emphasis"):
        validate_first_viewport_summary(_markdown(driver="금리 **-**0.10%**p** 변동"))


def test_validate_first_viewport_summary_rejects_long_dangling_tail() -> None:
    with pytest.raises(SummaryQualityError, match="dangling truncation"):
        validate_first_viewport_summary(
            _markdown(
                caution=(
                    "비트코인 가격은 정책 이벤트와 ETF 자금 흐름 사이에서 방향성을 탐색하고 "
                    "있으며 단기 수급은 아직 확인되지 않은 기관"
                )
            )
        )


def test_validate_first_viewport_summary_rejects_missing_required_line() -> None:
    markdown = _markdown().replace("> **핵심 동인**: 입법 가속화 vs. 정치적 마찰\n", "")

    with pytest.raises(SummaryQualityError, match="missing"):
        validate_first_viewport_summary(markdown)


def test_repair_first_viewport_summary_preserves_link_artifacts_for_u150_gate() -> None:
    markdown = _markdown(
        conclusion="[미국 증시(https://example.com)",
        driver="**입법 가속화 vs.",
        caution="1.",
    )

    repaired = repair_first_viewport_summary(markdown)

    with pytest.raises(SummaryQualityError, match="unbalanced markdown link"):
        validate_first_viewport_summary(repaired)
    assert "[미국 증시(https://example.com)" in repaired
    assert "**입법" not in repaired
    assert "> **주의할 점**: 관전 포인트는 데이터 회복 후 보강합니다." in repaired


def test_repair_first_viewport_summary_strips_heading_and_residue() -> None:
    markdown = _markdown(driver="### KOSPI 가격 흐름", caution="미국 증시 변동성 ROS")

    repaired = repair_first_viewport_summary(markdown)

    validate_first_viewport_summary(repaired)
    assert "###" not in repaired
    assert " ROS" not in repaired


@pytest.mark.parametrize("ending", ("...", "…", "("))
def test_u153_structural_summary_truncation_uses_owner_fallback(ending: str) -> None:
    markdown = _markdown(conclusion=f"확인이 더 필요{ending}")

    repaired = repair_first_viewport_summary(markdown)

    assert f"{CONCLUSION_PREFIX} {FALLBACK_BY_PREFIX[CONCLUSION_PREFIX]}" in repaired
    assert ending not in repaired
    validate_first_viewport_summary(repaired)


@pytest.mark.parametrize(
    "value",
    [
        "매수세가 본문 참고.",
        "기관의 본문 참고.",
        "이번 문서는 본문 참고.",
        "반등하며 본문 참고.",
        "상승...본문 참고.",
        "상승… 본문 참고.",
        "본문 참고.",
        "상승했습니다. 본문 참고. 본문 참고.",
        "지수는 3.14. 본문 참고.",
        "지수는 상승했습니다. " * 120 + "기관의 본문 참고.",
        "| 기관의 본문 참고.",
    ],
)
@pytest.mark.parametrize("surface", ["conclusion", "driver"])
def test_u153_canonical_gate_rejects_and_repairs_continuation(value: str, surface: str) -> None:
    markdown = _markdown(**{surface: value})
    assert is_unsafe_summary_value(value)
    with pytest.raises(SummaryQualityError, match="surface-quality"):
        validate_first_viewport_summary(markdown)
    repaired = repair_first_viewport_summary(markdown)
    prefix = CONCLUSION_PREFIX if surface == "conclusion" else DRIVER_PREFIX
    assert f"{prefix} {FALLBACK_BY_PREFIX[prefix]}" in repaired
    assert repair_first_viewport_summary(repaired) == repaired
    validate_first_viewport_summary(repaired)


@pytest.mark.parametrize(
    "value", ["기관의 본문 참고.", "상승했습니다. 본문 참고. 본문 참고.", "지수는 3.14. 본문 참고."]
)
def test_u153_typed_caution_gate_and_repair_remain_unchanged(value: str) -> None:
    markdown = _markdown(caution=value)
    validate_first_viewport_summary(markdown)
    assert repair_first_viewport_summary(markdown) == markdown


@pytest.mark.parametrize("value", ["본문 참고.", "기관의 본문 참고.", "지수는 3.14. 본문 참고."])
def test_u153_caution_extraction_retains_legacy_predicate(value: str) -> None:
    sections = ("지수는 상승했습니다.", "금리 변화입니다.", "", "", "", value)
    assert _build_summary_header(sections).caution == value
    assert _summary_sentence(value, fallback="fallback") == "fallback"
    assert not is_unsafe_summary_value(value, check_continuation=False)


@pytest.mark.parametrize("value", ["1.", "정책과.", "**입법 가속화", "[미국 증시"])
def test_u153_caution_opt_out_does_not_disable_other_summary_safety(value: str) -> None:
    assert is_unsafe_summary_value(value, check_continuation=False)


@pytest.mark.parametrize(
    "value, code",
    [
        ("| [링크](https://example.com/...) 기관의 본문 참고.", "markdown.href_ellipsis"),
        ("[링크](https://example.com/...) 기관의 본문 참고.", "markdown.href_ellipsis"),
        ("| [깨진 링크 기관의 본문 참고.", "markdown.unmatched_link"),
        ("| input_hash=redacted 기관의 본문 참고.", "trace.fragment"),
        ("[ref]: https://example.com/... 기관의 본문 참고.", "markdown.href_ellipsis"),
        (
            "가" * 1650 + " [링크](https://example.com/...) 기관의 본문 참고.",
            "markdown.href_ellipsis",
        ),
    ],
)
@pytest.mark.parametrize("surface", ["conclusion", "driver"])
def test_u153_continuation_fallback_does_not_erase_other_blockers(
    value: str, code: str, surface: str
) -> None:
    markdown = _markdown(**{surface: value})
    assert repair_first_viewport_summary(markdown) == markdown
    with pytest.raises(SummaryQualityError):
        validate_first_viewport_summary(markdown)
    # Keep anchored reference syntax and callout context for their existing
    # scanner owner, just as the formatter does; no new issue/disposition.
    codes = {
        issue.code
        for context in (markdown, f"{value}\n## ①")
        for issue in find_surface_quality_issues(context)
    }
    assert code in codes


@seed(15320260907)
@settings(max_examples=80, print_blob=True)
@given(
    number=st.decimals(
        min_value="0.01", max_value="999.99", places=2, allow_nan=False, allow_infinity=False
    ),
    shape=st.sampled_from(("plain", "bold", "link")),
    fragment=st.sampled_from(("매수세가", "기관의", "이번 문서는", "반등하며")),
)
def test_u153_canonical_continuation_property(number: object, shape: str, fragment: str) -> None:
    subject = {"plain": "지수", "bold": "**지수**", "link": "[지수](https://example.com/a)"}[shape]
    sentence = f"{subject}는 {number}% 상승했습니다."
    safe = f"{sentence} 본문 참고."
    assert not is_unsafe_summary_value(safe)
    assert repair_first_viewport_summary(_markdown(conclusion=safe)) == _markdown(conclusion=safe)
    unsafe = f"{sentence} {fragment} 본문 참고."
    assert is_unsafe_summary_value(unsafe)
    repaired = repair_first_viewport_summary(_markdown(driver=unsafe))
    validate_first_viewport_summary(repaired)
    assert repaired == repair_first_viewport_summary(repaired)
