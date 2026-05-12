"""Tests for ``investo.publisher.anchor_table`` (u51 Step 2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from investo.briefing.market_anchor import MarketAnchor, OHLCRow, compute_market_anchors
from investo.publisher.anchor_table import render_anchor_table


def _anchor(
    ticker: str,
    close: str,
    *,
    pct: str | None = None,
    is_ath: bool = False,
    high: str | None = None,
    low: str | None = None,
    mtd: str | None = None,
    ytd: str | None = None,
) -> MarketAnchor:
    return MarketAnchor(
        ticker=ticker,
        close=Decimal(close),
        prev_close=None,
        pct=Decimal(pct) if pct is not None else None,
        is_ath=is_ath,
        pct_from_52w_high=Decimal(high) if high is not None else None,
        pct_from_52w_low=Decimal(low) if low is not None else None,
        mtd_pct=Decimal(mtd) if mtd is not None else None,
        ytd_pct=Decimal(ytd) if ytd is not None else None,
    )


def test_render_anchor_table_empty_input() -> None:
    assert render_anchor_table(()) == ""


def test_render_anchor_table_single_anchor() -> None:
    out = render_anchor_table([_anchor("^GSPC", "7412.84", pct="0.37", is_ath=True)])
    assert "| 종목 | 종가 | 변동 | 비고 |" in out
    assert "| ^GSPC | 7,412.84 | +0.37% | ATH 경신 |" in out
    # Exactly 3 lines: header, divider, 1 row + trailing newline.
    assert out.count("\n") == 3


def test_render_anchor_table_priority_ordering() -> None:
    out = render_anchor_table(
        [
            _anchor("BTC-USD", "80000.00"),
            _anchor("^GSPC", "7412.84", is_ath=True),
            _anchor("^IXIC", "26274.13", is_ath=True),
        ]
    )
    # ^GSPC comes before ^IXIC, which comes before BTC-USD by _TABLE_PRIORITY.
    g = out.index("^GSPC")
    i = out.index("^IXIC")
    b = out.index("BTC-USD")
    assert g < i < b


def test_render_anchor_table_caps_at_five() -> None:
    anchors = [
        _anchor("^GSPC", "1.00", is_ath=True),
        _anchor("^IXIC", "2.00", is_ath=True),
        _anchor("^DJI", "3.00", is_ath=True),
        _anchor("AAPL", "4.00"),
        _anchor("MSFT", "5.00"),
        _anchor("NVDA", "6.00"),
        _anchor("TSLA", "7.00"),
    ]
    out = render_anchor_table(anchors)
    # 5 row cap → header + divider + 5 rows = 7 lines (+ trailing newline).
    body_lines = [line for line in out.splitlines() if line.startswith("|")]
    assert len(body_lines) == 5 + 2  # rows + header + divider
    assert "NVDA" not in out
    assert "TSLA" not in out


def test_render_anchor_table_pct_signed_format() -> None:
    out = render_anchor_table(
        [
            _anchor("AAPL", "292.68", pct="-0.22", high="-0.22", low="50.00"),
            _anchor("MSFT", "412.66", pct="2.50", low="15.67", high="-3.00"),
        ]
    )
    assert "| AAPL | 292.68 | -0.22% |" in out
    assert "| MSFT | 412.66 | +2.50% |" in out


def test_render_anchor_table_missing_pct_renders_em_dash() -> None:
    out = render_anchor_table([_anchor("X", "100.00")])
    assert "| X | 100.00 | — | — |" in out


def test_render_anchor_table_ath_with_ytd_note() -> None:
    out = render_anchor_table(
        [
            _anchor(
                "^GSPC",
                "7412.84",
                pct="0.37",
                is_ath=True,
                ytd="8.08",
            )
        ]
    )
    assert "ATH 경신 · +8.08% YTD" in out


def test_render_anchor_table_below_52w_high_phrase() -> None:
    out = render_anchor_table([_anchor("^DJI", "49704.47", pct="-0.50", high="-0.96", low="14.00")])
    assert "-0.96% from 52w high" in out


def test_render_anchor_table_off_52w_low_phrase() -> None:
    # high distance (-30%) is *farther* than low distance (+15.67%), so
    # the close is nearer the low → render the low-distance phrase.
    out = render_anchor_table([_anchor("MSFT", "412.66", pct="2.5", high="-30.00", low="15.67")])
    assert "+15.67% from 52w low" in out


def test_render_anchor_table_from_compute_market_anchors_round_trip() -> None:
    # End-to-end: compute MarketAnchor from synthetic OHLC history, then
    # render. Verifies the table renderer accepts the canonical anchor
    # shape without any massaging.
    from datetime import timedelta

    today = date(2026, 5, 11)
    base = date(2026, 4, 1)
    rows = [
        OHLCRow(
            trading_date=base + timedelta(days=i),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("95"),
            close=Decimal("100") + Decimal(str(i * 0.1)),
            volume=Decimal("1000"),
        )
        for i in range(30)
    ]
    anchors = compute_market_anchors({"AAPL": rows}, today=today)
    assert len(anchors) == 1
    out = render_anchor_table(anchors)
    assert "| AAPL |" in out
