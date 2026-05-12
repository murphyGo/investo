"""u54 — Reader-facing coverage badge rendering (AC-2 / AC-4 first viewport).

The badge surfaces the severity label, the one-line reader explanation
(``SEVERITY_READER_EXPLANATIONS``), and the new 5-tuple count split.
These tests pin the rendered layout so a stylistic regression cannot
silently strip the new signal.
"""

from __future__ import annotations

from datetime import UTC, datetime

from investo.briefing.pipeline import _render_coverage_badge
from investo.briefing.segments import (
    SEVERITY_READER_EXPLANATIONS,
    US_EQUITY,
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


def test_badge_carries_severity_explanation_inline() -> None:
    coverage = build_segment_coverage(
        US_EQUITY,
        [
            _item("yfinance-price"),
            _item("stooq-price"),
            _item("yahoo-finance-news", "news"),
        ],
        source_outcomes=(
            SourceOutcome.ok("yfinance-price", "price", 1),
            SourceOutcome.ok("stooq-price", "price", 1),
            SourceOutcome.ok("yahoo-finance-news", "news", 1),
        ),
    )
    badge = _render_coverage_badge(coverage)
    assert "**데이터 상태**: 정상" in badge
    # u54 — reader explanation appears alongside the label.
    assert SEVERITY_READER_EXPLANATIONS["normal"] in badge


def test_badge_carries_five_tuple_count_split() -> None:
    coverage = build_segment_coverage(
        US_EQUITY,
        [_item("yfinance-price"), _item("yahoo-finance-news", "news")],
        source_outcomes=(
            SourceOutcome.ok("yfinance-price", "price", 1),
            SourceOutcome.zero("stooq-price", "price"),
            SourceOutcome.from_failure("cnbc-top-news", "news", message="boom", transient=True),
            SourceOutcome.ok("yahoo-finance-news", "news", 1),
        ),
        body_used_count=2,
    )
    badge = _render_coverage_badge(coverage)
    assert "**소스 카운트**" in badge
    assert "수집 대상 4" in badge
    assert "성공 2" in badge
    assert "0건 1" in badge
    assert "실패 1" in badge
    assert "본문 사용 2" in badge


def test_badge_omits_count_line_for_legacy_caller() -> None:
    """Legacy callers (no outcomes) → no count-split line; only the
    head line is rendered (backward-compat)."""
    coverage = build_segment_coverage(US_EQUITY, [_item("yfinance-price")])
    badge = _render_coverage_badge(coverage)
    assert "**소스 카운트**" not in badge


def test_badge_limited_severity_label_renders_jeshan() -> None:
    coverage = build_segment_coverage(
        US_EQUITY,
        [_item("yahoo-finance-news", "news")],
        source_outcomes=(
            SourceOutcome.from_failure("yfinance-price", "price", message="x", transient=True),
            SourceOutcome.ok("stooq-price", "price", 1),
            SourceOutcome.ok("yahoo-finance-news", "news", 1),
        ),
    )
    badge = _render_coverage_badge(coverage)
    assert coverage.status == "limited"
    assert "**데이터 상태**: 제한" in badge
    assert SEVERITY_READER_EXPLANATIONS["limited"] in badge


def test_badge_failed_severity_label_renders() -> None:
    coverage = build_segment_coverage(
        US_EQUITY,
        [],
        source_outcomes=(
            SourceOutcome.from_failure("yfinance-price", "price", message="x", transient=True),
            SourceOutcome.from_failure("stooq-price", "price", message="x", transient=True),
        ),
    )
    badge = _render_coverage_badge(coverage)
    assert coverage.status == "failed"
    assert "**데이터 상태**: 실패" in badge
    assert SEVERITY_READER_EXPLANATIONS["failed"] in badge
