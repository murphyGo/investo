"""Exact, plain-string formatting for decimal metadata values."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Final

_MAX_DECIMAL_INPUT_CHARS: Final[int] = 128
_MAX_FIXED_DECIMAL_CHARS: Final[int] = 128


def shortest_exact_decimal(raw: str) -> str | None:
    """Return ``raw`` as the shortest exact fixed-point Decimal string.

    Trailing fractional zeroes and a trailing decimal point are removed. The
    conversion never quantizes or rounds, and fixed-point formatting prevents
    exponent notation. Invalid and non-finite values fail closed with ``None``
    so callers can use their existing missing-value behavior.
    """
    stripped = raw.strip()
    if not stripped or len(stripped) > _MAX_DECIMAL_INPUT_CHARS:
        return None
    try:
        value = Decimal(stripped)
    except InvalidOperation:
        return None
    if not value.is_finite():
        return None
    if value.is_zero():
        return "0"

    sign, raw_digits, raw_exponent = value.as_tuple()
    if not isinstance(raw_exponent, int):
        return None
    digits = list(raw_digits)
    exponent = raw_exponent
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exponent += 1

    digit_text = "".join(str(digit) for digit in digits)
    decimal_position = len(digit_text) + exponent
    sign_chars = 1 if sign else 0
    if exponent >= 0:
        body_length = len(digit_text) + exponent
    elif decimal_position > 0:
        body_length = len(digit_text) + 1
    else:
        body_length = 2 - decimal_position + len(digit_text)
    if sign_chars + body_length > _MAX_FIXED_DECIMAL_CHARS:
        return None

    if exponent >= 0:
        body = digit_text + ("0" * exponent)
    elif decimal_position > 0:
        body = f"{digit_text[:decimal_position]}.{digit_text[decimal_position:]}"
    else:
        body = f"0.{('0' * -decimal_position)}{digit_text}"
    return f"-{body}" if sign else body


__all__ = ["shortest_exact_decimal"]
