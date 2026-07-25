"""u55 Step 6 — Canary integration tests for the numeric/date/freshness chain.

These tests *do not* drive the full orchestrator pipeline. Instead they
compose the four u55 gates (``verify_core_facts``,
``find_corrupt_date_tokens``, ``verify_direction_against_anchor``,
``evaluate_segment_freshness``) end-to-end against fixture markdown
that contains intentionally-planted violations:

* ``5/65/7`` corruption  → ``find_corrupt_date_tokens`` must return ≥1.
* ATH lie (body claims ATH, anchor says distance -1.4%) →
  ``verify_direction_against_anchor`` returns one ``ath`` conflict.
* KOSPI prose without a source-emitted ``core_fact:kospi_close`` →
  ``verify_core_facts`` actions map says ``kospi_close: downgrade``.

The point is to pin the *composition* of the gate chain so a future
refactor that breaks one gate's surface contract is caught by an
integration test, not just unit tests.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from investo.briefing.date_corruption import (
    find_corrupt_date_tokens,
    verify_direction_against_anchor,
)
from investo.briefing.freshness import evaluate_segment_freshness
from investo.briefing.market_anchor import MarketAnchor
from investo.briefing.numeric_verify import render_downgrade_callout, verify_core_facts
from investo.models import NormalizedItem


def _item_with_fact(fact: str, value: str) -> NormalizedItem:
    return NormalizedItem(
        source_name="yfinance-price",
        category="price",
        title="fixture",
        summary=None,
        url="https://example.com/x",
        published_at=datetime(2026, 5, 11, 20, 0, tzinfo=UTC),
        raw_metadata={f"core_fact:{fact}": value},
    )


def _anchor_ath_lie() -> MarketAnchor:
    """Anchor that contradicts an ATH claim: distance from 52w high = -1.4%."""
    return MarketAnchor(
        ticker="^GSPC",
        close=Decimal("5750.00"),
        prev_close=Decimal("5700.00"),
        pct=Decimal("0.85"),
        is_ath=False,
        pct_from_52w_high=Decimal("-1.40"),
        pct_from_52w_low=None,
        mtd_pct=None,
        ytd_pct=None,
        volume_z_score=None,
    )


def test_canary_5_65_7_corruption_blocks() -> None:
    body = "## 요약\n토큰 corrupt 5/65/7 발생\n"
    corrupt = find_corrupt_date_tokens(body)
    assert len(corrupt) == 1
    assert corrupt[0].raw == "5/65/7"
    assert corrupt[0].reason == "day_out_of_range"


def test_canary_ath_lie_conflicts_with_anchor() -> None:
    body = "## 요약\nS&P 500 ATH 갱신 — 사상 최고치 마감.\n"
    conflicts = verify_direction_against_anchor(body, [_anchor_ath_lie()])
    assert len(conflicts) >= 1
    assert any(c.body_claim == "ath" for c in conflicts)


def test_canary_kospi_prose_without_source_downgrades() -> None:
    body = "## 요약\n코스피는 2,810.45 포인트로 마감했다.\n"
    # Source items have S&P but not KOSPI.
    items = [_item_with_fact("spx_close", "5820.40")]
    report = verify_core_facts(body, items)
    assert report.actions == {"kospi_close": "downgrade"}
    assert "kospi_close" in report.unverified
    callout = render_downgrade_callout(report)
    assert "kospi_close" in callout


def test_canary_freshness_stale_for_old_archive() -> None:
    now = datetime(2026, 5, 11, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    status, reason = evaluate_segment_freshness("domestic-equity", date(2026, 5, 4), now=now)
    assert status == "stale"
    assert reason is not None


def test_canary_full_chain_pass_when_clean() -> None:
    """Clean body + matching anchor + verified source + fresh archive ⇒ no blockers."""
    body = (
        "## 요약\n"
        "S&P 500는 5,820.40에 마감했고 [강세] 흐름을 보였다.\n"
        "코스피는 2,810.45 포인트로 마감.\n"
    )
    items = [
        _item_with_fact("spx_close", "5820.40"),
        _item_with_fact("kospi_close", "2810.45"),
    ]
    anchor_ok = MarketAnchor(
        ticker="^GSPC",
        close=Decimal("5820.40"),
        prev_close=Decimal("5770.00"),
        pct=Decimal("0.87"),
        is_ath=False,
        pct_from_52w_high=Decimal("-0.20"),
        pct_from_52w_low=None,
        mtd_pct=None,
        ytd_pct=None,
        volume_z_score=None,
    )
    assert find_corrupt_date_tokens(body) == ()
    assert verify_direction_against_anchor(body, [anchor_ok]) == ()
    report = verify_core_facts(body, items)
    assert set(report.verified) == {"spx_close", "kospi_close"}
    assert report.conflicts == ()
    assert report.unverified == ()
    now = datetime(2026, 5, 11, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    status, _ = evaluate_segment_freshness("domestic-equity", date(2026, 5, 11), now=now)
    assert status == "fresh"


def test_canary_callout_is_deterministic() -> None:
    body = "## 요약\n코스피 2,810.45, BTC 70,000"
    items = [_item_with_fact("spx_close", "5820.40")]
    a = render_downgrade_callout(verify_core_facts(body, items))
    b = render_downgrade_callout(verify_core_facts(body, items))
    assert a == b
