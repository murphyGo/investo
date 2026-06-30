"""Tests for publish-time first-viewport summary quality validation."""

from __future__ import annotations

import pytest

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


def test_repair_first_viewport_summary_cleans_markdown_artifacts() -> None:
    markdown = _markdown(
        conclusion="[미국 증시(https://example.com)",
        driver="**입법 가속화 vs.",
        caution="1.",
    )

    repaired = repair_first_viewport_summary(markdown)

    validate_first_viewport_summary(repaired)
    assert "[미국 증시" not in repaired
    assert "**입법" not in repaired
    assert "> **주의할 점**: 관전 포인트는 데이터 회복 후 보강합니다." in repaired


def test_repair_first_viewport_summary_strips_heading_and_residue() -> None:
    markdown = _markdown(driver="### KOSPI 가격 흐름", caution="미국 증시 변동성 ROS")

    repaired = repair_first_viewport_summary(markdown)

    validate_first_viewport_summary(repaired)
    assert "###" not in repaired
    assert " ROS" not in repaired
