"""u55 Step 3 — Tests for direction-vs-anchor sanity gate."""

from __future__ import annotations

from decimal import Decimal

from investo.briefing.date_corruption import verify_direction_against_anchor
from investo.briefing.market_anchor import MarketAnchor


def _anchor(
    *,
    ticker: str = "^GSPC",
    close: str = "5820.40",
    pct: str | None = "0.85",
    is_ath: bool = False,
    pct_from_52w_high: str | None = None,
) -> MarketAnchor:
    return MarketAnchor(
        ticker=ticker,
        close=Decimal(close),
        prev_close=None,
        pct=Decimal(pct) if pct is not None else None,
        is_ath=is_ath,
        pct_from_52w_high=Decimal(pct_from_52w_high) if pct_from_52w_high is not None else None,
        pct_from_52w_low=None,
        mtd_pct=None,
        ytd_pct=None,
        volume_z_score=None,
    )


def test_no_anchor_returns_empty() -> None:
    assert verify_direction_against_anchor("[강세] 흐름", anchors=()) == ()


def test_bullish_matches_positive_pct() -> None:
    text = "[강세] 흐름이 이어졌다"
    assert verify_direction_against_anchor(text, [_anchor(pct="0.85")]) == ()


def test_bullish_against_negative_pct_flags() -> None:
    text = "[강세] 흐름"
    out = verify_direction_against_anchor(text, [_anchor(pct="-0.42")])
    assert len(out) == 1
    assert out[0].body_claim == "bullish"
    assert out[0].anchor_pct == Decimal("-0.42")


def test_bearish_matches_negative_pct() -> None:
    text = "[약세] 마감"
    assert verify_direction_against_anchor(text, [_anchor(pct="-0.42")]) == ()


def test_bearish_against_positive_pct_flags() -> None:
    text = "하락 마감"
    out = verify_direction_against_anchor(text, [_anchor(pct="0.85")])
    assert len(out) == 1
    assert out[0].body_claim == "bearish"


def test_ath_claim_against_non_ath_anchor_flags() -> None:
    out = verify_direction_against_anchor(
        "S&P 500 ATH 갱신", [_anchor(is_ath=False, pct_from_52w_high="-1.4")]
    )
    assert len(out) == 1
    assert out[0].body_claim == "ath"


def test_ath_claim_with_is_ath_true_passes() -> None:
    out = verify_direction_against_anchor("ATH 갱신", [_anchor(is_ath=True)])
    assert out == ()


def test_52w_high_claim_far_from_high_flags() -> None:
    out = verify_direction_against_anchor("52주 최고가 갱신", [_anchor(pct_from_52w_high="-3.2")])
    assert len(out) == 1
    assert out[0].body_claim == "fiftytwoweek_high"


def test_no_direction_claim_no_conflict() -> None:
    out = verify_direction_against_anchor("오늘은 별 변동 없이 마감했다", [_anchor(pct="-2.5")])
    assert out == ()


def test_anchor_priority_uses_first_matching_ticker() -> None:
    # Priority list picks ^GSPC over ^IXIC.
    out = verify_direction_against_anchor(
        "[강세]",
        [
            _anchor(ticker="^IXIC", pct="1.5"),
            _anchor(ticker="^GSPC", pct="-0.3"),
        ],
    )
    assert len(out) == 1
    assert out[0].ticker == "^GSPC"
