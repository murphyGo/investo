"""Tests for publish-time first-viewport summary quality validation."""

from __future__ import annotations

import pytest

from investo.briefing.summary_quality import (
    SummaryQualityError,
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


def test_validate_first_viewport_summary_rejects_missing_required_line() -> None:
    markdown = _markdown().replace("> **핵심 동인**: 입법 가속화 vs. 정치적 마찰\n", "")

    with pytest.raises(SummaryQualityError, match="missing"):
        validate_first_viewport_summary(markdown)
