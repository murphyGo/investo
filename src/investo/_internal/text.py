"""Text helpers shared across internal unit boundaries."""

from __future__ import annotations

import re
from typing import Final

# Shared cap for stderr excerpts included in operator-visible errors.
STDERR_BYTE_CAP: Final[int] = 1024

# Shared "does this text carry alnum / Hangul content?" probe for pure
# internal validation helpers. Adapter packages may re-export it for
# compatibility, but this module is the inward contract home.
MEANINGFUL_TEXT: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9가-힣]")


def truncate_stderr(value: str | None) -> str | None:
    """Truncate ``value`` to ``STDERR_BYTE_CAP`` UTF-8 bytes.

    Returns ``None`` for ``None`` input. For non-None strings, the cap
    is enforced on encoded UTF-8 bytes, not code points. A cut that
    lands mid-codepoint is recovered by decoding with ``errors="ignore"``,
    dropping the partial sequence cleanly.
    """

    if value is None:
        return None
    encoded = value.encode("utf-8")
    if len(encoded) <= STDERR_BYTE_CAP:
        return value
    return encoded[:STDERR_BYTE_CAP].decode("utf-8", errors="ignore")


# u79 — UTF-16 truncation suffix. 1 UTF-16 code unit (BMP character).
# Kept here so the "truncate + append ellipsis" pattern has a single home.
UTF16_TRUNCATION_SUFFIX: Final[str] = "…"


def utf16_units(text: str) -> int:
    """Return the count of UTF-16 code units in ``text``.

    Equivalent to ``len(text.encode("utf-16-le")) // 2``. Non-BMP
    code points (emoji, certain CJK) count as 2 units. Telegram's
    ``sendMessage`` text limit (4096) is measured in these units, not
    in Python codepoints, so this is the count callers must budget
    against.
    """
    return len(text.encode("utf-16-le")) // 2


def utf16_truncate(text: str, max_units: int) -> str:
    """Truncate ``text`` to at most ``max_units`` UTF-16 code units.

    Surrogate-pair safe: a truncation that lands between the high
    and low halves of a non-BMP code point's UTF-16 encoding is
    rolled back by one unit so the result remains valid UTF-16.
    ``max_units <= 0`` yields the empty string; a ``text`` already
    within budget is returned unchanged.
    """
    encoded = text.encode("utf-16-le")
    if len(encoded) // 2 <= max_units:
        return text
    if max_units <= 0:
        return ""
    truncated_bytes = encoded[: max_units * 2]
    # If the final unit is a high surrogate (the first half of a
    # surrogate pair), drop it to avoid emitting half a code point.
    last_unit = int.from_bytes(truncated_bytes[-2:], "little")
    if 0xD800 <= last_unit <= 0xDBFF:
        truncated_bytes = truncated_bytes[:-2]
    return truncated_bytes.decode("utf-16-le", errors="ignore")


def truncate_with_suffix(
    text: str,
    max_units: int,
    *,
    suffix: str = UTF16_TRUNCATION_SUFFIX,
) -> str:
    """Truncate ``text`` to ``max_units`` UTF-16 units, appending ``suffix``.

    When ``text`` already fits within ``max_units`` it is returned
    unchanged (no suffix). Otherwise the body is truncated so that the
    body plus ``suffix`` together occupy at most ``max_units`` UTF-16
    code units, then ``suffix`` is appended. This mirrors the
    ``utf16_truncate(text, cap - 1) + "…"`` idiom the notifier used
    inline before u79.
    """
    if utf16_units(text) <= max_units:
        return text
    suffix_units = utf16_units(suffix)
    body = utf16_truncate(text, max_units - suffix_units)
    return body + suffix
