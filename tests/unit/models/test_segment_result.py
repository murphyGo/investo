"""u55 Step 4 — Tests for the :class:`SegmentResult` model contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from investo.models import Briefing
from investo.models.segment_result import SegmentResult


def _briefing() -> Briefing:
    disclaimer = "본 보고서는 정보 제공 목적이며 투자 권유가 아닙니다."
    body = (
        "## 요약\n오늘 마감.\n"
        "## 핵심 이슈\nnone\n"
        "## 섹터\nnone\n"
        "## 지표\nnone\n"
        "## 종목\nnone\n"
        "## 관전 포인트\nnone\n"
    )
    rendered = body + "\n" + disclaimer
    return Briefing(
        target_date="2026-05-11",  # type: ignore[arg-type]
        market_summary="오늘 마감.",
        key_issues="none",
        sector_flow="none",
        indicators_events="none",
        notable_tickers="none",
        today_watch="none",
        disclaimer=disclaimer,
        rendered_markdown=rendered,
    )


def test_fresh_with_briefing_passes() -> None:
    result = SegmentResult(
        segment="us-equity",
        status="fresh",
        briefing=_briefing(),
    )
    assert result.is_publishable
    assert result.stale_reason is None


def test_fresh_without_briefing_fails() -> None:
    with pytest.raises(ValidationError):
        SegmentResult(segment="us-equity", status="fresh", briefing=None)


def test_fresh_with_stale_reason_fails() -> None:
    with pytest.raises(ValidationError):
        SegmentResult(
            segment="us-equity",
            status="fresh",
            briefing=_briefing(),
            stale_reason="should not be present",
        )


def test_stale_without_reason_fails() -> None:
    with pytest.raises(ValidationError):
        SegmentResult(segment="us-equity", status="stale", briefing=None)


def test_stale_with_briefing_fails() -> None:
    with pytest.raises(ValidationError):
        SegmentResult(
            segment="us-equity",
            status="stale",
            briefing=_briefing(),
            stale_reason="x",
        )


def test_stale_proper_shape() -> None:
    result = SegmentResult(
        segment="domestic-equity",
        status="stale",
        briefing=None,
        stale_reason="국내 세그먼트 최신 아카이브 2026-05-04 — 기대일 2026-05-08 대비 지연",
    )
    assert not result.is_publishable
    assert result.briefing is None


def test_failed_status_requires_reason() -> None:
    with pytest.raises(ValidationError):
        SegmentResult(segment="crypto", status="failed", briefing=None)


def test_failed_with_reason_ok() -> None:
    result = SegmentResult(
        segment="crypto",
        status="failed",
        briefing=None,
        stale_reason="numeric gate blocked: 5/65/7 corruption",
    )
    assert result.status == "failed"
    assert not result.is_publishable


def test_frozen_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        SegmentResult(  # type: ignore[call-arg]
            segment="us-equity",
            status="fresh",
            briefing=_briefing(),
            unknown_field="rejected",
        )
