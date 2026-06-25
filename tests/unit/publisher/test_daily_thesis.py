"""u99 daily thesis publisher tests."""

from __future__ import annotations

import pytest

from investo.models.bundle_context import DailyThesisDecision
from investo.publisher.daily_thesis import (
    DAILY_THESIS_FALLBACK_LINE,
    DAILY_THESIS_MARKER,
    assert_distinct_daily_thesis_lines,
    inject_daily_thesis_line,
    render_daily_thesis_line,
)
from investo.publisher.errors import DailyThesisConsistencyError


def _decision(line: str, mode: str = "strong") -> DailyThesisDecision:
    return DailyThesisDecision(
        mode=mode,  # type: ignore[arg-type]
        line=line,
        reason="test",
        macro_keys=("ust_yield",),
        supporting_segments=("domestic-equity", "us-equity"),
    )


def test_render_rejects_digits() -> None:
    decision = _decision(f"{DAILY_THESIS_MARKER} 금리 10년물이 공통 변수입니다.")

    assert render_daily_thesis_line(decision) == ""


def test_injects_before_section_one() -> None:
    decision = _decision(
        f"{DAILY_THESIS_MARKER} 금리와 달러 변수가 국내·미국에 동시에 걸리며, "
        "오늘 독자는 금리·달러 민감도를 먼저 확인해야 합니다."
    )
    text = "# title\n\n## 한눈에 보기\n\n- a\n\n## ① 요약\n\n본문"

    out = inject_daily_thesis_line(text, decision)

    assert out.index(DAILY_THESIS_MARKER) < out.index("## ① 요약")
    assert out.count(DAILY_THESIS_MARKER) == 1


def test_segment_specific_line_takes_precedence() -> None:
    decision = DailyThesisDecision(
        mode="strong",
        line=f"{DAILY_THESIS_MARKER} 금리와 달러 변수가 공통 변수입니다.",
        per_segment_lines={
            "domestic-equity": (
                f"{DAILY_THESIS_MARKER} 금리와 달러 변수가 공통 변수지만, "
                "KOSPI·원/달러·외국인 수급을 먼저 확인해야 합니다."
            ),
            "us-equity": (
                f"{DAILY_THESIS_MARKER} 금리와 달러 변수가 공통 변수지만, "
                "Nasdaq·Dow 섹터 변동성을 먼저 확인해야 합니다."
            ),
        },
        reason="test",
    )

    assert "KOSPI" in render_daily_thesis_line(decision, segment="domestic-equity")
    assert "Nasdaq" in render_daily_thesis_line(decision, segment="us-equity")


def test_injection_is_idempotent_and_replaces_existing_marker() -> None:
    decision = _decision(
        f"{DAILY_THESIS_MARKER} 금리와 달러 변수가 국내·미국에 동시에 걸리며, "
        "오늘 독자는 금리·달러 민감도를 먼저 확인해야 합니다."
    )
    text = f"# title\n\n{DAILY_THESIS_MARKER} 임의 작성 문장입니다.\n\n## ① 요약\n본문"

    once = inject_daily_thesis_line(text, decision)
    twice = inject_daily_thesis_line(once, decision)

    assert once == twice
    assert "임의 작성" not in once
    assert once.count(DAILY_THESIS_MARKER) == 1


def test_omit_removes_existing_marker() -> None:
    text = f"{DAILY_THESIS_MARKER} 임의 작성 문장입니다.\n\n## ① 요약\n본문"

    out = inject_daily_thesis_line(
        text,
        DailyThesisDecision(mode="omit", reason="insufficient_successful_segments"),
    )

    assert DAILY_THESIS_MARKER not in out
    assert out.startswith("## ① 요약")


def test_distinct_guard_blocks_three_identical_public_lines() -> None:
    repeated = (
        f"{DAILY_THESIS_MARKER} 금리와 달러 변수가 공통 변수지만, "
        "KOSPI 수급을 먼저 확인해야 합니다."
    )

    with pytest.raises(DailyThesisConsistencyError) as exc_info:
        assert_distinct_daily_thesis_lines(
            {
                "domestic-equity": repeated,
                "us-equity": repeated,
                "crypto": repeated,
            }
        )
    assert exc_info.value.segments == ("domestic-equity", "us-equity", "crypto")


def test_distinct_guard_allows_bounded_fallback_repetition() -> None:
    assert_distinct_daily_thesis_lines(
        {
            "domestic-equity": DAILY_THESIS_FALLBACK_LINE,
            "us-equity": DAILY_THESIS_FALLBACK_LINE,
            "crypto": DAILY_THESIS_FALLBACK_LINE,
        }
    )
