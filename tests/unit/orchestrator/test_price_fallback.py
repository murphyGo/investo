"""u138 same-run Yahoo history fallback contract tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from investo.models import NormalizedItem, SourceOutcome
from investo.models.market_anchor import OHLCRow
from investo.orchestrator.price_fallback import reconcile_yahoo_history_fallback

_TARGET = date(2026, 7, 18)


def _row(
    trading_date: date,
    *,
    open_: Decimal = Decimal("100"),
    high: Decimal = Decimal("110"),
    low: Decimal = Decimal("90"),
    close: Decimal = Decimal("105"),
    volume: Decimal | None = Decimal("1000"),
) -> OHLCRow:
    return OHLCRow(
        trading_date=trading_date,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _direct_item(ticker: str, *, published_at: datetime | None = None) -> NormalizedItem:
    return NormalizedItem(
        source_name="yfinance-price",
        category="price",
        title=f"{ticker} direct",
        published_at=published_at or datetime(2026, 7, 17, 20, 0, tzinfo=UTC),
        raw_metadata={"ticker": ticker, "close": "101.000000"},
    )


def test_direct_snapshot_wins_and_prevents_duplicate_ticker() -> None:
    direct = _direct_item("AAPL")
    outcome = SourceOutcome.ok(
        "yfinance-price",
        "price",
        1,
        tier="A",
        latest_item_at=direct.published_at,
        elapsed_s=0.75,
    )

    reconciled = reconcile_yahoo_history_fallback(
        items=(direct,),
        outcomes=(outcome,),
        history_by_ticker={"AAPL": (_row(date(2026, 7, 17)),)},
        target_date=_TARGET,
    )

    assert reconciled.items == (direct,)
    assert reconciled.outcomes == (outcome,)
    assert reconciled.fallback_count == 0


@pytest.mark.parametrize(
    ("age_days", "accepted"),
    [(0, True), (4, True), (5, False), (-1, False)],
)
def test_fallback_freshness_boundary(age_days: int, accepted: bool) -> None:
    row_date = _TARGET - timedelta(days=age_days)
    reconciled = reconcile_yahoo_history_fallback(
        items=(),
        outcomes=(SourceOutcome.zero("yfinance-price", "price", tier="A"),),
        history_by_ticker={"AAPL": (_row(row_date),)},
        target_date=_TARGET,
    )

    assert bool(reconciled.fallback_count) is accepted
    assert bool(reconciled.items) is accepted
    assert reconciled.outcomes[0].status == ("ok" if accepted else "zero")


def test_future_latest_row_rejects_ticker_instead_of_scanning_back() -> None:
    reconciled = reconcile_yahoo_history_fallback(
        items=(),
        outcomes=(SourceOutcome.zero("yfinance-price", "price", tier="A"),),
        history_by_ticker={
            "AAPL": (
                _row(date(2026, 7, 17)),
                _row(date(2026, 7, 19), close=Decimal("106")),
            )
        },
        target_date=_TARGET,
    )

    assert reconciled.fallback_count == 0
    assert reconciled.items == ()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("open", Decimal("0")),
        ("high", Decimal("-1")),
        ("low", Decimal("NaN")),
        ("close", Decimal("Infinity")),
        ("volume", Decimal("-1")),
        ("volume", Decimal("NaN")),
    ],
)
def test_fallback_rejects_invalid_numeric_rows(field: str, value: Decimal) -> None:
    invalid_row = _row(date(2026, 7, 17)).model_copy(update={field: value})
    reconciled = reconcile_yahoo_history_fallback(
        items=(),
        outcomes=(SourceOutcome.zero("yfinance-price", "price", tier="A"),),
        history_by_ticker={"AAPL": (invalid_row,)},
        target_date=_TARGET,
    )

    assert reconciled.fallback_count == 0
    assert reconciled.items == ()


def test_fallback_emits_public_metadata_provenance_and_core_fact() -> None:
    reconciled = reconcile_yahoo_history_fallback(
        items=(),
        outcomes=(SourceOutcome.zero("yfinance-price", "price", tier="A"),),
        history_by_ticker={
            "^GSPC": (
                _row(date(2026, 7, 16), close=Decimal("6200")),
                _row(
                    date(2026, 7, 17),
                    open_=Decimal("6210"),
                    high=Decimal("6260"),
                    low=Decimal("6190"),
                    close=Decimal("6250"),
                    volume=None,
                ),
            )
        },
        target_date=_TARGET,
    )

    assert reconciled.fallback_count == 1
    item = reconciled.items[0]
    assert item.source_name == "yfinance-price"
    assert item.category == "price"
    assert item.published_at == datetime(2026, 7, 17, 20, 0, tzinfo=UTC)
    assert str(item.url) == "https://finance.yahoo.com/quote/%5EGSPC"
    assert item.raw_metadata == {
        "ticker": "^GSPC",
        "open": "6210.000000",
        "high": "6260.000000",
        "low": "6190.000000",
        "close": "6250.000000",
        "volume": "",
        "prev_close": "6200.000000",
        "provenance": "query2-history-fallback",
        "history_range": "1y",
        "core_fact:spx_close": "6250.000000",
    }
    assert item.summary is not None and "V:N/A" in item.summary
    assert "(+0.81%)" in item.title


def test_fallback_rebuilds_one_truthful_outcome_and_preserves_elapsed_time() -> None:
    direct = _direct_item(
        "AAPL",
        published_at=datetime(2026, 7, 18, 1, 0, tzinfo=UTC),
    )
    original = SourceOutcome.ok(
        "yfinance-price",
        "price",
        1,
        tier="A",
        latest_item_at=direct.published_at,
        elapsed_s=1.25,
    )
    duplicate = SourceOutcome.zero("yfinance-price", "price", tier="A")
    sibling = SourceOutcome.ok("other-source", "news", 1, tier="B")

    reconciled = reconcile_yahoo_history_fallback(
        items=(direct,),
        outcomes=(sibling, original, duplicate),
        history_by_ticker={"MSFT": (_row(date(2026, 7, 17)),)},
        target_date=_TARGET,
    )

    yahoo_outcomes = [
        outcome for outcome in reconciled.outcomes if outcome.source_name == "yfinance-price"
    ]
    assert len(yahoo_outcomes) == 1
    final = yahoo_outcomes[0]
    assert final.status == "ok"
    assert final.item_count == 2
    assert final.latest_item_at == direct.published_at
    assert final.elapsed_s == 1.25
    assert final.tier == "A"
    assert reconciled.outcomes[0] is sibling
    assert reconciled.fallback_count == 1
