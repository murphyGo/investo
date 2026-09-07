"""u79 — UTF-16 text primitives (moved from ``notifier/summary.py``).

Pins code-unit counting and surrogate-pair-safe truncation for BMP and
non-BMP (emoji) strings, plus the ``truncate_with_suffix`` ellipsis
idiom the notifier relies on. These supplement — they do not replace —
the unchanged ``tests/unit/notifier/test_summary.py`` assertions that
still import the same helpers via the notifier alias.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, seed, settings
from hypothesis import strategies as st

from investo._internal.text import (
    UTF16_TRUNCATION_SUFFIX,
    bound_at_sentence,
    truncate_with_suffix,
    utf16_truncate,
    utf16_units,
)


def test_bound_at_sentence_passthrough_below_and_at_cap() -> None:
    text = "코스피 변동성을 확인했다."

    assert bound_at_sentence(text, len(text) + 1) == text
    assert bound_at_sentence(text, len(text)) == text


def test_bound_at_sentence_uses_last_complete_sentence_within_cap() -> None:
    first = "첫 문장을 확인했다."
    second = " 두 번째 문장도 확인했다!"
    remainder = " 아직 끝나지 않은 세 번째 문장"
    text = first + second + remainder

    assert bound_at_sentence(text, len(first + second)) == first + second


def test_bound_at_sentence_supports_pinned_terminators() -> None:
    for terminator in (".", "!", "?", "。"):
        sentence = f"완료된 문장{terminator}"
        text = sentence + " 뒤 문장은 한도를 넘는다"

        assert bound_at_sentence(text, len(sentence)) == sentence


def test_bound_at_sentence_does_not_split_decimal_value() -> None:
    text = "비트코인은 7,499.36 수준에서 방향성을 탐색했다."
    decimal_cap = text.index("36") + 2

    assert bound_at_sentence(text, decimal_cap) is None


def test_bound_at_sentence_rejects_digit_preceded_period_before_space() -> None:
    text = "지수는 7,499.36. 후속 설명"
    number_suffix_period = text.index(". 후속") + 1

    assert bound_at_sentence(text, number_suffix_period) is None


def test_bound_at_sentence_returns_none_without_terminator() -> None:
    assert bound_at_sentence("완결 경계 없이 이어지는 문장", 10) is None


@pytest.mark.parametrize(
    "text",
    (
        "",
        " \t\n",
        "금리 안정과 수급 회복",
        "기관의 본문 참고.",
        "가격은 **7,499.36** 수준",
        "[근거](https://example.invalid/market)",
        "  시장 흐름을 확인했다.\n\n",
    ),
)
def test_bound_at_sentence_default_keeps_all_fitting_bytes(text: str) -> None:
    for cap in (len(text), len(text) + 1):
        assert bound_at_sentence(text, cap) == text
        assert bound_at_sentence(text, cap, require_complete=False) == text


@pytest.mark.parametrize(
    ("text", "cap", "expected"),
    (
        ("", 90, None),
        (" \t\n", 90, None),
        (".", 90, None),
        ("기관의", 90, None),
        ("확인했다. 아직 미완성", 90, "확인했다."),
        ("확인했다. 이어졌다! 아직 미완성", 90, "확인했다. 이어졌다!"),
        ("확인했다. 이어졌다!", 6, "확인했다."),
        ("확인했다.", 5, "확인했다."),
        ("확인했다.", 4, None),
        ("확인했다.", 0, None),
        ("확인했다.", -1, None),
        ("  확인했다.\n\t", 90, "  확인했다."),
        ("가격은 7,499.36", 90, None),
        ("가격은 7,499.36. 후속 설명", 90, None),
        ("가격은 **7,499.36**로 확인했다. 후속 설명", 90, "가격은 **7,499.36**로 확인했다."),
        (
            "[근거](https://example.invalid/market)를 확인했다. 후속 설명",
            90,
            "[근거](https://example.invalid/market)를 확인했다.",
        ),
    ),
)
def test_bound_at_sentence_requires_boundary_even_when_text_fits(
    text: str, cap: int, expected: str | None
) -> None:
    assert bound_at_sentence(text, cap, require_complete=True) == expected


@pytest.mark.parametrize("terminator", (".", "!", "?", "。"))
def test_bound_at_sentence_complete_mode_uses_existing_terminators(terminator: str) -> None:
    sentence = f"시장을 확인했다{terminator}"

    assert bound_at_sentence(sentence, len(sentence), require_complete=True) == sentence


@st.composite
def _market_sentences(draw: st.DrawFn) -> str:
    """Generate complete market-like prose with decimal and Markdown boundaries."""
    value: Decimal = draw(
        st.decimals(
            min_value="0.01",
            max_value="99999.99",
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    price = f"{value:,.2f}"
    style = draw(st.sampled_from(("plain", "bold", "link")))
    if style == "bold":
        price = f"**{price}**"
    elif style == "link":
        price = f"[{price}](https://example.invalid/market)"
    terminator = draw(st.sampled_from((".", "!", "?", "。")))
    return f"관측값 {price} 수준을 확인했다{terminator}"


@seed(15320260907)
@settings(max_examples=100, print_blob=True)
@given(
    sentences=st.lists(_market_sentences(), min_size=1, max_size=4),
    cap=st.integers(min_value=-1, max_value=300),
)
def test_bound_at_sentence_complete_mode_boundary_and_cap_property(
    sentences: list[str], cap: int
) -> None:
    # An independent oracle uses the generated sentence boundaries, not the regex.
    prefixes = [" ".join(sentences[:end]) for end in range(1, len(sentences) + 1)]
    text = prefixes[-1] + " 이후의 수급 방향은"
    fitting = [prefix for prefix in prefixes if len(prefix) <= cap]
    expected = fitting[-1] if fitting else None

    result = bound_at_sentence(text, cap, require_complete=True)

    assert result == expected
    if result is not None:
        assert len(result) <= cap
        assert text.startswith(result)
        assert bound_at_sentence(result, cap, require_complete=True) == result
    # Overflow scanning must remain the same in both modes.
    legacy_expected = text if len(text) <= cap else expected
    assert bound_at_sentence(text, cap) == legacy_expected
    assert bound_at_sentence(text, cap, require_complete=False) == legacy_expected


@seed(15320260907)
@settings(max_examples=60, print_blob=True)
@given(sentence=_market_sentences(), whitespace=st.sampled_from(("", " ", "\n\t")))
def test_bound_at_sentence_complete_mode_short_tail_property(
    sentence: str, whitespace: str
) -> None:
    text = whitespace + sentence + "  아직 이어지는 설명" + whitespace
    cap = len(text)
    expected = whitespace + sentence

    assert bound_at_sentence(text, cap) == text
    assert bound_at_sentence(text, cap, require_complete=True) == expected
    assert bound_at_sentence(expected, cap, require_complete=True) == expected


@given(
    body=st.text(alphabet=st.sampled_from(tuple("가나다라마바사ABC")), min_size=1, max_size=40),
    remainder=st.text(
        alphabet=st.sampled_from(tuple("가나다라마바사 ABC")), min_size=1, max_size=40
    ),
)
def test_bound_at_sentence_is_byte_idempotent(body: str, remainder: str) -> None:
    sentence = f"{body}."
    text = f"{sentence} {remainder}"

    once = bound_at_sentence(text, len(sentence))

    assert once == sentence
    assert bound_at_sentence(once, len(sentence)) == once


def test_utf16_units_ascii_is_one_per_char() -> None:
    assert utf16_units("hello") == 5


def test_utf16_units_empty_is_zero() -> None:
    assert utf16_units("") == 0


def test_utf16_units_korean_is_one_per_char() -> None:
    # BMP CJK / Hangul syllables are single UTF-16 units.
    assert utf16_units("안녕") == 2


def test_utf16_units_emoji_is_two_per_codepoint() -> None:
    # Non-BMP emoji encode as a surrogate pair → 2 UTF-16 units each.
    assert utf16_units("📈") == 2
    assert utf16_units("📈📈📈") == 6


def test_utf16_units_mixed_bmp_and_surrogate() -> None:
    # "A" (1) + "📈" (2) + "가" (1) = 4 units.
    assert utf16_units("A📈가") == 4


def test_utf16_truncate_passthrough_when_under_limit() -> None:
    assert utf16_truncate("hello", 100) == "hello"


def test_utf16_truncate_passthrough_at_exact_limit() -> None:
    assert utf16_truncate("hello", 5) == "hello"


def test_utf16_truncate_zero_max_returns_empty() -> None:
    assert utf16_truncate("anything", 0) == ""


def test_utf16_truncate_negative_max_returns_empty() -> None:
    assert utf16_truncate("anything", -3) == ""


def test_utf16_truncate_bmp_cut() -> None:
    assert utf16_truncate("hello", 3) == "hel"


def test_utf16_truncate_drops_partial_surrogate_pair() -> None:
    # Three emoji = 6 UTF-16 units. Cutting at 3 units would land in the
    # middle of the second emoji's surrogate pair; the helper rolls back
    # one unit, leaving exactly one whole emoji.
    text = "📈📈📈"
    assert utf16_units(text) == 6
    truncated = utf16_truncate(text, 3)
    assert truncated == "📈"
    assert utf16_units(truncated) == 2


def test_utf16_truncate_keeps_whole_pair_at_even_boundary() -> None:
    text = "📈📈📈"
    assert utf16_truncate(text, 4) == "📈📈"


def test_utf16_truncate_lone_high_surrogate_at_position_zero() -> None:
    # Truncating "📈AB" to 1 unit would keep only the high surrogate of
    # the emoji; the rollback drops it, yielding the empty string rather
    # than emitting half a code point.
    assert utf16_truncate("📈AB", 1) == ""


def test_truncate_with_suffix_passthrough_when_under_limit() -> None:
    # Fits within budget → returned unchanged, NO suffix appended.
    assert truncate_with_suffix("hello", 100) == "hello"


def test_truncate_with_suffix_appends_ellipsis_on_overflow() -> None:
    # "hello" = 5 units; cap 4 → body truncated to 3 units + "…" (1 unit).
    result = truncate_with_suffix("hello", 4)
    assert result == "hel…"
    assert utf16_units(result) == 4


def test_truncate_with_suffix_matches_inline_idiom() -> None:
    # Equivalent to the pre-u79 operator_alerter inline:
    #   utf16_truncate(text, cap - 1) + "…"
    text = "x" * 50
    cap = 10
    expected = utf16_truncate(text, cap - 1) + UTF16_TRUNCATION_SUFFIX
    assert truncate_with_suffix(text, cap) == expected
    assert utf16_units(truncate_with_suffix(text, cap)) == cap


def test_truncate_with_suffix_custom_suffix() -> None:
    result = truncate_with_suffix("hello world", 6, suffix="..")
    assert result == "hell.."
    assert utf16_units(result) == 6


def test_truncate_with_suffix_surrogate_safe() -> None:
    # Emoji body with an ellipsis: the truncation point must not split a
    # surrogate pair even when leaving room for the 1-unit suffix.
    text = "📈📈📈"  # 6 units
    result = truncate_with_suffix(text, 4)  # body budget 3 → 1 emoji + "…"
    assert result == "📈…"
    assert utf16_units(result) <= 4
