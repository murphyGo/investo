"""u67 — domestic KR anchor synthesis from snapshot items.

``_build_kr_anchors_from_items`` turns ``stooq-kr-market`` price snapshot
items into close-only :class:`MarketAnchor` rows for the domestic anchor
table (Yahoo history cannot supply ^KOSPI / ^KOSDAQ / KRW=X — they 429 on
the GHA IP). Pins:
* one close-only anchor per KR ticker present, in canonical order,
* derived fields stay ``None`` (no history),
* missing / non-KR items contribute nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from investo.models import NormalizedItem
from investo.orchestrator.pipeline import _build_kr_anchors_from_items

_TS = datetime(2026, 5, 22, 6, 30, tzinfo=UTC)


def _kr_item(ticker: str, close: str) -> NormalizedItem:
    return NormalizedItem(
        source_name="stooq-kr-market",
        category="price",
        title=f"{ticker} {close}",
        published_at=_TS,
        raw_metadata={"ticker": ticker, "close": close},
    )


def test_builds_close_only_anchors_in_canonical_order() -> None:
    items = [
        _kr_item("KRW=X", "1518.21"),
        _kr_item("^KOSPI", "2650.50"),
        _kr_item("^KOSDAQ", "870.25"),
    ]
    anchors = _build_kr_anchors_from_items(items)
    assert [a.ticker for a in anchors] == ["^KOSPI", "^KOSDAQ", "KRW=X"]
    kospi = anchors[0]
    assert kospi.close == Decimal("2650.50")
    assert kospi.is_ath is False
    # Close-only: no derived history fields.
    assert kospi.pct is None
    assert kospi.pct_from_52w_high is None
    assert kospi.mtd_pct is None


def test_partial_basket_yields_only_present_tickers() -> None:
    anchors = _build_kr_anchors_from_items([_kr_item("KRW=X", "1518.21")])
    assert [a.ticker for a in anchors] == ["KRW=X"]


def test_non_kr_and_empty_contribute_nothing() -> None:
    us = NormalizedItem(
        source_name="stooq-price",
        category="price",
        title="AAPL 305.10",
        published_at=_TS,
        raw_metadata={"ticker": "AAPL", "close": "305.10"},
    )
    assert _build_kr_anchors_from_items([us]) == ()
    assert _build_kr_anchors_from_items([]) == ()
