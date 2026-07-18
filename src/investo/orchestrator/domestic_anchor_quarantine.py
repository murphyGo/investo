"""Deterministic domestic anchor trust gate for u109."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Final, Literal

from investo.models import NormalizedItem, SourceOutcome

DomesticAnchorTrust = Literal[
    "trusted",
    "unavailable",
    "stale",
    "implausible",
    "provenance_missing",
]

_INDEX_FX_SOURCES: Final[dict[str, str]] = {
    "^KOSPI": "yonhap-index-close",
    "^KOSDAQ": "yonhap-index-close",
    "KRW=X": "fred-fx-close",
}
_FRED_FX_SOURCE: Final[str] = "fred-fx-close"
_FRED_FX_MAX_AGE_DAYS: Final[int] = 7
_LARGE_CAP_SOURCE: Final[str] = "fsc-krx-stock-price"
_LARGE_CAP_SYMBOLS: Final[frozenset[str]] = frozenset({"005930.KS", "000660.KS"})
_STATE_ORDER: Final[tuple[DomesticAnchorTrust, ...]] = (
    "unavailable",
    "provenance_missing",
    "stale",
    "implausible",
    "trusted",
)
_BANDS: Final[dict[str, tuple[Decimal, Decimal, Decimal]]] = {
    "^KOSPI": (Decimal("1000"), Decimal("12000"), Decimal("30.0")),
    "^KOSDAQ": (Decimal("300"), Decimal("3000"), Decimal("30.0")),
    "KRW=X": (Decimal("500"), Decimal("2500"), Decimal("20.0")),
    "005930.KS": (Decimal("1000"), Decimal("2000000"), Decimal("30.0")),
    "000660.KS": (Decimal("1000"), Decimal("2000000"), Decimal("30.0")),
}
_ALIASES: Final[dict[str, str]] = {
    "^kospi": "^KOSPI",
    "kospi": "^KOSPI",
    "코스피": "^KOSPI",
    "^kosdaq": "^KOSDAQ",
    "kosdaq": "^KOSDAQ",
    "코스닥": "^KOSDAQ",
    "krw=x": "KRW=X",
    "usd/krw": "KRW=X",
    "원/달러": "KRW=X",
    "달러-원": "KRW=X",
    "005930": "005930.KS",
    "005930.ks": "005930.KS",
    "삼성전자": "005930.KS",
    "000660": "000660.KS",
    "000660.ks": "000660.KS",
    "sk하이닉스": "000660.KS",
}


@dataclass(frozen=True, slots=True)
class DomesticAnchorCandidate:
    symbol: str
    close: Decimal | None
    close_parse_failed: bool
    change_pct: Decimal | None
    change_pct_parse_failed: bool
    source_name: str | None
    observed_at: datetime | None
    raw_ticker: str


@dataclass(frozen=True, slots=True)
class DomesticAnchorVerdict:
    candidate: DomesticAnchorCandidate
    trust: DomesticAnchorTrust


def normalize_domestic_anchor_symbol(value: str | None) -> str | None:
    """Return the bounded u109 registry symbol for ``value``."""

    if value is None:
        return None
    key = value.strip()
    if not key:
        return None
    return _ALIASES.get(key.casefold())


def candidate_from_item(item: NormalizedItem) -> DomesticAnchorCandidate | None:
    """Build a u109 candidate from an existing price item, if in scope."""

    raw_ticker = _metadata_text(item, "ticker") or _metadata_text(item, "index_name")
    symbol = normalize_domestic_anchor_symbol(raw_ticker)
    if symbol is None:
        return None
    close, close_parse_failed = _metadata_decimal(item, "close", "last_price", "price")
    change_pct, change_pct_parse_failed = _metadata_decimal(item, "pct_change", "change_pct", "pct")
    return DomesticAnchorCandidate(
        symbol=symbol,
        close=close,
        close_parse_failed=close_parse_failed,
        change_pct=change_pct,
        change_pct_parse_failed=change_pct_parse_failed,
        source_name=item.source_name or None,
        observed_at=item.published_at,
        raw_ticker=raw_ticker,
    )


def classify_domestic_anchor_candidate(
    candidate: DomesticAnchorCandidate,
    *,
    target_date: date | None = None,
    source_outcomes: Sequence[SourceOutcome] = (),
) -> DomesticAnchorTrust:
    """Classify one domestic anchor candidate using u109 fixed rules."""

    if candidate.close_parse_failed or candidate.change_pct_parse_failed:
        return "implausible"
    if candidate.close is None:
        return "unavailable"
    if candidate.source_name is None:
        return "provenance_missing"
    expected_source = _expected_source(candidate.symbol)
    if candidate.source_name != expected_source:
        return "provenance_missing"
    if normalize_domestic_anchor_symbol(candidate.raw_ticker) != candidate.symbol:
        return "provenance_missing"
    outcome_status = _source_statuses(source_outcomes).get(candidate.source_name)
    if outcome_status in {"failed", "zero"}:
        return "provenance_missing"
    if target_date is not None and not _date_matches(
        candidate.observed_at,
        target_date,
        source_name=candidate.source_name,
    ):
        return "stale"
    min_close, max_close, max_abs_change = _BANDS[candidate.symbol]
    if not min_close <= candidate.close <= max_close:
        return "implausible"
    if candidate.change_pct is not None and abs(candidate.change_pct) > max_abs_change:
        return "implausible"
    return "trusted"


def domestic_anchor_verdicts(
    items: Sequence[NormalizedItem],
    *,
    target_date: date | None = None,
    source_outcomes: Sequence[SourceOutcome] = (),
) -> tuple[DomesticAnchorVerdict, ...]:
    """Return deterministic u109 verdicts for in-scope domestic price items."""

    verdicts: list[DomesticAnchorVerdict] = []
    for item in items:
        if item.category != "price":
            continue
        candidate = candidate_from_item(item)
        if candidate is None:
            continue
        verdicts.append(
            DomesticAnchorVerdict(
                candidate=candidate,
                trust=classify_domestic_anchor_candidate(
                    candidate,
                    target_date=target_date,
                    source_outcomes=source_outcomes,
                ),
            )
        )
    return tuple(verdicts)


def trusted_domestic_price_items(
    items: Sequence[NormalizedItem],
    *,
    target_date: date | None = None,
    source_outcomes: Sequence[SourceOutcome] = (),
) -> tuple[NormalizedItem, ...]:
    """Filter only u109-trusted domestic registry price rows; pass others through."""

    verdict_by_identity = {
        id(item): verdict
        for item, verdict in (
            (item, _verdict_for_item(item, target_date, source_outcomes)) for item in items
        )
        if verdict is not None
    }
    out: list[NormalizedItem] = []
    for item in items:
        verdict = verdict_by_identity.get(id(item))
        if verdict is None or verdict.trust == "trusted":
            out.append(item)
    return tuple(out)


def _verdict_for_item(
    item: NormalizedItem,
    target_date: date | None,
    source_outcomes: Sequence[SourceOutcome],
) -> DomesticAnchorVerdict | None:
    if item.category != "price":
        return None
    candidate = candidate_from_item(item)
    if candidate is None:
        return None
    return DomesticAnchorVerdict(
        candidate=candidate,
        trust=classify_domestic_anchor_candidate(
            candidate,
            target_date=target_date,
            source_outcomes=source_outcomes,
        ),
    )


def _expected_source(symbol: str) -> str:
    if symbol in _INDEX_FX_SOURCES:
        return _INDEX_FX_SOURCES[symbol]
    if symbol in _LARGE_CAP_SYMBOLS:
        return _LARGE_CAP_SOURCE
    return ""


def _source_statuses(outcomes: Sequence[SourceOutcome]) -> Mapping[str, str]:
    return {outcome.source_name: outcome.status for outcome in outcomes}


def _date_matches(
    observed_at: datetime | None,
    target_date: date,
    *,
    source_name: str,
) -> bool:
    if observed_at is None:
        return False
    observed_date = observed_at.astimezone(UTC).date()
    age_days = (target_date - observed_date).days
    if source_name == _FRED_FX_SOURCE:
        return 0 <= age_days <= _FRED_FX_MAX_AGE_DAYS
    return age_days == 0


def _metadata_text(item: NormalizedItem, key: str) -> str:
    value = item.raw_metadata.get(key)
    return value.strip() if isinstance(value, str) else ""


def _metadata_decimal(item: NormalizedItem, *keys: str) -> tuple[Decimal | None, bool]:
    for key in keys:
        value = item.raw_metadata.get(key)
        if value is None:
            continue
        try:
            return Decimal(str(value).replace(",", "").strip()), False
        except (InvalidOperation, ValueError):
            return None, True
    return None, False


__all__ = [
    "DomesticAnchorCandidate",
    "DomesticAnchorTrust",
    "DomesticAnchorVerdict",
    "candidate_from_item",
    "classify_domestic_anchor_candidate",
    "domestic_anchor_verdicts",
    "normalize_domestic_anchor_symbol",
    "trusted_domestic_price_items",
]
