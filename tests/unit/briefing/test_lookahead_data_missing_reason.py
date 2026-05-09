"""u43 — ``LOOKAHEAD_DATA_MISSING`` coverage reason code.

Pins the trigger conditions from the u43 plan (Step 9):

* Fires when (a) ≥ 1 lookahead-aware adapter was attempted for the
  segment **and** (b) zero forward-scheduled items were routed.
* Does not fire when no lookahead-aware adapter was attempted (the
  anti-regression guard — readers on a segment with no lookahead
  surface must not see a permanent "예정 일정 데이터 미확보" tag).
* Does not fire when ≥ 1 forward-scheduled item is present.
"""

from __future__ import annotations

from datetime import UTC, datetime

from investo.briefing.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    LOOKAHEAD_AWARE_SOURCES,
    US_EQUITY,
    build_segment_coverage,
)
from investo.models import NormalizedItem, SourceOutcome


def _item(
    source_name: str,
    title: str,
    *,
    category: str = "news",
    scheduled_at: datetime | None = None,
) -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name,
        category=category,  # type: ignore[arg-type]
        title=title,
        published_at=datetime(2026, 5, 10, 12, 0, tzinfo=UTC),
        scheduled_at=scheduled_at,
    )


def test_emits_when_lookahead_adapter_attempted_and_zero_forward_items() -> None:
    # us-equity has fomc-calendar in LOOKAHEAD_AWARE_SOURCES. Its
    # outcome is recorded (status doesn't matter — attempted = present
    # in source_outcomes), and no item carries scheduled_at.
    items = [
        _item("yfinance-price", "S&P 500 close", category="price"),
        _item("cnbc-top-news", "Fed officials speak"),
        _item("fomc-rss", "Federal Reserve issues FOMC statement", category="calendar"),
    ]
    outcomes = (
        SourceOutcome.ok("yfinance-price", "price", item_count=1),
        SourceOutcome.ok("cnbc-top-news", "news", item_count=1),
        SourceOutcome.ok("fomc-rss", "calendar", item_count=1),
        SourceOutcome.zero("fomc-calendar", "calendar"),
    )

    coverage = build_segment_coverage(US_EQUITY, items, source_outcomes=outcomes)

    assert "LOOKAHEAD_DATA_MISSING" in coverage.reason_codes


def test_does_not_emit_when_no_lookahead_adapter_attempted() -> None:
    # crypto has no entry in LOOKAHEAD_AWARE_SOURCES at u43 landing
    # time (fomc-calendar is us-equity-only; nasdaq-earnings is us-only).
    # Even with zero forward items, the reason must NOT fire — readers
    # on a segment without any lookahead-aware adapter should not see
    # a permanent flag.
    items = [
        _item("coingecko-price", "BTC $42,000", category="price"),
        _item("theblock-crypto", "ETH staking discussion"),
    ]
    outcomes = (
        SourceOutcome.ok("coingecko-price", "price", item_count=1),
        SourceOutcome.ok("theblock-crypto", "news", item_count=1),
    )

    coverage = build_segment_coverage(CRYPTO, items, source_outcomes=outcomes)

    assert "LOOKAHEAD_DATA_MISSING" not in coverage.reason_codes


def test_does_not_emit_when_forward_item_present() -> None:
    # us-equity with a scheduled FOMC event present — no missing flag.
    items = [
        _item("yfinance-price", "S&P 500 close", category="price"),
        _item("cnbc-top-news", "Fed officials speak"),
        _item(
            "fomc-calendar",
            "2026-05-20 — FOMC Minutes",
            category="calendar",
            scheduled_at=datetime(2026, 5, 20, 0, 0, tzinfo=UTC),
        ),
    ]
    outcomes = (
        SourceOutcome.ok("yfinance-price", "price", item_count=1),
        SourceOutcome.ok("cnbc-top-news", "news", item_count=1),
        SourceOutcome.ok("fomc-calendar", "calendar", item_count=1),
    )

    coverage = build_segment_coverage(US_EQUITY, items, source_outcomes=outcomes)

    assert "LOOKAHEAD_DATA_MISSING" not in coverage.reason_codes


def test_does_not_emit_on_failed_lookahead_adapter_alone_when_no_other_signal() -> None:
    # Fail-only is still "attempted" — the operator should know the
    # forward calendar is dark. Reason fires.
    items = [
        _item("yfinance-price", "S&P 500 close", category="price"),
        _item("cnbc-top-news", "Fed officials speak"),
    ]
    outcomes = (
        SourceOutcome.ok("yfinance-price", "price", item_count=1),
        SourceOutcome.ok("cnbc-top-news", "news", item_count=1),
        SourceOutcome.from_failure("fomc-calendar", "calendar", message="HTTP 503", transient=True),
    )

    coverage = build_segment_coverage(US_EQUITY, items, source_outcomes=outcomes)

    assert "LOOKAHEAD_DATA_MISSING" in coverage.reason_codes
    # Co-existing SOURCE_FAILED must also fire — orthogonal signals.
    assert "SOURCE_FAILED" in coverage.reason_codes


def test_lookahead_aware_sources_registry_includes_fomc_calendar() -> None:
    # Anti-regression: u43 introduced fomc-calendar; it must be in
    # the registry so the trigger fires on its segment.
    assert "fomc-calendar" in LOOKAHEAD_AWARE_SOURCES
    # Anti-regression: u35 nasdaq-earnings-calendar already had the
    # forward path; keep the entry stable.
    assert "nasdaq-earnings-calendar" in LOOKAHEAD_AWARE_SOURCES


def test_reason_code_does_not_fire_on_domestic_equity() -> None:
    # domestic-equity has no lookahead-aware adapter at u43 landing.
    # KRX option-expiry was deferred (R10 — no public non-scraping
    # path). Until that lands, domestic readers must not see the
    # missing-data flag.
    items = [
        _item("yonhap-market", "코스피 7,000"),
        _item("fsc-krx-index-price", "KOSPI 2,730", category="price"),
        _item("dart-disclosure", "삼성전자 주요 사항", category="news"),
    ]
    outcomes = (
        SourceOutcome.ok("yonhap-market", "news", item_count=1),
        SourceOutcome.ok("fsc-krx-index-price", "price", item_count=1),
        SourceOutcome.ok("dart-disclosure", "news", item_count=1),
    )

    coverage = build_segment_coverage(DOMESTIC_EQUITY, items, source_outcomes=outcomes)

    assert "LOOKAHEAD_DATA_MISSING" not in coverage.reason_codes


def test_label_renders_korean_text_for_reason_code() -> None:
    items = [_item("yfinance-price", "x", category="price")]
    outcomes = (
        SourceOutcome.ok("yfinance-price", "price", item_count=1),
        SourceOutcome.zero("fomc-calendar", "calendar"),
    )
    coverage = build_segment_coverage(US_EQUITY, items, source_outcomes=outcomes)

    assert "LOOKAHEAD_DATA_MISSING" in coverage.reason_codes
    assert "예정 일정 데이터 미확보" in coverage.reason_labels
