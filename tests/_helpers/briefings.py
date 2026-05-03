"""Shared Briefing builders for publisher and integration tests."""

from __future__ import annotations

from datetime import date

from investo.briefing.disclaimer import DISCLAIMER
from investo.models import Briefing

DEFAULT_TARGET_DATE = date(2026, 4, 25)


def build_briefing(
    *,
    target_date: date = DEFAULT_TARGET_DATE,
    with_disclaimer: bool = True,
) -> Briefing:
    """Construct a minimal Briefing fixture.

    When ``with_disclaimer`` is false, bypass model validation with
    ``model_construct`` so publisher failure-path tests can explicitly
    exercise malformed briefing input.
    """
    body = (
        "## ① 요약\n오늘 시장 요약\n\n"
        "## ② 전일 핵심 이슈\n핵심 이슈\n\n"
        "## ③ 섹터/수급 동향\n섹터 동향\n\n"
        "## ④ 지표·이벤트\n지표 이벤트\n\n"
        "## ⑤ 주요 종목\n종목 본문\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전 포인트\n\n"
    )
    rendered = body + (DISCLAIMER if with_disclaimer else "no disclaimer here")
    kwargs = {
        "target_date": target_date,
        "market_summary": "요약",
        "key_issues": "이슈",
        "sector_flow": "섹터",
        "indicators_events": "지표",
        "notable_tickers": "종목",
        "today_watch": "관전",
        "disclaimer": DISCLAIMER,
        "rendered_markdown": rendered,
    }
    if not with_disclaimer:
        return Briefing.model_construct(**kwargs)
    return Briefing(**kwargs)
