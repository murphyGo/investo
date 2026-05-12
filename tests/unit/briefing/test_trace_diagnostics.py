"""u54 — Trace diagnostics surfaces sanitized failure cells (AC-5).

The collapsed trace already exists from u22/u32; this test pins that
failure-reason text routes through ``sanitize_source_error_message``
(the R13 chokepoint) so a secret-shaped value in an adapter's
exception message cannot leak via the trace row.
"""

from __future__ import annotations

from investo.briefing.pipeline import _render_source_outcome_line
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
