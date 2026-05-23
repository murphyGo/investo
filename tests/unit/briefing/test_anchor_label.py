"""u70 — canonical symbol / display-label registry.

The registry is the single source of truth for how each core anchor
symbol is named on every reader surface. The regression of record:
``^IXIC`` (Nasdaq Composite) must never be labelled Nasdaq 100 (``^NDX``).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from investo.briefing.market_anchor import AnchorLabel, anchor_label


@pytest.mark.parametrize(
    ("symbol", "expected_short", "expected_ko"),
    [
        ("^GSPC", "S&P500", "S&P 500"),
        ("^IXIC", "Nasdaq", "나스닥 종합"),
        ("^DJI", "Dow", "다우존스"),
        ("^NDX", "NDX", "나스닥 100"),
        ("BTC-USD", "BTC", "비트코인"),
        ("^KOSPI", "KOSPI", "코스피"),
        ("KRW=X", "USD/KRW", "원/달러"),
    ],
)
def test_known_symbols_resolve(symbol: str, expected_short: str, expected_ko: str) -> None:
    label = anchor_label(symbol)
    assert label.short == expected_short
    assert label.ko == expected_ko


def test_ixic_is_never_nasdaq_100() -> None:
    label = anchor_label("^IXIC")
    assert "100" not in label.ko
    assert "100" not in label.short
    assert label.short != "NDX"
    # The Nasdaq 100 has its own distinct symbol/label.
    assert anchor_label("^NDX").ko == "나스닥 100"
    assert anchor_label("^NDX").symbol != anchor_label("^IXIC").symbol


def test_unknown_symbol_falls_back_to_raw() -> None:
    label = anchor_label("ZZZZ")
    assert isinstance(label, AnchorLabel)
    assert label.symbol == "ZZZZ"
    assert label.short == "ZZZZ"
    assert label.ko == "ZZZZ"
    assert label.display == "ZZZZ"


def test_label_is_frozen() -> None:
    label = anchor_label("^GSPC")
    with pytest.raises(ValidationError):
        label.short = "mutated"  # type: ignore[misc]
