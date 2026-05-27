"""u79 — UTF-16 text primitives (moved from ``notifier/summary.py``).

Pins code-unit counting and surrogate-pair-safe truncation for BMP and
non-BMP (emoji) strings, plus the ``truncate_with_suffix`` ellipsis
idiom the notifier relies on. These supplement — they do not replace —
the unchanged ``tests/unit/notifier/test_summary.py`` assertions that
still import the same helpers via the notifier alias.
"""

from __future__ import annotations

from investo._internal.text import (
    UTF16_TRUNCATION_SUFFIX,
    truncate_with_suffix,
    utf16_truncate,
    utf16_units,
)


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
