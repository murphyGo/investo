"""u54 — Core-source staleness override on severity (AC-3).

A core price source can be ``ok`` with items but emit *yesterday's*
data when the wall clock has moved on (yfinance returning Fri close
during a Mon KST run, CoinGecko stuck after an upstream outage). The
staleness check compares each core source's ``latest_item_at`` to the
segment's window floor — if every populated timestamp is out of
window and none are fresh, severity is forced ≥ ``limited`` with a
``CORE_STALE`` reason code.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from investo.briefing.segments import (
    CRYPTO,
    US_EQUITY,
    build_segment_coverage,
    core_staleness_window,
)
from investo.models import NormalizedItem, SourceOutcome

_NOW = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)


def _item(source: str, category: str = "price") -> NormalizedItem:
    return NormalizedItem(
        source_name=source,
        category=category,  # type: ignore[arg-type]
        published_at=datetime(2026, 5, 11, 8, 0, tzinfo=UTC),
        url=f"https://example.invalid/{source}",
        title=f"{source} item",
    )


def _ok(source: str, latest_item_at: datetime | None) -> SourceOutcome:
    return SourceOutcome.ok("X", "price", 3).__class__(  # type: ignore[call-arg]
        source_name=source,
        category="price",
        status="ok",
        item_count=3,
        tier="B",
        latest_item_at=latest_item_at,
    )


def test_fresh_us_equity_core_within_window_stays_normal() -> None:
    """KST Monday-morning yfinance with Fri close → within 30h window."""
    # Fri 16:00 ET == Fri 20:00 UTC; Mon morning KST cron = Sun 22:00 ET = Mon 02:00 UTC
    # Use a 24h-old item against a 30h window → fresh.
    fresh = _NOW - timedelta(hours=24)
    coverage = build_segment_coverage(
        US_EQUITY,
        [
            _item("yfinance-price"),
            _item("stooq-price"),
            _item("yahoo-finance-news", "news"),
        ],
        source_outcomes=(
            _ok("yfinance-price", fresh),
            _ok("stooq-price", fresh),
            _ok("yahoo-finance-news", None),
        ),
        now_utc=_NOW,
    )
    assert coverage.status == "normal"
    assert "CORE_STALE" not in coverage.reason_codes


def test_stale_us_equity_core_outside_window_downgrades_to_limited() -> None:
    stale = _NOW - timedelta(hours=72)  # 72h > 30h window
    coverage = build_segment_coverage(
        US_EQUITY,
        [_item("yfinance-price"), _item("yahoo-finance-news", "news")],
        source_outcomes=(
            _ok("yfinance-price", stale),
            _ok("stooq-price", stale),
            _ok("yahoo-finance-news", None),
        ),
        now_utc=_NOW,
    )
    assert coverage.status == "limited"
    assert "CORE_STALE" in coverage.reason_codes


def test_crypto_short_window_six_hours_strict() -> None:
    stale = _NOW - timedelta(hours=8)  # 8h > 6h window
    coverage = build_segment_coverage(
        CRYPTO,
        [_item("coingecko-price"), _item("theblock-crypto", "news")],
        source_outcomes=(
            _ok("coingecko-price", stale),
            _ok("stooq-price", stale),
            _ok("theblock-crypto", None),
        ),
        now_utc=_NOW,
    )
    assert coverage.status == "limited"
    assert "CORE_STALE" in coverage.reason_codes


def test_legacy_caller_without_latest_item_at_skips_check() -> None:
    """``latest_item_at=None`` on every core source → no staleness signal."""
    coverage = build_segment_coverage(
        US_EQUITY,
        [
            _item("yfinance-price"),
            _item("stooq-price"),
            _item("yahoo-finance-news", "news"),
        ],
        source_outcomes=(
            _ok("yfinance-price", None),
            _ok("stooq-price", None),
            _ok("yahoo-finance-news", None),
        ),
        now_utc=_NOW,
    )
    assert coverage.status == "normal"
    assert "CORE_STALE" not in coverage.reason_codes


def test_now_utc_omitted_disables_staleness_path() -> None:
    """No ``now_utc`` argument → staleness path skipped even with
    populated timestamps (legacy callers stay unaffected)."""
    stale = datetime(2020, 1, 1, tzinfo=UTC)
    coverage = build_segment_coverage(
        US_EQUITY,
        [
            _item("yfinance-price"),
            _item("stooq-price"),
            _item("yahoo-finance-news", "news"),
        ],
        source_outcomes=(
            _ok("yfinance-price", stale),
            _ok("stooq-price", stale),
            _ok("yahoo-finance-news", None),
        ),
        # now_utc not supplied
    )
    assert coverage.status == "normal"
    assert "CORE_STALE" not in coverage.reason_codes


def test_one_core_fresh_other_stale_stays_normal() -> None:
    """At least one fresh core source means we have a current quote
    → no staleness downgrade."""
    fresh = _NOW - timedelta(hours=2)
    stale = _NOW - timedelta(hours=48)
    coverage = build_segment_coverage(
        US_EQUITY,
        [
            _item("yfinance-price"),
            _item("stooq-price"),
            _item("yahoo-finance-news", "news"),
        ],
        source_outcomes=(
            _ok("yfinance-price", fresh),
            _ok("stooq-price", stale),
            _ok("yahoo-finance-news", None),
        ),
        now_utc=_NOW,
    )
    assert coverage.status == "normal"
    assert "CORE_STALE" not in coverage.reason_codes


def test_core_staleness_window_accessor_pinned() -> None:
    assert core_staleness_window(US_EQUITY) == timedelta(hours=30)
    assert core_staleness_window(CRYPTO) == timedelta(hours=6)
