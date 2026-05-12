"""Integration test for u51 reader-format wire-through.

Drives ``_apply_reader_format_to_segments`` end-to-end on synthetic
Stage-2 output and verifies the six u51 DoD bullets are met:

* TL;DR block (``## 한눈에 보기``) present + 3 bullets.
* Anchor table replaces the prose blockquote.
* H3 sub-headings (``### Title``) in §②/③/④/⑥.
* Numbers wrapped in ``**...**`` outside tables / code blocks / URLs.
* Glossings deduped (first occurrence kept).
* Disclaimer string preserved verbatim at the tail.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.market_anchor import MarketAnchor
from investo.models import Briefing
from investo.orchestrator.pipeline import _apply_reader_format_to_segments


def _make_briefing(rendered: str) -> Briefing:
    return Briefing(
        target_date=date(2026, 5, 11),
        market_summary="요약 본문.",
        key_issues="이슈 본문.",
        sector_flow="섹터 본문.",
        indicators_events="지표 본문.",
        notable_tickers="종목 본문.",
        today_watch="관전 본문.",
        disclaimer=DISCLAIMER,
        rendered_markdown=rendered,
    )


def _make_anchors() -> tuple[MarketAnchor, ...]:
    return (
        MarketAnchor(
            ticker="^GSPC",
            close=Decimal("7412.84"),
            prev_close=Decimal("7385.30"),
            pct=Decimal("0.37"),
            is_ath=True,
            pct_from_52w_high=None,
            pct_from_52w_low=None,
            mtd_pct=None,
            ytd_pct=Decimal("8.08"),
            volume_z_score=None,
        ),
        MarketAnchor(
            ticker="^IXIC",
            close=Decimal("26274.13"),
            prev_close=Decimal("26135.63"),
            pct=Decimal("0.53"),
            is_ath=True,
            pct_from_52w_high=None,
            pct_from_52w_low=None,
            mtd_pct=None,
            ytd_pct=Decimal("13.08"),
            volume_z_score=None,
        ),
    )


_SAMPLE_BRIEFING = (
    """\
# 2026-05-11 미국 증시 시황

**기준 시각**: 2026-05-11 NY

> **시장 anchor**: ^GSPC 7,412.84 ATH 경신, ^IXIC 26,274.13 ATH 경신
**세그먼트**: A | B | C

> **오늘의 결론**: 3대 지수 상승 마감 — S&P 500 사상 최고치 [강세]
> **핵심 동인**: 전주 반등 흐름 연장 (+3.89% TSLA 견인)
> **주의할 점**: 10Y 4.42% 부담 잔존

## ① 요약

S&P 500(스탠더드앤드푸어스 500 지수)이 +0.37% 상승했다.

## ② 전일 핵심 이슈

**3대 지수 상승 마감 — 전주 반등 흐름 연장**

S&P 500(스탠더드앤드푸어스 500 지수)은 종가 7,412.80으로 +0.37% 상승.
NASDAQ은 26,135.63 → 26,274.13.

## ③ 섹터/수급 동향

데이터 부족.

## ④ 지표·이벤트

| 지표 | 값 |
|------|-----|
| 10Y | 4.42% |

## ⑤ 주요 종목

TSLA +3.89%, NVDA +2.50%.

## ⑥ 오늘의 관전 포인트

- 5/12 SPG·OVV·STE 실적 EPS 상회 여부
- 달러 강세 지속 여부
- 10Y 금리 추세 확인할 필요가 있다
- TSLA 추세 확인
- 변동성 흐름 점검

"""
    + DISCLAIMER
    + "\n"
)


def test_apply_reader_format_to_segments_meets_all_dod_bullets() -> None:
    segment_briefings = {"us-equity": _make_briefing(_SAMPLE_BRIEFING)}  # type: ignore[dict-item]
    anchors_by_segment = {"us-equity": _make_anchors()}  # type: ignore[dict-item]
    out = _apply_reader_format_to_segments(
        segment_briefings,  # type: ignore[arg-type]
        anchors_by_segment=anchors_by_segment,  # type: ignore[arg-type]
    )
    markdown = out["us-equity"].rendered_markdown  # type: ignore[index]

    # DoD-1: TL;DR block present + 3 bullets.
    assert "## 한눈에 보기" in markdown
    tldr_section = markdown.split("## 한눈에 보기", 1)[1].split("## ①", 1)[0]
    bullets = [line for line in tldr_section.splitlines() if line.startswith("- ")]
    assert len(bullets) == 3

    # DoD-2: Anchor table replaces the prose blockquote.
    assert "| 종목 | 종가 | 변동 | 비고 |" in markdown
    assert "> **시장 anchor**:" not in markdown
    assert "| ^GSPC | 7,412.84 | +0.37% | ATH 경신 · +8.08% YTD |" in markdown

    # DoD-3: H3 sub-headings.
    assert "### 3대 지수 상승 마감 — 전주 반등 흐름 연장" in markdown
    assert "**3대 지수 상승 마감 — 전주 반등 흐름 연장**\n\n" not in markdown

    # DoD-4: Numbers wrapped in bold (outside tables / URLs / code).
    assert "**+0.37%**" in markdown
    assert "**+3.89%**" in markdown
    # Table cell stays plain.
    assert "| 10Y | 4.42% |" in markdown

    # DoD-5: Glossing dedupe (first kept, others stripped).
    assert markdown.count("(스탠더드앤드푸어스 500 지수)") == 1
    assert markdown.count("S&P 500") >= 2  # base term still appears multiple times

    # DoD-6: Disclaimer preserved verbatim.
    assert DISCLAIMER in markdown
    # And lives at the tail.
    assert markdown.rstrip().endswith(DISCLAIMER.rstrip())


def test_apply_reader_format_to_segments_empty_input_is_noop() -> None:
    out = _apply_reader_format_to_segments({}, anchors_by_segment={})
    assert out == {}


def test_apply_reader_format_to_segments_skips_segments_without_anchors() -> None:
    segment_briefings = {"us-equity": _make_briefing(_SAMPLE_BRIEFING)}  # type: ignore[dict-item]
    out = _apply_reader_format_to_segments(
        segment_briefings,  # type: ignore[arg-type]
        anchors_by_segment={},
    )
    md = out["us-equity"].rendered_markdown  # type: ignore[index]
    # No anchor table (no anchors supplied) but reader_format still ran.
    assert "| 종목 | 종가 | 변동 | 비고 |" not in md
    assert "## 한눈에 보기" in md  # TL;DR still injected from callouts
    # Disclaimer untouched.
    assert DISCLAIMER in md


def test_apply_reader_format_idempotent_on_second_pass() -> None:
    segment_briefings = {"us-equity": _make_briefing(_SAMPLE_BRIEFING)}  # type: ignore[dict-item]
    anchors_by_segment = {"us-equity": _make_anchors()}  # type: ignore[dict-item]
    first = _apply_reader_format_to_segments(
        segment_briefings,  # type: ignore[arg-type]
        anchors_by_segment=anchors_by_segment,  # type: ignore[arg-type]
    )
    second = _apply_reader_format_to_segments(
        first,  # type: ignore[arg-type]
        anchors_by_segment=anchors_by_segment,  # type: ignore[arg-type]
    )
    # Same-day re-publish (FR-006) must yield byte-equal markdown.
    assert (
        first["us-equity"].rendered_markdown  # type: ignore[index]
        == second["us-equity"].rendered_markdown  # type: ignore[index]
    )
