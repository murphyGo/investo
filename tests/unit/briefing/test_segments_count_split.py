"""u54 — 5-tuple count split on ``SegmentCoverage`` (AC-1).

The reader-facing badge surfaces ``수집 대상 / 성공 / 0건 / 실패 / 본문
사용`` so the audience can distinguish "we tried N adapters" from "N
adapters returned items" from "N items survived to the body". These
tests pin the derivation invariant: ``targeted = succeeded + zero +
failed`` (plus any future ``excluded`` slot) and ``body_used_count ≤
succeeded_count`` (you cannot cite an item you did not collect).
"""

from __future__ import annotations

from datetime import UTC, datetime

from investo.briefing.segments import US_EQUITY, build_segment_coverage
from investo.models import NormalizedItem, SourceOutcome


def _item(source: str, category: str = "price") -> NormalizedItem:
    return NormalizedItem(
        source_name=source,
        category=category,  # type: ignore[arg-type]
        published_at=datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
        url=f"https://example.invalid/{source}",
        title=f"{source} item",
    )


def test_five_tuple_counts_sum_to_targeted() -> None:
    coverage = build_segment_coverage(
        US_EQUITY,
        [_item("yfinance-price"), _item("yahoo-finance-news", "news")],
        source_outcomes=(
            SourceOutcome.ok("yfinance-price", "price", 3),
            SourceOutcome.zero("nasdaq-stocks-news", "news"),
            SourceOutcome.from_failure(
                "cnbc-top-news",
                "news",
                message="boom",
                transient=True,
            ),
            SourceOutcome.ok("yahoo-finance-news", "news", 5),
        ),
    )
    assert coverage.targeted_count == 4
    assert coverage.succeeded_count == 2
    assert coverage.zero_count == 1
    assert coverage.failed_count == 1
    assert (
        coverage.targeted_count
        == coverage.succeeded_count + coverage.zero_count + coverage.failed_count
    )


def test_body_used_count_defaults_to_zero_when_omitted() -> None:
    coverage = build_segment_coverage(
        US_EQUITY,
        [_item("yfinance-price")],
        source_outcomes=(SourceOutcome.ok("yfinance-price", "price", 1),),
    )
    assert coverage.body_used_count == 0
    assert coverage.body_used_count <= coverage.succeeded_count


def test_body_used_count_passed_through() -> None:
    coverage = build_segment_coverage(
        US_EQUITY,
        [_item("yfinance-price"), _item("yahoo-finance-news", "news")],
        source_outcomes=(
            SourceOutcome.ok("yfinance-price", "price", 1),
            SourceOutcome.ok("yahoo-finance-news", "news", 1),
        ),
        body_used_count=2,
    )
    assert coverage.body_used_count == 2
    assert coverage.body_used_count <= coverage.succeeded_count


def test_body_used_count_negative_clamped_to_zero() -> None:
    coverage = build_segment_coverage(
        US_EQUITY,
        [_item("yfinance-price")],
        source_outcomes=(SourceOutcome.ok("yfinance-price", "price", 1),),
        body_used_count=-3,
    )
    assert coverage.body_used_count == 0


def test_legacy_caller_no_outcomes_yields_zero_counts() -> None:
    """Legacy callers that supply only ``items`` get zeros across the
    new count fields — backward compat for older test fixtures."""
    coverage = build_segment_coverage(US_EQUITY, [_item("yfinance-price")])
    assert coverage.targeted_count == 0
    assert coverage.succeeded_count == 0
    assert coverage.zero_count == 0
    assert coverage.failed_count == 0
    assert coverage.body_used_count == 0


def test_count_split_all_failed() -> None:
    coverage = build_segment_coverage(
        US_EQUITY,
        [],
        source_outcomes=(
            SourceOutcome.from_failure("yfinance-price", "price", message="x", transient=True),
            SourceOutcome.from_failure("cnbc-top-news", "news", message="x", transient=True),
        ),
    )
    assert coverage.targeted_count == 2
    assert coverage.failed_count == 2
    assert coverage.succeeded_count == 0
