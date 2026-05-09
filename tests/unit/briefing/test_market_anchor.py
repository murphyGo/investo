"""Tests for ``investo.briefing.market_anchor`` (u49).

Pins the deterministic facts the brief header line cites:

* ATH detection (today's close >= prior history max).
* 52-week high / low distance percentages.
* MTD / YTD percentage versus the period-first-business-day close.
* Volume z-score versus the trailing 60-day mean / pstdev.
* Graceful degrade for short history (< 20 rows) and missing volume.
* Header rendering — priority ordering, ATH marker, range phrase
  selection (closer-to-high vs closer-to-low), MTD/YTD threshold.
* Determinism: identical inputs ⇒ identical outputs.

The test set also walks the recorded Yahoo Finance fixture files
(``tests/unit/sources/fixtures/api/yfinance-history/``) end-to-end
through :func:`parse_chart_payload` → :func:`compute_market_anchors`
to pin the contract on real recorded bytes (R10).
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from investo.briefing.market_anchor import (
    DEFAULT_HISTORY_WINDOW_DAYS,
    MarketAnchor,
    OHLCRow,
    compute_market_anchors,
    render_market_anchor_line,
)
from investo.sources.yfinance_history import parse_chart_payload

_HISTORY_FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "unit"
    / "sources"
    / "fixtures"
    / "api"
    / "yfinance-history"
)


def _row(
    trading_date: date,
    close: float,
    *,
    volume: float | None = 100.0,
) -> OHLCRow:
    return OHLCRow(
        trading_date=trading_date,
        open=Decimal(str(close)),
        high=Decimal(str(close)),
        low=Decimal(str(close)),
        close=Decimal(str(close)),
        volume=Decimal(str(volume)) if volume is not None else None,
    )


def _ramp(start_value: float, *, days: int, step: float = 1.0) -> tuple[OHLCRow, ...]:
    """Build a flat-volume monotonically-rising history of ``days`` rows."""
    return tuple(
        _row(
            date(2026, 1, 1).fromordinal(date(2026, 1, 1).toordinal() + idx),
            start_value + step * idx,
        )
        for idx in range(days)
    )


# ---------------------------------------------------------------------------
# Model — frozen + extra="forbid"
# ---------------------------------------------------------------------------


def test_market_anchor_is_frozen_and_forbids_extra() -> None:
    anchor = MarketAnchor(
        ticker="^GSPC",
        close=Decimal("100.00"),
        is_ath=True,
    )
    # Frozen — direct mutation rejected.
    try:
        anchor.ticker = "^DJI"  # type: ignore[misc]
    except (TypeError, ValueError):
        pass
    else:
        raise AssertionError("frozen MarketAnchor allowed mutation")
    # extra="forbid" — unknown fields rejected.
    import pydantic

    raised = False
    try:
        MarketAnchor(
            ticker="^GSPC",
            close=Decimal("100"),
            is_ath=True,
            unexpected_field="x",  # type: ignore[call-arg]
        )
    except pydantic.ValidationError:
        raised = True
    assert raised, "extra fields should be forbidden"


def test_ohlcrow_is_frozen() -> None:
    row = _row(date(2026, 5, 1), 100.0)
    assert row.close == Decimal("100.0")
    try:
        row.close = Decimal("200")  # type: ignore[misc]
    except (TypeError, ValueError):
        pass
    else:
        raise AssertionError("frozen OHLCRow allowed mutation")


# ---------------------------------------------------------------------------
# Empty / single-row inputs
# ---------------------------------------------------------------------------


def test_empty_history_yields_empty_tuple() -> None:
    assert compute_market_anchors({}, today=date(2026, 5, 9)) == ()


def test_ticker_with_empty_rows_is_skipped() -> None:
    # Empty ticker history is silently dropped (no exception).
    out = compute_market_anchors({"AAPL": ()}, today=date(2026, 5, 9))
    assert out == ()


def test_single_row_history_is_ath_with_none_prev() -> None:
    rows = (_row(date(2026, 5, 9), 195.0),)
    (anchor,) = compute_market_anchors({"AAPL": rows}, today=date(2026, 5, 9))
    assert anchor.ticker == "AAPL"
    assert anchor.is_ath is True
    assert anchor.prev_close is None
    assert anchor.pct is None
    assert anchor.pct_from_52w_high is None  # too short for range fields
    assert anchor.pct_from_52w_low is None
    assert anchor.mtd_pct is None
    assert anchor.ytd_pct is None
    # Single-row volume z-score is undefined.
    assert anchor.volume_z_score is None


# ---------------------------------------------------------------------------
# ATH detection
# ---------------------------------------------------------------------------


def test_ath_when_today_close_strictly_above_prior_max() -> None:
    rows = _ramp(100.0, days=30)  # last close = 129.0, max prior = 128.0
    (anchor,) = compute_market_anchors({"^GSPC": rows}, today=date(2026, 5, 9))
    assert anchor.is_ath is True
    assert anchor.pct_from_52w_high == Decimal("0.00")


def test_ath_when_today_close_equal_to_prior_max() -> None:
    # close re-tests the prior peak — equality counts as ATH.
    base = list(_ramp(100.0, days=30))
    # Force last row to equal the prior max.
    prior_max = max(r.close for r in base[:-1])
    last = base[-1]
    base[-1] = OHLCRow(
        trading_date=last.trading_date,
        open=prior_max,
        high=prior_max,
        low=prior_max,
        close=prior_max,
        volume=last.volume,
    )
    (anchor,) = compute_market_anchors({"X": tuple(base)}, today=date(2026, 5, 9))
    assert anchor.is_ath is True


def test_not_ath_when_today_below_prior_max() -> None:
    rows = list(_ramp(100.0, days=30))
    # Force last row well below the prior max.
    last = rows[-1]
    rows[-1] = OHLCRow(
        trading_date=last.trading_date,
        open=Decimal("100"),
        high=Decimal("100"),
        low=Decimal("100"),
        close=Decimal("100"),
        volume=last.volume,
    )
    (anchor,) = compute_market_anchors({"X": tuple(rows)}, today=date(2026, 5, 9))
    assert anchor.is_ath is False


# ---------------------------------------------------------------------------
# 52-week range
# ---------------------------------------------------------------------------


def test_pct_from_52w_high_negative_for_off_high_close() -> None:
    # Build a 60-day history: high=200 mid-range, last close=180.
    rows: list[OHLCRow] = []
    for i in range(60):
        close = 200.0 if i == 30 else 150.0 + i * 0.1
        rows.append(_row(date(2026, 1, 1).fromordinal(date(2026, 1, 1).toordinal() + i), close))
    # Force last close.
    rows[-1] = _row(rows[-1].trading_date, 180.0)
    (anchor,) = compute_market_anchors({"X": tuple(rows)}, today=date(2026, 5, 9))
    assert anchor.is_ath is False
    assert anchor.pct_from_52w_high is not None
    assert anchor.pct_from_52w_high == Decimal("-10.00")  # (180-200)/200 = -0.10


def test_pct_from_52w_low_positive_for_off_low_close() -> None:
    rows: list[OHLCRow] = []
    for i in range(60):
        close = 80.0 if i == 5 else 100.0 + i * 0.1
        rows.append(_row(date(2026, 1, 1).fromordinal(date(2026, 1, 1).toordinal() + i), close))
    rows[-1] = _row(rows[-1].trading_date, 88.0)
    (anchor,) = compute_market_anchors({"X": tuple(rows)}, today=date(2026, 5, 9))
    assert anchor.pct_from_52w_low == Decimal("10.00")  # (88-80)/80 = 0.10


def test_short_history_returns_none_for_range_fields() -> None:
    rows = _ramp(100.0, days=10)  # below _MIN_HISTORY_FOR_RANGE = 20
    (anchor,) = compute_market_anchors({"X": rows}, today=date(2026, 5, 9))
    assert anchor.pct_from_52w_high is None
    assert anchor.pct_from_52w_low is None
    assert anchor.mtd_pct is None
    assert anchor.ytd_pct is None
    # ATH still resolves (any non-empty history).
    assert anchor.is_ath is True


# ---------------------------------------------------------------------------
# MTD / YTD
# ---------------------------------------------------------------------------


def test_mtd_pct_versus_first_business_day_of_month() -> None:
    # Build a history spanning April + May; last close in May.
    rows = []
    for day in range(1, 31):
        rows.append(_row(date(2026, 4, day), 100.0 + day * 0.5))
    for day in range(1, 10):
        rows.append(_row(date(2026, 5, day), 120.0 + day * 1.0))
    (anchor,) = compute_market_anchors({"X": tuple(rows)}, today=date(2026, 5, 9))
    # First May row close = 121.0; last close = 129.0.
    expected = (Decimal("129.0") - Decimal("121.0")) / Decimal("121.0") * Decimal("100")
    assert anchor.mtd_pct is not None
    assert anchor.mtd_pct == expected.quantize(Decimal("0.01"))


def test_ytd_pct_versus_first_business_day_of_year() -> None:
    rows = []
    # Year 2025 history (December — does NOT count as YTD baseline for 2026).
    for day in range(1, 32):
        rows.append(_row(date(2025, 12, day), 100.0))
    # Year 2026 history starting 2026-01-02.
    for day in range(2, 32):
        rows.append(_row(date(2026, 1, day), 110.0 + day * 0.5))
    rows.append(_row(date(2026, 5, 9), 150.0))
    (anchor,) = compute_market_anchors({"X": tuple(rows)}, today=date(2026, 5, 9))
    # First 2026 row close = 110 + 2*0.5 = 111.0; last = 150.
    expected = (Decimal("150") - Decimal("111.0")) / Decimal("111.0") * Decimal("100")
    assert anchor.ytd_pct is not None
    assert anchor.ytd_pct == expected.quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# Volume z-score
# ---------------------------------------------------------------------------


def test_volume_z_score_resolves_for_normal_volume() -> None:
    # Build 30 days flat at volume=100, last day spike to 200.
    rows: list[OHLCRow] = []
    for i in range(29):
        rows.append(
            _row(
                date(2026, 1, 1).fromordinal(date(2026, 1, 1).toordinal() + i), 100.0, volume=100.0
            )
        )
    rows.append(_row(date(2026, 1, 30), 100.0, volume=200.0))
    (anchor,) = compute_market_anchors({"X": tuple(rows)}, today=date(2026, 5, 9))
    # The z-score is computed against the trailing-60-day window (we
    # only have 30 days; the helper accepts the available rows). Mean
    # ~103, pstdev > 0 → some positive z value.
    assert anchor.volume_z_score is not None
    assert anchor.volume_z_score > Decimal("1.0")


def test_volume_z_score_none_when_today_volume_zero() -> None:
    rows: list[OHLCRow] = []
    for i in range(30):
        rows.append(
            _row(date(2026, 1, 1).fromordinal(date(2026, 1, 1).toordinal() + i), 100.0, volume=0.0)
        )
    (anchor,) = compute_market_anchors({"^VIX": tuple(rows)}, today=date(2026, 5, 9))
    assert anchor.volume_z_score is None


def test_volume_z_score_none_when_stdev_zero() -> None:
    rows: list[OHLCRow] = []
    for i in range(30):
        rows.append(
            _row(
                date(2026, 1, 1).fromordinal(date(2026, 1, 1).toordinal() + i), 100.0, volume=100.0
            )
        )
    (anchor,) = compute_market_anchors({"X": tuple(rows)}, today=date(2026, 5, 9))
    # All-equal volumes → pstdev=0 → z-score undefined.
    assert anchor.volume_z_score is None


# ---------------------------------------------------------------------------
# Determinism (FD R9 / NFR-006 PBT contract)
# ---------------------------------------------------------------------------


def test_compute_market_anchors_is_deterministic() -> None:
    rows = _ramp(100.0, days=30)
    out1 = compute_market_anchors({"X": rows}, today=date(2026, 5, 9))
    out2 = compute_market_anchors({"X": rows}, today=date(2026, 5, 9))
    assert out1 == out2


# ---------------------------------------------------------------------------
# render_market_anchor_line
# ---------------------------------------------------------------------------


def test_render_empty_returns_empty_string() -> None:
    assert render_market_anchor_line(()) == ""


def test_render_ath_marker_for_ath_anchor() -> None:
    anchor = MarketAnchor(
        ticker="^GSPC",
        close=Decimal("5820.40"),
        is_ath=True,
        pct_from_52w_high=Decimal("0.00"),
        pct_from_52w_low=Decimal("30.00"),
    )
    line = render_market_anchor_line([anchor])
    assert line.startswith("> **시장 anchor**: ")
    assert line.endswith("\n")
    assert "^GSPC 5,820.40 ATH 경신" in line


def test_render_picks_closer_reference_for_off_high_anchor() -> None:
    # Close is closer to the high (-1%) than the low (+30%) → high phrase wins.
    anchor = MarketAnchor(
        ticker="^DJI",
        close=Decimal("40000.00"),
        is_ath=False,
        pct_from_52w_high=Decimal("-1.00"),
        pct_from_52w_low=Decimal("30.00"),
    )
    line = render_market_anchor_line([anchor])
    assert "(-1.00% from 52w high)" in line
    assert "from 52w low" not in line


def test_render_picks_low_reference_when_closer_to_low() -> None:
    # Close is closer to the low (+5%) than the high (-30%) → low phrase wins.
    anchor = MarketAnchor(
        ticker="X",
        close=Decimal("100.00"),
        is_ath=False,
        pct_from_52w_high=Decimal("-30.00"),
        pct_from_52w_low=Decimal("5.00"),
    )
    line = render_market_anchor_line([anchor])
    assert "(+5.00% from 52w low)" in line
    assert "from 52w high" not in line


def test_render_appends_mtd_when_threshold_exceeded() -> None:
    anchor = MarketAnchor(
        ticker="AAPL",
        close=Decimal("293.32"),
        is_ath=True,
        pct_from_52w_high=Decimal("0.00"),
        pct_from_52w_low=Decimal("50.00"),
        mtd_pct=Decimal("12.50"),
        ytd_pct=Decimal("3.00"),
    )
    line = render_market_anchor_line([anchor])
    # MTD wins over YTD (|MTD| > |YTD|).
    assert "+12.50% MTD" in line
    assert "YTD" not in line


def test_render_omits_mtd_ytd_below_threshold() -> None:
    anchor = MarketAnchor(
        ticker="AAPL",
        close=Decimal("293.32"),
        is_ath=True,
        pct_from_52w_high=Decimal("0.00"),
        pct_from_52w_low=Decimal("50.00"),
        mtd_pct=Decimal("1.00"),
        ytd_pct=Decimal("3.00"),
    )
    line = render_market_anchor_line([anchor])
    assert "MTD" not in line
    assert "YTD" not in line


def test_render_caps_at_five_anchors_with_priority() -> None:
    # Provide 8 anchors; only the top 5 by priority should render.
    anchors = [
        MarketAnchor(
            ticker="ETH-USD",
            close=Decimal("2000"),
            is_ath=False,
            pct_from_52w_high=Decimal("-10"),
            pct_from_52w_low=Decimal("20"),
        ),
        MarketAnchor(
            ticker="^DJI",
            close=Decimal("40000"),
            is_ath=False,
            pct_from_52w_high=Decimal("-1"),
            pct_from_52w_low=Decimal("20"),
        ),
        MarketAnchor(
            ticker="AAPL",
            close=Decimal("200"),
            is_ath=False,
            pct_from_52w_high=Decimal("-1"),
            pct_from_52w_low=Decimal("20"),
        ),
        MarketAnchor(
            ticker="^GSPC",
            close=Decimal("5800"),
            is_ath=True,
            pct_from_52w_high=Decimal("0"),
            pct_from_52w_low=Decimal("20"),
        ),
        MarketAnchor(
            ticker="^IXIC",
            close=Decimal("18000"),
            is_ath=False,
            pct_from_52w_high=Decimal("-1"),
            pct_from_52w_low=Decimal("20"),
        ),
        MarketAnchor(
            ticker="MSFT",
            close=Decimal("400"),
            is_ath=False,
            pct_from_52w_high=Decimal("-1"),
            pct_from_52w_low=Decimal("20"),
        ),
        MarketAnchor(
            ticker="NVDA",
            close=Decimal("200"),
            is_ath=False,
            pct_from_52w_high=Decimal("-1"),
            pct_from_52w_low=Decimal("20"),
        ),
        MarketAnchor(
            ticker="BTC-USD",
            close=Decimal("80000"),
            is_ath=False,
            pct_from_52w_high=Decimal("-1"),
            pct_from_52w_low=Decimal("20"),
        ),
    ]
    line = render_market_anchor_line(anchors)
    # Indices come first by priority — ^GSPC, ^IXIC, ^DJI lead.
    assert line.index("^GSPC") < line.index("^IXIC") < line.index("^DJI")
    # AAPL / MSFT outrank BTC-USD / ETH-USD on priority.
    assert "AAPL" in line and "MSFT" in line
    # ETH-USD does NOT appear (caps at 5 anchors).
    assert "ETH-USD" not in line
    # Verify count of anchor chunks: split on ", " then drop the prefix.
    body = line.removeprefix("> **시장 anchor**: ").rstrip("\n")
    assert len(body.split(", ")) == 5


# ---------------------------------------------------------------------------
# Real fixture replay (R10) — end-to-end parser → compute → render
# ---------------------------------------------------------------------------

_FIXTURE_TICKER_MAP: dict[str, str] = {
    "GSPC.json": "^GSPC",
    "IXIC.json": "^IXIC",
    "DJI.json": "^DJI",
    "VIX.json": "^VIX",
    "AAPL.json": "AAPL",
    "MSFT.json": "MSFT",
    "GOOGL.json": "GOOGL",
    "AMZN.json": "AMZN",
    "NVDA.json": "NVDA",
    "META.json": "META",
    "TSLA.json": "TSLA",
    "BTC-USD.json": "BTC-USD",
    "ETH-USD.json": "ETH-USD",
}


def test_recorded_yahoo_fixtures_drive_anchor_pipeline() -> None:
    """End-to-end: 13 recorded JSON payloads → 13 OHLCRow histories →
    13 MarketAnchor records → header line cites at least the 3 indices.

    This is the load-bearing R10 anti-regression: any drift in the
    Yahoo schema or the parser will break this test against the
    committed fixture bytes, before it can break a live cron.
    """
    history: dict[str, tuple[OHLCRow, ...]] = {}
    for filename, display_ticker in _FIXTURE_TICKER_MAP.items():
        payload = json.loads((_HISTORY_FIXTURE_DIR / filename).read_text())
        rows = parse_chart_payload(payload, ticker=display_ticker)
        history[display_ticker] = rows

    # All tickers parsed at least 250 rows except crypto (~365).
    for ticker, rows in history.items():
        if ticker in {"BTC-USD", "ETH-USD"}:
            assert len(rows) >= 360, f"{ticker} rows={len(rows)}"
        elif ticker == "^VIX":
            assert len(rows) >= 250
        else:
            assert len(rows) >= 250, f"{ticker} rows={len(rows)}"

    anchors = compute_market_anchors(history, today=date(2026, 5, 9))
    by_ticker = {a.ticker: a for a in anchors}
    # ATH expectations from fixture bytes (recorded 2026-05-10):
    assert by_ticker["^GSPC"].is_ath is True
    assert by_ticker["^IXIC"].is_ath is True
    assert by_ticker["AAPL"].is_ath is True
    # ^VIX volume column is all zeros → z-score must be None.
    assert by_ticker["^VIX"].volume_z_score is None

    line = render_market_anchor_line(anchors)
    assert line.startswith("> **시장 anchor**: ")
    assert "^GSPC" in line
    assert "ATH 경신" in line


def test_render_uses_default_history_window_constant_visible() -> None:
    # Smoke — the public constant is exported for orchestrator wiring.
    assert DEFAULT_HISTORY_WINDOW_DAYS == 252
