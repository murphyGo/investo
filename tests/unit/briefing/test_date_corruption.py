"""u55 Step 3 — Tests for the date-corruption regex gate."""

from __future__ import annotations

from investo.briefing.date_corruption import find_corrupt_date_tokens


def test_no_corruption_in_clean_text() -> None:
    assert find_corrupt_date_tokens("정상적인 본문, 5월 11일 마감.") == ()


def test_valid_us_date_5_11_passes() -> None:
    assert find_corrupt_date_tokens("Friday 5/11 close") == ()


def test_valid_three_segment_date_passes() -> None:
    assert find_corrupt_date_tokens("On 05/11/26 the market closed") == ()


def test_corrupt_day_65_blocks() -> None:
    result = find_corrupt_date_tokens("토큰 corrupt 5/65/7 발생")
    assert len(result) == 1
    assert result[0].reason == "day_out_of_range"
    assert result[0].raw == "5/65/7"


def test_corrupt_month_13_blocks() -> None:
    result = find_corrupt_date_tokens("Bad: 13/5 marker")
    assert len(result) == 1
    assert result[0].reason == "month_out_of_range"


def test_corrupt_day_32_blocks() -> None:
    result = find_corrupt_date_tokens("ex 1/32")
    assert len(result) == 1
    assert result[0].reason == "day_out_of_range"


def test_all_zero_blocks() -> None:
    result = find_corrupt_date_tokens("placeholder 0/0/0")
    assert len(result) == 1
    assert result[0].reason == "all_zero"


def test_korean_month_day_phrase_not_flagged() -> None:
    # "5월 11일" is Korean wording — no slashes, must not match.
    assert find_corrupt_date_tokens("5월 11일은 휴장일") == ()


def test_code_block_corruption_ignored() -> None:
    text = "정상 본문\n```\ncron schedule example: 0 7 * 1/65 1-5\n```\n끝"
    assert find_corrupt_date_tokens(text) == ()


def test_multiple_corruptions_returned_in_order() -> None:
    text = "first 99/99 then 5/65 last"
    result = find_corrupt_date_tokens(text)
    assert len(result) == 2
    assert result[0].position < result[1].position


def test_duplicate_segment_5_5_5_is_valid() -> None:
    # Could be May 5, '05 — not flagged per docstring rule.
    assert find_corrupt_date_tokens("on 5/5/5") == ()


def test_year_in_three_segment_not_flagged_when_all_valid() -> None:
    # 12/31/26 → all in range → valid.
    assert find_corrupt_date_tokens("close 12/31/26") == ()
