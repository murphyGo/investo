"""Unit tests for ``investo.sources._config.parse_symbol_list``.

Pins NFR AC-5.5 (env-var override convention) and FD R12 (env-var
naming + parse semantics) for the shared helper that all
extension-2026-05 adapters consume.
"""

from __future__ import annotations

import pytest

from investo.sources._config import format_float, format_int, parse_symbol_list

_DEFAULTS: tuple[str, ...] = ("AAPL", "MSFT", "GOOGL")
_ENV = "INVESTO_TEST_TICKERS"


def test_env_unset_returns_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_ENV, raising=False)
    assert parse_symbol_list(_ENV, _DEFAULTS) == _DEFAULTS


def test_env_empty_string_returns_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_ENV, "")
    assert parse_symbol_list(_ENV, _DEFAULTS) == _DEFAULTS


def test_env_whitespace_only_returns_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_ENV, "   ")
    assert parse_symbol_list(_ENV, _DEFAULTS) == _DEFAULTS


def test_env_only_commas_returns_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    # Yields zero non-empty tokens after split + strip → fall through to defaults.
    monkeypatch.setenv(_ENV, ",,,")
    assert parse_symbol_list(_ENV, _DEFAULTS) == _DEFAULTS


def test_simple_comma_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_ENV, "AAPL,MSFT,GOOGL")
    assert parse_symbol_list(_ENV, _DEFAULTS) == ("AAPL", "MSFT", "GOOGL")


def test_whitespace_around_tokens_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_ENV, "  AAPL  ,  MSFT  ")
    assert parse_symbol_list(_ENV, _DEFAULTS) == ("AAPL", "MSFT")


def test_empty_tokens_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    # Trailing comma + adjacent commas + whitespace-only token all drop.
    monkeypatch.setenv(_ENV, "AAPL,,MSFT, ,GOOGL,")
    assert parse_symbol_list(_ENV, _DEFAULTS) == ("AAPL", "MSFT", "GOOGL")


def test_single_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_ENV, "TSLA")
    assert parse_symbol_list(_ENV, _DEFAULTS) == ("TSLA",)


def test_case_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    # Yahoo index symbols like ``^GSPC`` are case-sensitive at the API
    # boundary; the parser MUST NOT lowercase / uppercase tokens.
    monkeypatch.setenv(_ENV, "^GSPC,^IXIC,^DJI,bitcoin,Ethereum")
    assert parse_symbol_list(_ENV, _DEFAULTS) == (
        "^GSPC",
        "^IXIC",
        "^DJI",
        "bitcoin",
        "Ethereum",
    )


def test_defaults_not_mutated_by_override(monkeypatch: pytest.MonkeyPatch) -> None:
    # Defaults is a tuple (immutable) but we still pin the contract: a
    # successful override returns a fresh tuple, not the defaults
    # reference, so callers can't accidentally mutate state shared with
    # the module-level constant.
    monkeypatch.setenv(_ENV, "META")
    result = parse_symbol_list(_ENV, _DEFAULTS)
    assert result == ("META",)
    assert result is not _DEFAULTS
    # And defaults itself is unchanged after several overridden calls.
    monkeypatch.setenv(_ENV, "AAPL,MSFT")
    parse_symbol_list(_ENV, _DEFAULTS)
    assert _DEFAULTS == ("AAPL", "MSFT", "GOOGL")


def test_format_float_uses_canonical_six_decimal_places() -> None:
    assert format_float(1.5) == "1.500000"
    assert format_float(311.054) == "311.054000"


def test_format_float_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError):
        format_float(float("nan"))


def test_format_int_uses_plain_decimal_string() -> None:
    assert format_int(1_100_000) == "1100000"
