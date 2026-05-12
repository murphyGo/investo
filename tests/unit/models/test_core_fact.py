"""u55 Step 1 — Tests for the CoreFact / market_calendar / mapping foundation."""

from __future__ import annotations

from datetime import date, datetime
from typing import get_args
from zoneinfo import ZoneInfo

from investo.models.core_fact import (
    CORE_FACT_KEYWORDS,
    CORE_FACT_TOLERANCE,
    CoreFact,
    is_core_fact,
)
from investo.models.market_calendar import (
    KRX_HOLIDAYS_2026,
    NYSE_HOLIDAYS_2026,
    is_holiday,
    is_trading_day,
    next_expected_trading_day,
    previous_trading_day,
)
from investo.sources._core_fact_map import (
    CORE_FACT_METADATA_PREFIX,
    core_fact_for_ticker,
    core_fact_metadata_key,
)

# --- CoreFact enum --------------------------------------------------------


def test_core_fact_has_exactly_ten_values() -> None:
    assert len(get_args(CoreFact)) == 10


def test_core_fact_values_are_unique_and_sluggified() -> None:
    values = get_args(CoreFact)
    assert len(set(values)) == len(values)
    for value in values:
        assert value == value.lower()
        assert " " not in value


def test_is_core_fact_truthy_for_each_enum() -> None:
    for value in get_args(CoreFact):
        assert is_core_fact(value)


def test_is_core_fact_rejects_unknown() -> None:
    assert not is_core_fact("kospi")  # missing _close
    assert not is_core_fact("KOSPI_CLOSE")  # case-sensitive
    assert not is_core_fact("")


# --- CORE_FACT_KEYWORDS ---------------------------------------------------


def test_every_core_fact_has_at_least_one_keyword() -> None:
    for fact in get_args(CoreFact):
        assert fact in CORE_FACT_KEYWORDS
        assert len(CORE_FACT_KEYWORDS[fact]) >= 1
        for token in CORE_FACT_KEYWORDS[fact]:
            assert token.strip() == token
            assert len(token) >= 1


def test_keywords_cover_both_korean_and_english_for_indices() -> None:
    # Every market-index CoreFact should expose at least one Korean
    # token and at least one ASCII token — Stage 2 prose mixes both.
    for fact in ("kospi_close", "kosdaq_close", "spx_close", "ndx_close", "dji_close"):
        tokens = CORE_FACT_KEYWORDS[fact]
        has_korean = any(any("가" <= ch <= "힣" for ch in t) for t in tokens)
        has_ascii = any(t.isascii() for t in tokens)
        assert has_korean, fact
        assert has_ascii, fact


# --- CORE_FACT_TOLERANCE --------------------------------------------------


def test_every_core_fact_has_a_tolerance() -> None:
    for fact in get_args(CoreFact):
        assert fact in CORE_FACT_TOLERANCE
        # Tolerance is Decimal-as-string; coerce check.
        from decimal import Decimal

        assert Decimal(CORE_FACT_TOLERANCE[fact]) > 0


# --- market_calendar ------------------------------------------------------


def test_krx_holidays_includes_new_year_and_chuseok() -> None:
    assert date(2026, 1, 1) in KRX_HOLIDAYS_2026
    assert date(2026, 9, 25) in KRX_HOLIDAYS_2026  # 추석


def test_nyse_holidays_includes_new_year_and_thanksgiving() -> None:
    assert date(2026, 1, 1) in NYSE_HOLIDAYS_2026
    assert date(2026, 11, 26) in NYSE_HOLIDAYS_2026


def test_is_holiday_weekend_for_equity_segments() -> None:
    saturday = date(2026, 5, 9)
    sunday = date(2026, 5, 10)
    assert is_holiday("domestic-equity", saturday)
    assert is_holiday("us-equity", sunday)


def test_is_holiday_weekend_for_crypto_is_false() -> None:
    saturday = date(2026, 5, 9)
    assert not is_holiday("crypto", saturday)


def test_is_holiday_listed_krx_day() -> None:
    assert is_holiday("domestic-equity", date(2026, 5, 5))  # 어린이날
    assert is_trading_day("domestic-equity", date(2026, 5, 7))  # 평일


def test_previous_trading_day_skips_weekend() -> None:
    monday = date(2026, 5, 11)
    # KRX weekend skip — Friday May 8 is a trading day.
    assert previous_trading_day("domestic-equity", monday) == date(2026, 5, 8)


def test_previous_trading_day_skips_holiday() -> None:
    # The day after 어린이날 (May 6 Wed): previous trading day is May 4 Mon.
    assert previous_trading_day("domestic-equity", date(2026, 5, 6)) == date(2026, 5, 4)


def test_next_expected_trading_day_crypto_returns_today_utc() -> None:
    now = datetime(2026, 5, 9, 12, 0, tzinfo=ZoneInfo("UTC"))
    assert next_expected_trading_day("crypto", now) == date(2026, 5, 9)


def test_next_expected_trading_day_us_equity_weekend_backs_off() -> None:
    saturday_ny_noon = datetime(2026, 5, 9, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    assert next_expected_trading_day("us-equity", saturday_ny_noon) == date(2026, 5, 8)


def test_next_expected_trading_day_kst_holiday_backs_off() -> None:
    # 2026-05-05 KST is 어린이날 → expected = May 4 (Mon).
    kst_noon = datetime(2026, 5, 5, 12, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    assert next_expected_trading_day("domestic-equity", kst_noon) == date(2026, 5, 4)


# --- _core_fact_map -------------------------------------------------------


def test_core_fact_for_known_ticker() -> None:
    assert core_fact_for_ticker("^GSPC") == "spx_close"
    assert core_fact_for_ticker("BTC-USD") == "btc_usd"
    assert core_fact_for_ticker("^KS11") == "kospi_close"
    assert core_fact_for_ticker("KRW=X") == "usd_krw"
    assert core_fact_for_ticker("^TNX") == "us10y_yield"
    assert core_fact_for_ticker("^VIX") == "vix"


def test_core_fact_for_unknown_ticker_returns_none() -> None:
    assert core_fact_for_ticker("AAPL") is None  # equity, not a core fact
    assert core_fact_for_ticker("XLK") is None  # sector ETF, not a core fact
    assert core_fact_for_ticker("") is None


def test_core_fact_metadata_key_format() -> None:
    assert core_fact_metadata_key("spx_close") == "core_fact:spx_close"
    assert core_fact_metadata_key("btc_usd") == f"{CORE_FACT_METADATA_PREFIX}btc_usd"


def test_metadata_key_round_trips_via_prefix() -> None:
    key = core_fact_metadata_key("kospi_close")
    assert key.startswith(CORE_FACT_METADATA_PREFIX)
    fact = key[len(CORE_FACT_METADATA_PREFIX) :]
    assert is_core_fact(fact)
