"""Tests for u32 Step 2 — Stage 3 numeric self-check."""

from __future__ import annotations

from datetime import UTC, datetime

from investo.briefing.numeric_self_check import (
    extract_flaggable_numbers,
    find_unverified,
    render_warning_line,
)
from investo.models import NormalizedItem


def _item(
    *, title: str, summary: str | None = None, raw_metadata: dict | None = None
) -> NormalizedItem:  # type: ignore[type-arg]
    return NormalizedItem(
        source_name="test-source",
        category="news",
        title=title,
        summary=summary,
        published_at=datetime(2026, 5, 9, tzinfo=UTC),
        raw_metadata=raw_metadata or {},
    )


def test_extract_picks_decimal_and_pct_tokens() -> None:
    text = "S&P 500 closed at 5,200.42, up 0.42%."
    flagged = extract_flaggable_numbers(text)
    # 5,200.42 (thousands separator) + 0.42% (decimal + unit) flagged.
    assert "5,200.42" in flagged
    assert "0.42%" in flagged


def test_extract_skips_short_bare_integers() -> None:
    """Years and short counts shouldn't trigger flagging on their own."""
    text = "2026년 5월 9일 시장은 5건의 이벤트로 분주했다."
    flagged = extract_flaggable_numbers(text)
    # 2026 is exactly 4 digits → flaggable as a numeric figure (year).
    # We accept some noise here; the comparison step is what filters.
    assert "9" not in flagged  # 1-digit, no unit, no separator → ignored


def test_extract_picks_korean_units() -> None:
    text = "시총 합산 약 1.7조원으로 추정"
    flagged = extract_flaggable_numbers(text)
    assert "1.7조" in flagged or "1.7원" in flagged or any("1.7" in t for t in flagged)


def test_find_unverified_returns_empty_when_all_numbers_appear() -> None:
    text = "S&P 500 closed at 5,200.42, up 0.42%."
    candidates = [
        _item(
            title="^GSPC closing data",
            raw_metadata={"close": "5200.420000", "pct_change": "0.420000"},
        ),
    ]
    assert find_unverified(text, candidates) == ()


def test_find_unverified_flags_invented_numbers() -> None:
    """LLM hallucinates ``평균 수익률 약 12%`` not in any input."""
    text = "오늘 평균 수익률 약 12% 상승."
    candidates = [
        _item(
            title="^GSPC moved",
            raw_metadata={"close": "5200.0", "pct_change": "0.42"},
        ),
    ]
    flagged = find_unverified(text, candidates)
    assert "12%" in flagged


def test_find_unverified_recognises_thousands_separator_match() -> None:
    """``5,200`` in Stage 2 output matches ``5200`` raw in metadata."""
    text = "지수는 5,200으로 마감."
    candidates = [_item(title="x", raw_metadata={"close": "5200"})]
    assert find_unverified(text, candidates) == ()


def test_find_unverified_returns_all_when_candidate_haystack_empty() -> None:
    """Defensive: no candidates → every flagged token is unverified."""
    text = "지수 5,200.42 상승 0.42%."
    flagged = find_unverified(text, [])
    assert "5,200.42" in flagged
    assert "0.42%" in flagged


def test_render_warning_line_renders_with_cap_and_suffix() -> None:
    out = render_warning_line(("1.1%", "2.2%", "3.3%", "4.4%", "5.5%", "6.6%", "7.7%"))
    assert "수치 검증 경고" in out
    # First five tokens appear; trailing 6th/7th collapsed under " 외".
    assert "1.1%, 2.2%, 3.3%, 4.4%, 5.5%" in out
    assert "외" in out
    assert "6.6%" not in out


def test_render_warning_line_returns_empty_for_empty_input() -> None:
    assert render_warning_line(()) == ""
