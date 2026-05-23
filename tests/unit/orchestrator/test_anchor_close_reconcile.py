"""P1-2 — anchor header-table close reconciliation (option B).

Regression coverage for the orchestrator helpers that align the
``MarketAnchor.close`` displayed in the header table with the
price-snapshot close the body prose + trace footer cite:

* ``_snapshot_close_by_ticker`` — extracts ``ticker -> Decimal(close)``
  from ``category == "price"`` items only.
* ``_reconcile_anchor_closes`` — overrides display close beyond tolerance,
  preserves derived fields, falls back when no snapshot exists.

Module boundary: orchestrator is allowed to import sources/briefing/
publisher; these helpers live in the orchestrator and only read shared
models.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from investo.briefing.market_anchor import MarketAnchor
from investo.briefing.segments import CRYPTO, US_EQUITY
from investo.models import NormalizedItem
from investo.orchestrator.pipeline import (
    _reconcile_anchor_closes,
    _snapshot_close_by_ticker,
)

_TS = datetime(2026, 5, 22, 21, 0, tzinfo=UTC)


def _price_item(ticker: str, close: str) -> NormalizedItem:
    return NormalizedItem(
        source_name="yfinance",
        category="price",
        title=f"{ticker} {close}",
        published_at=_TS,
        raw_metadata={"ticker": ticker, "close": close},
    )


def _anchor(ticker: str, close: str, **overrides: object) -> MarketAnchor:
    base: dict[str, object] = {
        "ticker": ticker,
        "close": Decimal(close),
        "prev_close": Decimal("300.00"),
        "pct": Decimal("1.50"),
        "is_ath": True,
        "pct_from_52w_high": Decimal("-0.50"),
        "pct_from_52w_low": Decimal("28.90"),
        "mtd_pct": Decimal("6.10"),
        "ytd_pct": Decimal("13.08"),
        "volume_z_score": Decimal("2.1"),
    }
    base.update(overrides)
    return MarketAnchor(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _snapshot_close_by_ticker
# ---------------------------------------------------------------------------


def test_snapshot_close_extracts_price_items() -> None:
    items = [
        _price_item("AAPL", "305.10"),
        _price_item("^GSPC", "5820.40"),
    ]
    out = _snapshot_close_by_ticker(items)
    assert out == {"AAPL": Decimal("305.10"), "^GSPC": Decimal("5820.40")}


def test_snapshot_close_ignores_non_price_categories() -> None:
    news = NormalizedItem(
        source_name="fomc-rss",
        category="news",
        title="headline",
        published_at=_TS,
        raw_metadata={"ticker": "AAPL", "close": "999.99"},
    )
    out = _snapshot_close_by_ticker([news])
    assert out == {}


def test_snapshot_close_skips_unparseable_or_missing() -> None:
    items = [
        NormalizedItem(
            source_name="yfinance",
            category="price",
            title="bad",
            published_at=_TS,
            raw_metadata={"ticker": "AAPL", "close": "n/a"},
        ),
        NormalizedItem(
            source_name="yfinance",
            category="price",
            title="no-close",
            published_at=_TS,
            raw_metadata={"ticker": "MSFT"},
        ),
    ]
    assert _snapshot_close_by_ticker(items) == {}


def test_snapshot_close_last_writer_wins() -> None:
    items = [_price_item("AAPL", "304.99"), _price_item("AAPL", "305.10")]
    assert _snapshot_close_by_ticker(items) == {"AAPL": Decimal("305.10")}


# ---------------------------------------------------------------------------
# _reconcile_anchor_closes
# ---------------------------------------------------------------------------


def test_reconcile_overrides_display_close_beyond_tolerance() -> None:
    anchors = {US_EQUITY: (_anchor("AAPL", "304.99"),)}
    snapshot = {"AAPL": Decimal("305.10")}
    out = _reconcile_anchor_closes(anchors, snapshot)
    (reconciled,) = out[US_EQUITY]
    assert reconciled.close == Decimal("305.10")


def test_reconcile_preserves_derived_fields() -> None:
    original = _anchor("AAPL", "304.99")
    out = _reconcile_anchor_closes({US_EQUITY: (original,)}, {"AAPL": Decimal("305.10")})
    (reconciled,) = out[US_EQUITY]
    # Display close swapped, but every history-derived field is untouched.
    assert reconciled.close == Decimal("305.10")
    assert reconciled.is_ath == original.is_ath
    assert reconciled.pct == original.pct
    assert reconciled.prev_close == original.prev_close
    assert reconciled.pct_from_52w_high == original.pct_from_52w_high
    assert reconciled.pct_from_52w_low == original.pct_from_52w_low
    assert reconciled.mtd_pct == original.mtd_pct
    assert reconciled.ytd_pct == original.ytd_pct
    assert reconciled.volume_z_score == original.volume_z_score


def test_reconcile_falls_back_when_no_snapshot() -> None:
    original = _anchor("NVDA", "950.00")
    out = _reconcile_anchor_closes({US_EQUITY: (original,)}, {})
    (passthrough,) = out[US_EQUITY]
    assert passthrough is original
    assert passthrough.close == Decimal("950.00")


def test_reconcile_within_abs_tolerance_passes_through() -> None:
    original = _anchor("AAPL", "305.00")
    # 0.005 < $0.01 abs tolerance → no swap, same instance returned.
    out = _reconcile_anchor_closes({US_EQUITY: (original,)}, {"AAPL": Decimal("305.005")})
    (passthrough,) = out[US_EQUITY]
    assert passthrough is original


def test_reconcile_rel_tolerance_triggers_on_low_price() -> None:
    # Low-priced ticker: abs diff 0.008 ≤ $0.01 abs floor, but
    # 0.008 / 5.00 = 0.16 % > 0.05 % rel tolerance → override fires
    # (OR semantics: either threshold exceeded counts as different).
    original = _anchor("PENNY", "5.000")
    out = _reconcile_anchor_closes({CRYPTO: (original,)}, {"PENNY": Decimal("5.008")})
    (reconciled,) = out[CRYPTO]
    assert reconciled.close == Decimal("5.008")


def test_reconcile_large_abs_diff_always_overrides() -> None:
    # 50000 vs 50015: abs diff 15 > $0.01 abs floor → override under OR
    # semantics even though rel diff (0.03 %) is below the rel floor.
    original = _anchor("BTC-USD", "50000.00")
    out = _reconcile_anchor_closes({CRYPTO: (original,)}, {"BTC-USD": Decimal("50015.00")})
    (reconciled,) = out[CRYPTO]
    assert reconciled.close == Decimal("50015.00")


def test_reconcile_index_ticker_override() -> None:
    # Index uses the same ticker vocabulary (^GSPC) as the snapshot key.
    anchors = {US_EQUITY: (_anchor("^GSPC", "5818.00"),)}
    out = _reconcile_anchor_closes(anchors, {"^GSPC": Decimal("5820.40")})
    (reconciled,) = out[US_EQUITY]
    assert reconciled.close == Decimal("5820.40")
