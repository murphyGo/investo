"""Deterministic domestic anchor trust gate for u109."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final, Literal

from investo.briefing.quality_eval import iter_archive_files
from investo.models import NormalizedItem, SourceOutcome
from investo.models.segments import DOMESTIC_EQUITY

DomesticAnchorTrust = Literal[
    "trusted",
    "unavailable",
    "stale",
    "implausible",
    "discontinuous",
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
    "discontinuous",
    "trusted",
)
_PREVIOUS_ANCHOR_LOOKBACK_DAYS: Final[int] = 7
_DISCONTINUITY_THRESHOLDS: Final[dict[str, Decimal]] = {
    "^KOSPI": Decimal("0.15"),
    "^KOSDAQ": Decimal("0.15"),
    "KRW=X": Decimal("0.15"),
    "005930.KS": Decimal("0.30"),
    "000660.KS": Decimal("0.30"),
}
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
    previous_close: Decimal | None = None,
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
    if _is_discontinuous(
        symbol=candidate.symbol,
        candidate_close=candidate.close,
        previous_close=previous_close,
    ):
        return "discontinuous"
    return "trusted"


def domestic_anchor_verdicts(
    items: Sequence[NormalizedItem],
    *,
    target_date: date | None = None,
    source_outcomes: Sequence[SourceOutcome] = (),
    previous_closes: Mapping[str, Decimal] | None = None,
) -> tuple[DomesticAnchorVerdict, ...]:
    """Return deterministic u109 verdicts for in-scope domestic price items."""

    resolved_previous_closes = previous_closes or {}
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
                    previous_close=resolved_previous_closes.get(candidate.symbol),
                ),
            )
        )
    return tuple(verdicts)


def trusted_domestic_price_items(
    items: Sequence[NormalizedItem],
    *,
    target_date: date | None = None,
    source_outcomes: Sequence[SourceOutcome] = (),
    previous_closes: Mapping[str, Decimal] | None = None,
) -> tuple[NormalizedItem, ...]:
    """Filter only u109-trusted domestic registry price rows; pass others through."""

    resolved_previous_closes = previous_closes or {}
    verdict_by_identity = {
        id(item): verdict
        for item, verdict in (
            (
                item,
                _verdict_for_item(
                    item,
                    target_date,
                    source_outcomes,
                    resolved_previous_closes,
                ),
            )
            for item in items
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
    previous_closes: Mapping[str, Decimal],
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
            previous_close=previous_closes.get(candidate.symbol),
        ),
    )


def load_previous_domestic_anchor_closes(
    archive_root: Path,
    target_date: date,
    *,
    lookback_days: int = _PREVIOUS_ANCHOR_LOOKBACK_DAYS,
) -> dict[str, Decimal]:
    """Load newest published domestic closes inside a calendar-day window.

    Reuses the quality-history archive iterator, which includes weekend
    publications, then reads only domestic documents selected inside the
    exact prior calendar-day window.
    """

    if lookback_days <= 0:
        return {}
    domestic_root = archive_root / DOMESTIC_EQUITY
    archive_paths = sorted(
        (
            path
            for path in iter_archive_files(
                archive_root,
                today=target_date - timedelta(days=1),
                window_days=lookback_days,
            )
            if path.is_relative_to(domestic_root)
        ),
        key=lambda path: path.stem,
        reverse=True,
    )
    previous_closes: dict[str, Decimal] = {}
    for path in archive_paths:
        try:
            markdown = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for symbol, close in _published_anchor_closes(markdown).items():
            previous_closes.setdefault(symbol, close)
        if len(previous_closes) == len(_DISCONTINUITY_THRESHOLDS):
            break
    return previous_closes


def _published_anchor_closes(markdown: str) -> dict[str, Decimal]:
    """Extract canonical symbol/close pairs from published Markdown tables."""

    closes: dict[str, Decimal] = {}
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [cell.strip() for cell in line[1:-1].split("|")]
        if len(cells) < 2:
            continue
        symbol = normalize_domestic_anchor_symbol(cells[0])
        if symbol is None or symbol in closes:
            continue
        try:
            close = Decimal(cells[1].replace(",", ""))
        except (InvalidOperation, ValueError):
            continue
        if not close.is_finite() or close <= 0:
            continue
        closes[symbol] = close
    return closes


def _is_discontinuous(
    *,
    symbol: str,
    candidate_close: Decimal,
    previous_close: Decimal | None,
) -> bool:
    if previous_close is None or not previous_close.is_finite() or previous_close <= 0:
        return False
    threshold = _DISCONTINUITY_THRESHOLDS[symbol]
    return abs(candidate_close / previous_close - Decimal(1)) > threshold


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
            parsed = Decimal(str(value).replace(",", "").strip())
        except (InvalidOperation, ValueError):
            return None, True
        if not parsed.is_finite():
            return None, True
        return parsed, False
    return None, False


__all__ = [
    "DomesticAnchorCandidate",
    "DomesticAnchorTrust",
    "DomesticAnchorVerdict",
    "candidate_from_item",
    "classify_domestic_anchor_candidate",
    "domestic_anchor_verdicts",
    "load_previous_domestic_anchor_closes",
    "normalize_domestic_anchor_symbol",
    "trusted_domestic_price_items",
]
