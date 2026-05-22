"""u54 — Severity decision-tree truth table + enum migration tests.

The 8-row decision tree in ``investo.briefing.segments._resolve_severity``
is the single source of truth for "what severity does this segment get".
These tests pin every row so a future refactor cannot silently change
the policy.

The tests intentionally avoid the routing helpers (``segment_items``,
``segment_source_outcomes``) and call ``build_segment_coverage``
directly with hand-crafted outcomes — that isolates the severity tree
from any incidental routing change in u45 / u53.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from investo.briefing.segments import (
    COVERAGE_REASON_LABELS,
    COVERAGE_STATUS_LABELS,
    CRYPTO,
    DOMESTIC_EQUITY,
    SEGMENT_CORE_SOURCES,
    SEGMENT_CORE_STALENESS_WINDOW,
    SEVERITY_READER_EXPLANATIONS,
    US_EQUITY,
    CoverageStatus,
    build_segment_coverage,
)
from investo.models import NormalizedItem, SourceOutcome


def _item(source: str, category: str = "price") -> NormalizedItem:
    return NormalizedItem(
        source_name=source,
        category=category,  # type: ignore[arg-type]
        published_at=datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
        url=f"https://example.invalid/{source}",
        title=f"{source} item",
    )


def _ok(source: str, category: str = "price", count: int = 5) -> SourceOutcome:
    return SourceOutcome.ok(source, category, count)  # type: ignore[arg-type]


def _zero(source: str, category: str = "price") -> SourceOutcome:
    return SourceOutcome.zero(source, category)  # type: ignore[arg-type]


def _failed(source: str, category: str = "price") -> SourceOutcome:
    return SourceOutcome.from_failure(
        source,
        category,  # type: ignore[arg-type]
        message="boom",
        transient=True,
    )


# ---------------------------------------------------------------------------
# Row 1: all core failed → failed
# ---------------------------------------------------------------------------


def test_us_equity_all_core_failed_yields_failed() -> None:
    """Both yfinance + stooq failed simultaneously → ``failed``."""
    coverage = build_segment_coverage(
        US_EQUITY,
        [_item("yahoo-finance-news", "news"), _item("fomc-rss", "calendar")],
        source_outcomes=(
            _failed("yfinance-price"),
            _failed("stooq-price"),
            _ok("yahoo-finance-news", "news"),
            _ok("fomc-rss", "calendar"),
        ),
    )
    assert coverage.status == "failed"
    assert "ALL_FAILED" in coverage.reason_codes
    assert "CORE_FAILED" in coverage.reason_codes


def test_domestic_single_core_failed_yields_failed() -> None:
    """domestic-equity has 1 core source — its failure is "all core failed"."""
    coverage = build_segment_coverage(
        DOMESTIC_EQUITY,
        [_item("yonhap-market", "news")],
        source_outcomes=(
            _failed("fsc-krx-index-price"),
            _ok("yonhap-market", "news"),
        ),
    )
    assert coverage.status == "failed"


# ---------------------------------------------------------------------------
# Row 2: ≥ 1 core failed (but not all) → limited
# ---------------------------------------------------------------------------


def test_us_equity_one_core_failed_one_ok_yields_limited() -> None:
    """yfinance failed, stooq ok → ``limited`` (degraded but salvageable)."""
    coverage = build_segment_coverage(
        US_EQUITY,
        [
            _item("stooq-price", "price"),
            _item("yahoo-finance-news", "news"),
        ],
        source_outcomes=(
            _failed("yfinance-price"),
            _ok("stooq-price", "price"),
            _ok("yahoo-finance-news", "news"),
        ),
    )
    assert coverage.status == "limited"
    assert "CORE_FAILED" in coverage.reason_codes
    assert "ALL_FAILED" not in coverage.reason_codes


# ---------------------------------------------------------------------------
# Row 3: all core zero (none failed, none ok) → limited
# ---------------------------------------------------------------------------


def test_crypto_all_core_zero_yields_limited() -> None:
    coverage = build_segment_coverage(
        CRYPTO,
        [_item("theblock-crypto", "news")],
        source_outcomes=(
            _zero("coingecko-price"),
            _zero("binance-crypto-market"),
            _ok("theblock-crypto", "news"),
        ),
    )
    assert coverage.status == "limited"
    assert "CORE_ZERO" in coverage.reason_codes


# ---------------------------------------------------------------------------
# Row 4 / 5: core healthy + structural deficit → partial
# ---------------------------------------------------------------------------


def test_core_healthy_missing_news_yields_partial() -> None:
    coverage = build_segment_coverage(
        US_EQUITY,
        [
            _item("yfinance-price", "price"),
            _item("stooq-price", "price"),
            _item("fomc-rss", "calendar"),
            _item("yfinance-price", "price"),
        ],
        source_outcomes=(
            _ok("yfinance-price"),
            _ok("stooq-price"),
            _ok("fomc-rss", "calendar"),
        ),
    )
    assert coverage.status == "partial"
    assert "MISSING_NEWS" in coverage.reason_codes


def test_core_healthy_non_core_failed_stays_normal_with_reason_signal() -> None:
    """A non-core source flake does *not* downgrade status — it only
    surfaces ``SOURCE_FAILED`` as a transparency reason. Intended per
    plan AC-3: only core source failures downgrade severity.
    """
    coverage = build_segment_coverage(
        US_EQUITY,
        [
            _item("yfinance-price", "price"),
            _item("stooq-price", "price"),
            _item("yahoo-finance-news", "news"),
        ],
        source_outcomes=(
            _ok("yfinance-price"),
            _ok("stooq-price"),
            _ok("yahoo-finance-news", "news"),
            _failed("cnbc-top-news", "news"),
        ),
    )
    assert coverage.status == "normal"
    assert "SOURCE_FAILED" in coverage.reason_codes
    assert "CORE_FAILED" not in coverage.reason_codes


# ---------------------------------------------------------------------------
# Row 6: zero items → failed
# ---------------------------------------------------------------------------


def test_zero_items_with_core_registered_yields_failed() -> None:
    coverage = build_segment_coverage(
        US_EQUITY,
        [],
        source_outcomes=(
            _zero("yfinance-price"),
            _zero("stooq-price"),
            _zero("yahoo-finance-news", "news"),
        ),
    )
    assert coverage.status == "failed"


# ---------------------------------------------------------------------------
# Row 7: all healthy → normal
# ---------------------------------------------------------------------------


def test_all_core_ok_meeting_threshold_yields_normal() -> None:
    coverage = build_segment_coverage(
        US_EQUITY,
        [
            _item("yfinance-price", "price"),
            _item("stooq-price", "price"),
            _item("yahoo-finance-news", "news"),
        ],
        source_outcomes=(
            _ok("yfinance-price"),
            _ok("stooq-price"),
            _ok("yahoo-finance-news", "news"),
        ),
    )
    assert coverage.status == "normal"
    assert "CORE_FAILED" not in coverage.reason_codes
    assert "ALL_FAILED" not in coverage.reason_codes


# ---------------------------------------------------------------------------
# Legacy migration: insufficient → failed
# ---------------------------------------------------------------------------


def test_legacy_insufficient_alias_no_longer_accepted() -> None:
    """Static typing prevents the legacy literal from sneaking in.

    The migration is single-PR; this asserts the runtime label map has
    no ``"insufficient"`` key (defense in depth — mypy already catches
    callers).
    """
    assert "insufficient" not in COVERAGE_STATUS_LABELS  # type: ignore[comparison-overlap]
    assert set(COVERAGE_STATUS_LABELS.keys()) == {
        "normal",
        "partial",
        "limited",
        "failed",
    }


def test_legacy_caller_zero_items_no_outcomes_yields_failed() -> None:
    """Legacy callers (no outcomes wired) still get the strictest tier on empty."""
    coverage = build_segment_coverage(DOMESTIC_EQUITY, [])
    assert coverage.status == "failed"
    assert "ZERO_ITEMS" in coverage.reason_codes


# ---------------------------------------------------------------------------
# Label map completeness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["normal", "partial", "limited", "failed"])
def test_status_labels_present_for_every_tier(status: CoverageStatus) -> None:
    assert status in COVERAGE_STATUS_LABELS
    assert COVERAGE_STATUS_LABELS[status]
    assert status in SEVERITY_READER_EXPLANATIONS
    assert SEVERITY_READER_EXPLANATIONS[status]


def test_new_reason_codes_have_korean_labels() -> None:
    for code in ("CORE_FAILED", "CORE_ZERO", "CORE_STALE", "ALL_FAILED"):
        assert code in COVERAGE_REASON_LABELS
        assert COVERAGE_REASON_LABELS[code]  # type: ignore[literal-required]


# ---------------------------------------------------------------------------
# Frozen constants
# ---------------------------------------------------------------------------


def test_segment_core_sources_membership_pinned() -> None:
    """Plan-frozen constants — change here is a deliberate policy shift."""
    assert SEGMENT_CORE_SOURCES[DOMESTIC_EQUITY] == frozenset({"fsc-krx-index-price"})
    assert SEGMENT_CORE_SOURCES[US_EQUITY] == frozenset({"yfinance-price", "stooq-price"})
    assert SEGMENT_CORE_SOURCES[CRYPTO] == frozenset({"coingecko-price", "stooq-price"})


def test_segment_core_staleness_windows_pinned() -> None:
    assert SEGMENT_CORE_STALENESS_WINDOW[DOMESTIC_EQUITY].total_seconds() == 30 * 3600
    assert SEGMENT_CORE_STALENESS_WINDOW[US_EQUITY].total_seconds() == 30 * 3600
    assert SEGMENT_CORE_STALENESS_WINDOW[CRYPTO].total_seconds() == 6 * 3600
