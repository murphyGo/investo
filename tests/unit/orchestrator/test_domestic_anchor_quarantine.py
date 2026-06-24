"""u109 domestic anchor trust gate tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from investo.briefing.disclaimer import DISCLAIMER
from investo.models import Briefing, NormalizedItem, SourceOutcome
from investo.orchestrator.domestic_anchor_quarantine import (
    candidate_from_item,
    classify_domestic_anchor_candidate,
    domestic_anchor_verdicts,
    normalize_domestic_anchor_symbol,
    trusted_domestic_price_items,
)
from investo.orchestrator.pipeline import _build_quality_snapshot

_TARGET = date(2026, 5, 22)
_TS = datetime(2026, 5, 22, 6, 30, tzinfo=UTC)


def _item(
    ticker: str,
    close: str,
    *,
    source: str = "stooq-kr-market",
    pct: str | None = "1.25",
    published_at: datetime = _TS,
) -> NormalizedItem:
    metadata: dict[str, str] = {"ticker": ticker, "close": close}
    if pct is not None:
        metadata["pct_change"] = pct
    return NormalizedItem(
        source_name=source,
        category="price",
        title=f"{ticker} {close}",
        published_at=published_at,
        raw_metadata=metadata,
    )


def test_normalize_domestic_anchor_symbol_registry() -> None:
    assert normalize_domestic_anchor_symbol("KOSPI") == "^KOSPI"
    assert normalize_domestic_anchor_symbol("코스닥") == "^KOSDAQ"
    assert normalize_domestic_anchor_symbol("USD/KRW") == "KRW=X"
    assert normalize_domestic_anchor_symbol("005930") == "005930.KS"
    assert normalize_domestic_anchor_symbol("SK하이닉스") == "000660.KS"
    assert normalize_domestic_anchor_symbol("AAPL") is None


def test_classifies_trusted_stooq_index_candidate() -> None:
    candidate = candidate_from_item(_item("^KOSPI", "2650.50"))
    assert candidate is not None

    trust = classify_domestic_anchor_candidate(candidate, target_date=_TARGET)

    assert trust == "trusted"
    assert candidate.close == Decimal("2650.50")


def test_plausibility_boundaries_are_inclusive() -> None:
    verdicts = domestic_anchor_verdicts(
        [
            _item("^KOSPI", "1000", pct="30.0"),
            _item("^KOSDAQ", "3000", pct="-30.0"),
            _item("KRW=X", "500", pct="20.0"),
        ],
        target_date=_TARGET,
    )

    assert [verdict.trust for verdict in verdicts] == ["trusted", "trusted", "trusted"]


def test_out_of_band_or_unparseable_values_are_implausible() -> None:
    verdicts = domestic_anchor_verdicts(
        [
            _item("^KOSPI", "999.99"),
            _item("^KOSDAQ", "bad"),
            _item("KRW=X", "1500", pct="21.0"),
        ],
        target_date=_TARGET,
    )

    assert [verdict.trust for verdict in verdicts] == [
        "implausible",
        "implausible",
        "implausible",
    ]


def test_wrong_source_and_bad_source_outcome_are_not_trusted() -> None:
    wrong_source = _item("^KOSPI", "2650.50", source="fsc-krx-stock-price")
    bad_outcome = _item("^KOSDAQ", "870.25")

    verdicts = domestic_anchor_verdicts(
        [wrong_source, bad_outcome],
        target_date=_TARGET,
        source_outcomes=(SourceOutcome.zero("stooq-kr-market", "price"),),
    )

    assert [verdict.trust for verdict in verdicts] == [
        "provenance_missing",
        "provenance_missing",
    ]


def test_stale_candidate_is_withheld() -> None:
    old = _item("^KOSPI", "2650.50", published_at=datetime(2026, 5, 21, 6, 30, tzinfo=UTC))

    (verdict,) = domestic_anchor_verdicts([old], target_date=_TARGET)

    assert verdict.trust == "stale"


def test_large_cap_source_contract() -> None:
    samsung = _item("005930", "72000", source="fsc-krx-stock-price", pct="2.0")
    sk_hynix = _item("000660", "185000", source="fsc-krx-stock-price", pct="-1.0")

    verdicts = domestic_anchor_verdicts([samsung, sk_hynix], target_date=_TARGET)

    assert [verdict.candidate.symbol for verdict in verdicts] == ["005930.KS", "000660.KS"]
    assert [verdict.trust for verdict in verdicts] == ["trusted", "trusted"]


def test_trusted_domestic_price_items_filters_only_registry_failures() -> None:
    items = [
        _item("^KOSPI", "999.99"),
        _item("^KOSDAQ", "870.25"),
        _item("AAPL", "305.10", source="stooq-price"),
    ]

    out = trusted_domestic_price_items(items, target_date=_TARGET)

    assert [item.raw_metadata["ticker"] for item in out] == ["^KOSDAQ", "AAPL"]


def test_quality_snapshot_records_domestic_anchor_withholding() -> None:
    briefing = Briefing(
        target_date=_TARGET,
        market_summary="summary",
        key_issues="issues",
        sector_flow="sector",
        indicators_events="events",
        notable_tickers="tickers",
        today_watch="watch",
        disclaimer=DISCLAIMER,
        rendered_markdown="# 국내\n\n## ① 요약\n본문\n\n" + DISCLAIMER,
    )

    snapshot = _build_quality_snapshot(
        briefings={"domestic-equity": briefing},
        published_segments=("domestic-equity",),
        items=[_item("^KOSPI", "999.99"), _item("^KOSDAQ", "870.25")],
        source_outcomes=(),
    )

    assert snapshot.domestic_anchor_withheld_count == 1
    assert snapshot.domestic_anchor_withheld_reasons == ("implausible",)
