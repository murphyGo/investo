"""u131 rendered-chain regression for the 2026-06-29/30 residue family."""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from investo._internal.surface_quality import find_surface_quality_issues
from investo.briefing.disclaimer import DISCLAIMER
from investo.models import Briefing
from investo.models.market_anchor import MarketAnchor
from investo.models.segments import CRYPTO
from investo.publisher.reader_format import MEANING_FALLBACK
from investo.publisher.segment_reader_format import apply_reader_format_to_segments

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures/u131/bounded-line-regression.json"
_OWNED_LINE_RE = re.compile(
    r"^(?:> \*\*(?:그래서 의미는\?|주의할 점)\*\*|#### 관찰 신호:)",
)
_TRAILING_ELLIPSIS_RE = re.compile(r"(?:\.{3}|…)$")


def _load_fixture() -> dict[str, Any]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _briefing(fixture: dict[str, Any]) -> Briefing:
    markdown = (
        "# 2026-06-30 크립토 시황\n\n"
        "> **오늘의 결론**: 시장 방향을 추가로 확인해야 합니다.\n"
        "> **핵심 동인**: 수급과 심리가 엇갈립니다.\n"
        f"> **주의할 점**: {fixture['caution_body']}\n\n"
        "## ① 요약\n\n시장 요약입니다.\n\n"
        "## ② 전일 핵심 이슈\n\n이슈 본문입니다.\n\n"
        f"> **그래서 의미는?** {fixture['meaning_body']}\n\n"
        "## ③ 섹터/수급 동향\n\n수급 본문입니다.\n\n"
        "## ④ 지표·이벤트\n\n지표 본문입니다.\n\n"
        "## ⑤ 주요 종목\n\n종목 본문입니다.\n\n"
        "## ⑥ 오늘의 관전 포인트\n\n"
        f"- {fixture['watchpoint_bullet']}\n\n"
        f"{DISCLAIMER}\n"
    )
    return Briefing(
        target_date=date(2026, 6, 30),
        market_summary="시장 방향을 추가로 확인해야 합니다.",
        key_issues="이슈",
        sector_flow="수급",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer=DISCLAIMER,
        rendered_markdown=markdown,
    )


def test_u131_trimmed_incidents_render_cleanly_and_rerun_byte_stable() -> None:
    fixture = _load_fixture()
    original = _briefing(fixture)

    anchor = MarketAnchor(
        ticker="BTC-USD",
        close=Decimal("60284"),
        prev_close=Decimal("58969.09"),
        pct=Decimal("2.23"),
        is_ath=False,
    )
    anchors = {CRYPTO: (anchor,)}
    first = apply_reader_format_to_segments(
        {CRYPTO: original},
        anchors_by_segment=anchors,
    )[CRYPTO]
    second = apply_reader_format_to_segments(
        {CRYPTO: first},
        anchors_by_segment=anchors,
    )[CRYPTO]
    rendered = first.rendered_markdown
    rendered_lines = rendered.splitlines()

    assert first.rendered_markdown == second.rendered_markdown

    owned_lines = [line for line in rendered_lines if _OWNED_LINE_RE.match(line)]
    assert owned_lines == [
        "> **주의할 점**: 본문 §②·§④ 참조",
        MEANING_FALLBACK,
        "#### 관찰 신호: CoinGecko BTC",
    ]
    assert all(_TRAILING_ELLIPSIS_RE.search(line) is None for line in owned_lines)
    assert "- 현재: **$60,284.00** (**+2.23%**)" in rendered
    assert not any(
        issue.code == "summary.truncated_mid_token"
        for issue in find_surface_quality_issues(rendered)
    )

    legacy = fixture["legacy_residue"]
    assert legacy["meaning_line"] not in rendered
    assert legacy["caution_line"] not in rendered
    assert legacy["watchpoint_title"] not in rendered
