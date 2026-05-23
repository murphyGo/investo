"""u54 — Trace diagnostics surfaces sanitized failure cells (AC-5).

The collapsed trace already exists from u22/u32; this test pins that
failure-reason text routes through ``sanitize_source_error_message``
(the R13 chokepoint) so a secret-shaped value in an adapter's
exception message cannot leak via the trace row.
"""

from __future__ import annotations

import pytest

from investo.briefing.pipeline import (
    _classify_failure_reason,
    _render_source_outcome_line,
)
from investo.briefing.segments import US_EQUITY, build_segment_coverage
from investo.models import SourceOutcome


def test_failed_source_outcome_line_uses_sanitized_message() -> None:
    # Construct a failed outcome whose raw message embeds a
    # Telegram-bot-token-shaped substring — the chokepoint must redact
    # it before the trace row consumes ``failure_reason``.
    outcome = SourceOutcome.from_failure(
        "yfinance-price",
        "price",
        message=(
            "Auth header rejected: bot 123456:AAH-secret-shape-bot-token-tail-Xyz from request URL"
        ),
        transient=False,
    )
    coverage = build_segment_coverage(
        US_EQUITY,
        [],
        source_outcomes=(outcome,),
    )
    rendered = _render_source_outcome_line(coverage)
    # Sanitization happened upstream (from_failure) — the raw token
    # shape is not in the rendered cell.
    assert "AAH-secret-shape-bot-token-tail-Xyz" not in rendered
    assert "yfinance-price 실패" in rendered


def test_zero_and_failed_render_deterministic_order() -> None:
    """Failed first, then zero, then ``정상 N개``. Pinned for the trace
    column-order contract."""
    coverage = build_segment_coverage(
        US_EQUITY,
        [],
        source_outcomes=(
            SourceOutcome.zero("yahoo-finance-news", "news"),
            SourceOutcome.from_failure("yfinance-price", "price", message="x", transient=True),
            SourceOutcome.ok("stooq-price", "price", 2),
        ),
    )
    rendered = _render_source_outcome_line(coverage)
    failed_idx = rendered.find("yfinance-price 실패")
    zero_idx = rendered.find("yahoo-finance-news 0건")
    ok_idx = rendered.find("정상 1개")
    assert 0 <= failed_idx < zero_idx < ok_idx


# P1-3 — the reader-facing source line must classify raw plumbing reasons
# into Korean category labels, never echo the English exception text.
@pytest.mark.parametrize(
    ("reason", "expected_label"),
    [
        # observed archive evidence — verbatim sanitized reasons.
        ("source 'cnbc-top-news' failed: status 403 (terminal)", "접근 제한"),
        ("source 'binance-crypto-market' failed: status 451 (terminal)", "접근 제한"),
        (
            "source 'congress-gov-bill-actions' failed: CONGRESS_API_KEY not set; "
            "congress-gov-bill-actions adapter will not run",
            "설정 미완료(미수집)",
        ),
        # other 4xx access shapes.
        ("status 401 (terminal)", "접근 제한"),
        ("status 404 (terminal)", "접근 제한"),
        ("status 429 after 3 attempts", "접근 제한"),
        # 5xx / transient shapes.
        ("status 503 after 3 attempts", "일시적 수집 오류"),
        ("exceeded 8s total budget", "일시적 수집 오류"),
        ("network error after 3 attempts: ReadTimeout", "일시적 수집 오류"),
        ("HTTP error: connection refused", "일시적 수집 오류"),
        # generic fallback.
        ("response body exceeded 5000000 cap while streaming", "수집 불가"),
        ("", "수집 불가"),
        (None, "수집 불가"),
    ],
)
def test_classify_failure_reason(reason: str | None, expected_label: str) -> None:
    assert _classify_failure_reason(reason) == expected_label


def test_reader_line_omits_raw_english_plumbing() -> None:
    """The rendered reader line carries the Korean label, not the raw
    ``status 403 (terminal)`` / ``not set`` plumbing text (P1-3)."""
    coverage = build_segment_coverage(
        US_EQUITY,
        [],
        source_outcomes=(
            SourceOutcome.from_failure(
                "cnbc-top-news",
                "news",
                message="source 'cnbc-top-news' failed: status 403 (terminal)",
                transient=False,
            ),
            SourceOutcome.from_failure(
                "congress-gov-bill-actions",
                "calendar",
                message="CONGRESS_API_KEY not set; congress-gov-bill-actions adapter will not run",
                transient=False,
            ),
        ),
    )
    rendered = _render_source_outcome_line(coverage)
    assert "cnbc-top-news 실패 (접근 제한)" in rendered
    assert "congress-gov-bill-actions 실패 (설정 미완료(미수집))" in rendered
    # no raw English plumbing leaks to the reader surface.
    assert "status 403" not in rendered
    assert "terminal" not in rendered
    assert "not set" not in rendered
    assert "CONGRESS_API_KEY" not in rendered
