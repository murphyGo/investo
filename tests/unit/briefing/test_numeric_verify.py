"""u55 Step 2 — Tests for the core-fact verification gate."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from investo.briefing.numeric_verify import (
    WINDOW,
    aggregate_source_facts,
    find_body_value,
    render_downgrade_callout,
    verify_core_facts,
)
from investo.models import NormalizedItem


def _item(
    *,
    title: str = "fixture",
    raw_metadata: dict[str, str] | None = None,
    source_name: str = "yfinance-price",
) -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name,
        category="price",
        title=title,
        summary=None,
        url="https://example.com/x",
        published_at=datetime(2026, 5, 11, 20, 0, tzinfo=UTC),
        raw_metadata=raw_metadata or {},
    )


# --- aggregate_source_facts ----------------------------------------------


def test_aggregate_picks_up_prefix_keys() -> None:
    items = [
        _item(raw_metadata={"ticker": "^GSPC", "core_fact:spx_close": "5820.40"}),
        _item(raw_metadata={"ticker": "BTC-USD", "core_fact:btc_usd": "62100.00"}),
    ]
    out = aggregate_source_facts(items)
    assert out == {"spx_close": Decimal("5820.40"), "btc_usd": Decimal("62100.00")}


def test_aggregate_skips_non_prefix_metadata() -> None:
    items = [_item(raw_metadata={"ticker": "AAPL", "close": "193.40"})]
    assert aggregate_source_facts(items) == {}


def test_aggregate_skips_unknown_fact_typo() -> None:
    items = [_item(raw_metadata={"core_fact:typo_field": "1.0"})]
    assert aggregate_source_facts(items) == {}


def test_aggregate_skips_malformed_decimal() -> None:
    items = [_item(raw_metadata={"core_fact:spx_close": "not a number"})]
    assert aggregate_source_facts(items) == {}


def test_aggregate_last_writer_wins() -> None:
    items = [
        _item(
            raw_metadata={"core_fact:kospi_close": "2820.40"},
            source_name="fsc-krx-index-price",
        ),
        _item(
            raw_metadata={"core_fact:kospi_close": "2820.41"},
            source_name="yonhap-index-close",
        ),
    ]
    # Both current domestic adapters can stamp the same close within tolerance.
    out = aggregate_source_facts(items)
    assert out["kospi_close"] in (Decimal("2820.40"), Decimal("2820.41"))


# --- find_body_value (keyword-window scan) -------------------------------


def test_find_body_value_korean_keyword() -> None:
    text = "코스피는 2,810.45 포인트로 마감했다."
    assert find_body_value(text, "kospi_close") == Decimal("2810.45")


def test_find_body_value_english_keyword() -> None:
    text = "S&P 500 closed at 5,820.40 on Friday."
    assert find_body_value(text, "spx_close") == Decimal("5820.40")


def test_find_body_value_keyword_not_present_returns_none() -> None:
    assert find_body_value("아무 내용", "kospi_close") is None


def test_find_body_value_decimal_outside_window_skipped() -> None:
    # KOSPI keyword followed by a wall of text > WINDOW chars before 1234.56.
    padding = "x" * (WINDOW + 20)
    text = f"코스피{padding}1234.56"
    assert find_body_value(text, "kospi_close") is None


def test_find_body_value_picks_closest_match() -> None:
    text = "다른 숫자 999.99 .. 코스피 2,810.45 ... 후속 8888.88 다른 단락"
    # Both 2,810.45 (close to 코스피) and 8888.88 (further away) fall in
    # window; the closest (2810.45) wins.
    assert find_body_value(text, "kospi_close") == Decimal("2810.45")


def test_find_body_value_skips_tiny_bare_integers() -> None:
    # "코스피 5" should not match — bare 1-2 digit integers below 100 are skipped.
    text = "코스피 5는 코스피 종목 수와 관련된 임의 카운트"
    assert find_body_value(text, "kospi_close") is None


def test_find_body_value_accepts_decimal_with_no_thousands() -> None:
    text = "BTC 62100.00에 마감"
    assert find_body_value(text, "btc_usd") == Decimal("62100.00")


# --- verify_core_facts ----------------------------------------------------


def test_verify_pass_when_body_matches_source_within_tolerance() -> None:
    text = "S&P 500는 5,820.40에 마감했다."
    items = [_item(raw_metadata={"core_fact:spx_close": "5820.40"})]
    report = verify_core_facts(text, items)
    assert report.verified == ("spx_close",)
    assert report.conflicts == ()
    assert report.actions == {"spx_close": "pass"}


def test_verify_pass_with_micro_rounding_inside_tolerance() -> None:
    # Tolerance for index close is ±0.01 (Decimal).
    text = "S&P 500는 5,820.41에 마감했다."
    items = [_item(raw_metadata={"core_fact:spx_close": "5820.40"})]
    report = verify_core_facts(text, items)
    assert report.verified == ("spx_close",)


def test_verify_conflict_when_outside_tolerance() -> None:
    text = "S&P 500는 5,900.00에 마감했다."
    items = [_item(raw_metadata={"core_fact:spx_close": "5820.40"})]
    report = verify_core_facts(text, items)
    assert report.verified == ()
    assert len(report.conflicts) == 1
    conflict = report.conflicts[0]
    assert conflict.fact == "spx_close"
    assert conflict.body_value == Decimal("5900.00")
    assert conflict.source_value == Decimal("5820.40")
    assert conflict.delta == Decimal("79.60")
    assert report.actions == {"spx_close": "downgrade"}


def test_verify_unverified_when_no_source_fact() -> None:
    text = "코스피는 2,810.45 포인트로 마감"
    items: list[NormalizedItem] = []  # no source facts
    report = verify_core_facts(text, items)
    assert report.unverified == ("kospi_close",)
    assert report.actions == {"kospi_close": "downgrade"}


def test_verify_btc_within_tolerance() -> None:
    # BTC tolerance is ±$1 — body $62,100 vs source $62,100.50 ⇒ pass.
    text = "BTC는 62,100에 거래되었다."
    items = [_item(raw_metadata={"core_fact:btc_usd": "62100.50"})]
    report = verify_core_facts(text, items)
    assert "btc_usd" in report.verified


def test_verify_btc_beyond_tolerance() -> None:
    # BTC tolerance is ±$1 — body $62,100 vs source $61,000 ⇒ conflict.
    text = "BTC는 62,100에 거래되었다."
    items = [_item(raw_metadata={"core_fact:btc_usd": "61000"})]
    report = verify_core_facts(text, items)
    assert report.verified == ()
    assert len(report.conflicts) == 1
    assert report.conflicts[0].fact == "btc_usd"


def test_verify_ignores_facts_not_in_body() -> None:
    text = "오늘 KOSPI 2,810.45."
    items = [
        _item(raw_metadata={"core_fact:kospi_close": "2810.45"}),
        # NDX in source but never mentioned in body — should not appear.
        _item(raw_metadata={"core_fact:ndx_close": "18450.20"}),
    ]
    report = verify_core_facts(text, items)
    assert report.verified == ("kospi_close",)
    assert "ndx_close" not in report.actions


def test_verify_idempotent() -> None:
    text = "코스피 2,810.45 마감"
    items = [_item(raw_metadata={"core_fact:kospi_close": "2810.45"})]
    a = verify_core_facts(text, items)
    b = verify_core_facts(text, items)
    assert a == b


def test_figures_verified_rate_none_when_no_body_mentions() -> None:
    report = verify_core_facts("아무것도 언급 없음", [])
    assert report.figures_verified_rate is None


def test_figures_verified_rate_one_when_all_pass() -> None:
    text = "코스피 2,810.45 마감"
    items = [_item(raw_metadata={"core_fact:kospi_close": "2810.45"})]
    assert verify_core_facts(text, items).figures_verified_rate == 1.0


def test_figures_verified_rate_partial() -> None:
    text = "코스피 2,810.45, S&P 500 9,999.99 마감"
    items = [_item(raw_metadata={"core_fact:kospi_close": "2810.45"})]
    rate = verify_core_facts(text, items).figures_verified_rate
    assert rate is not None
    # 1 verified out of 2 mentioned.
    assert 0.49 < rate < 0.51


# --- render_downgrade_callout --------------------------------------------


def test_render_callout_empty_when_no_downgrades() -> None:
    text = "S&P 500는 5,820.40 마감"
    items = [_item(raw_metadata={"core_fact:spx_close": "5820.40"})]
    report = verify_core_facts(text, items)
    assert render_downgrade_callout(report) == ""


def test_render_callout_includes_unverified_and_conflicts() -> None:
    text = "코스피 2,810.45, S&P 500 9,999.99"
    items = [_item(raw_metadata={"core_fact:spx_close": "5820.40"})]
    report = verify_core_facts(text, items)
    out = render_downgrade_callout(report)
    assert out.startswith("> ⚠️ 확인 필요:")
    assert "kospi_close" in out  # unverified
    assert "spx_close" in out  # conflict
    assert out.endswith("\n")
