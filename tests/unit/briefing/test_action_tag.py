"""Tests for u30 Step 3 — closed-set action tag contract."""

from __future__ import annotations

import pytest

from investo.briefing.action_tag import (
    ACTION_TAGS,
    DATA_LIMITED_ACTION_TAG,
    DEFAULT_ACTION_TAG,
    apply_action_tag,
)


def test_default_tag_is_kanmang() -> None:
    assert DEFAULT_ACTION_TAG == "[관망]"


def test_data_limited_tag_is_separate_constant() -> None:
    assert DATA_LIMITED_ACTION_TAG == "[데이터부족]"


def test_closed_set_size() -> None:
    """The closed set is six tags. Adding a tag is a contract change."""
    assert len(ACTION_TAGS) == 6
    assert (
        frozenset({"[관망]", "[변동성↑]", "[강세]", "[약세]", "[혼조]", "[데이터부족]"})
        == ACTION_TAGS
    )


def test_appends_default_when_no_tag_present() -> None:
    assert apply_action_tag("오늘 시장은 안정적이었습니다.", data_limited=False) == (
        "오늘 시장은 안정적이었습니다. [관망]"
    )


@pytest.mark.parametrize(
    "tag",
    ["[관망]", "[변동성↑]", "[강세]", "[약세]", "[혼조]"],
)
def test_preserves_in_set_tag(tag: str) -> None:
    assert apply_action_tag(f"오늘 시장은 안정적이었습니다. {tag}", data_limited=False) == (
        f"오늘 시장은 안정적이었습니다. {tag}"
    )


def test_normalizes_extra_whitespace_before_in_set_tag() -> None:
    """Multiple spaces before the tag collapse to one."""
    assert apply_action_tag("결론입니다.   [강세]", data_limited=False) == ("결론입니다. [강세]")


def test_strips_off_set_english_tag_and_replaces_with_default() -> None:
    assert apply_action_tag("Bullish day. [BUY]", data_limited=False) == ("Bullish day. [관망]")


def test_strips_off_set_korean_tag_and_replaces_with_default() -> None:
    assert apply_action_tag("결론입니다. [강력매수]", data_limited=False) == ("결론입니다. [관망]")


def test_data_limited_overrides_in_set_tag() -> None:
    """When data is limited the tag is forced regardless of LLM output."""
    assert apply_action_tag("오늘은 데이터가 부족합니다. [강세]", data_limited=True) == (
        "오늘은 데이터가 부족합니다. [데이터부족]"
    )


def test_data_limited_appends_when_no_tag_present() -> None:
    assert apply_action_tag("데이터 부족 안내문입니다.", data_limited=True) == (
        "데이터 부족 안내문입니다. [데이터부족]"
    )


def test_inline_bracket_tokens_are_preserved() -> None:
    """Mid-sentence bracket tokens (tickers, references) are NOT touched.

    Only the trailing token gets inspected. ``[NVDA]`` mid-sentence
    survives intact, and the deterministic default is appended.
    """
    assert apply_action_tag("NVDA [NVDA] 실적이 발표됐습니다.", data_limited=False) == (
        "NVDA [NVDA] 실적이 발표됐습니다. [관망]"
    )


def test_idempotent_reapply() -> None:
    """Calling apply_action_tag twice on the same input is a fixed point."""
    once = apply_action_tag("오늘 시장은 안정적이었습니다.", data_limited=False)
    twice = apply_action_tag(once, data_limited=False)
    assert once == twice


def test_idempotent_under_data_limited() -> None:
    once = apply_action_tag("자료 한계 안내.", data_limited=True)
    twice = apply_action_tag(once, data_limited=True)
    assert once == twice


def test_empty_conclusion_returns_default_alone() -> None:
    """Empty input becomes just the default tag — never an empty string."""
    assert apply_action_tag("", data_limited=False) == "[관망]"
    assert apply_action_tag("   ", data_limited=False) == "[관망]"


def test_empty_conclusion_under_data_limited_returns_data_limited_alone() -> None:
    assert apply_action_tag("", data_limited=True) == "[데이터부족]"
