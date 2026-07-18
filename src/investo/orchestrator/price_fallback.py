"""Pure same-run Yahoo history fallback reconciliation for u138."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from investo.models import NormalizedItem, SourceOutcome
from investo.models.coverage import SourceTier
from investo.models.market_anchor import OHLCRow
from investo.sources.yfinance import (
    DEFAULT_CRITICAL_TICKERS,
    build_yfinance_price_item,
)

YFINANCE_SOURCE_NAME = "yfinance-price"
_MAX_FALLBACK_AGE_DAYS = 4


@dataclass(frozen=True, slots=True)
class ReconciledPriceCollection:
    """Final price collection consumed by every downstream stage."""

    items: tuple[NormalizedItem, ...]
    outcomes: tuple[SourceOutcome, ...]
    fallback_count: int


def reconcile_yahoo_history_fallback(
    *,
    items: Sequence[NormalizedItem],
    outcomes: Sequence[SourceOutcome],
    history_by_ticker: Mapping[str, Sequence[OHLCRow]],
    target_date: date,
) -> ReconciledPriceCollection:
    """Fill missing critical Yahoo snapshots from fresh same-run history."""

    original_items = tuple(items)
    original_outcomes = tuple(outcomes)
    direct_items = tuple(
        item for item in original_items if item.source_name == YFINANCE_SOURCE_NAME
    )
    seen_tickers = {
        str(item.raw_metadata.get("ticker", "")).strip()
        for item in direct_items
        if str(item.raw_metadata.get("ticker", "")).strip()
    }

    fallback_items: list[NormalizedItem] = []
    for ticker in DEFAULT_CRITICAL_TICKERS:
        if ticker in seen_tickers:
            continue
        rows = history_by_ticker.get(ticker, ())
        if not rows:
            continue
        latest = rows[-1]
        age_days = (target_date - latest.trading_date).days
        if not 0 <= age_days <= _MAX_FALLBACK_AGE_DAYS or not _valid_row(latest):
            continue
        previous_close = _previous_close(rows)
        fallback = build_yfinance_price_item(
            ticker,
            latest,
            previous_close=previous_close,
            provenance="query2-history-fallback",
            history_range="1y",
        )
        if fallback is None:
            continue
        fallback_items.append(fallback)
        seen_tickers.add(ticker)

    if not fallback_items:
        return ReconciledPriceCollection(
            items=original_items,
            outcomes=original_outcomes,
            fallback_count=0,
        )

    final_items = (*original_items, *fallback_items)
    final_yahoo_items = tuple(
        item for item in final_items if item.source_name == YFINANCE_SOURCE_NAME
    )
    original_outcome = next(
        (outcome for outcome in original_outcomes if outcome.source_name == YFINANCE_SOURCE_NAME),
        None,
    )
    tier: SourceTier = original_outcome.tier if original_outcome is not None else "A"
    elapsed_s = original_outcome.elapsed_s if original_outcome is not None else None
    rebuilt_outcome = SourceOutcome.ok(
        YFINANCE_SOURCE_NAME,
        "price",
        len(final_yahoo_items),
        tier=tier,
        latest_item_at=max(item.published_at for item in final_yahoo_items),
        elapsed_s=elapsed_s,
    )
    final_outcomes = _replace_yahoo_outcomes(original_outcomes, rebuilt_outcome)
    return ReconciledPriceCollection(
        items=final_items,
        outcomes=final_outcomes,
        fallback_count=len(fallback_items),
    )


def _valid_row(row: OHLCRow) -> bool:
    prices = (row.open, row.high, row.low, row.close)
    if any(not _finite_positive(value) for value in prices):
        return False
    return row.volume is None or (row.volume.is_finite() and row.volume >= 0)


def _finite_positive(value: Decimal) -> bool:
    return value.is_finite() and value > 0


def _previous_close(rows: Sequence[OHLCRow]) -> Decimal | None:
    if len(rows) < 2:
        return None
    previous = rows[-2].close
    return previous if _finite_positive(previous) else None


def _replace_yahoo_outcomes(
    outcomes: Sequence[SourceOutcome],
    rebuilt: SourceOutcome,
) -> tuple[SourceOutcome, ...]:
    final: list[SourceOutcome] = []
    replaced = False
    for outcome in outcomes:
        if outcome.source_name != YFINANCE_SOURCE_NAME:
            final.append(outcome)
            continue
        if not replaced:
            final.append(rebuilt)
            replaced = True
    if not replaced:
        final.append(rebuilt)
    return tuple(final)


__all__ = [
    "YFINANCE_SOURCE_NAME",
    "ReconciledPriceCollection",
    "reconcile_yahoo_history_fallback",
]
