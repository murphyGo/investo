from __future__ import annotations

import pytest

from investo._internal.decimal_format import shortest_exact_decimal


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        ("0.0001000000000000", "0.0001"),
        ("0.0100", "0.01"),
        ("1.000", "1"),
        ("1000.000", "1000"),
        ("1E-7", "0.0000001"),
        ("1E+3", "1000"),
        ("-0.0000", "0"),
    ),
)
def test_shortest_exact_decimal_uses_plain_notation(raw: str, expected: str) -> None:
    assert shortest_exact_decimal(raw) == expected


@pytest.mark.parametrize("raw", ("not-a-number", "NaN", "Infinity", "-Infinity"))
def test_shortest_exact_decimal_rejects_invalid_or_non_finite(raw: str) -> None:
    assert shortest_exact_decimal(raw) is None


@pytest.mark.parametrize(
    "raw",
    (
        "1E+999999999",
        "1E-999999999",
        "9" * 129,
    ),
)
def test_shortest_exact_decimal_rejects_unbounded_fixed_output(raw: str) -> None:
    assert shortest_exact_decimal(raw) is None


def test_shortest_exact_decimal_handles_large_exponent_zero_before_expansion() -> None:
    assert shortest_exact_decimal("0E-999999999") == "0"


def test_shortest_exact_decimal_accepts_bounded_signed_output() -> None:
    expected = f"-1{'0' * 126}"
    assert len(expected) == 128
    assert shortest_exact_decimal("-1E+126") == expected
