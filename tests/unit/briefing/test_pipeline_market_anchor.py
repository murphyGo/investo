"""Pipeline header rendering tests for u49 market anchor line.

Pins:

* ``_enhance_reader_experience`` inserts the ``> **시장 anchor**``
  blockquote line directly after the watermark line and before the
  segment-nav row, when ``market_anchors`` is non-empty.
* Empty ``market_anchors`` collapses the line cleanly (no orphan
  blockquote, no double blank line).
* The anchor line is gated on ``segment is not None`` like the rest
  of the reader-experience header (legacy unsegmented path is
  untouched).
* The Stage 2 system prompt carries the new anchor citation rule.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from investo.briefing.market_anchor import MarketAnchor
from investo.briefing.pipeline import _enhance_reader_experience
from investo.briefing.prompts import STAGE2_SYSTEM

_SECTIONS = (
    "요약 문장입니다. [관망]",
    "전일 이슈 본문입니다.",
    "섹터 흐름입니다.",
    "지표 이벤트입니다.",
    "주요 종목 본문입니다.",
    "관전 포인트입니다.",
)


def _body() -> str:
    return (
        "## ① 요약\n요약 문장입니다. [관망]\n\n"
        "## ② 전일 핵심 이슈\n전일 이슈 본문입니다.\n\n"
        "## ③ 섹터/수급 동향\n섹터 흐름입니다.\n\n"
        "## ④ 지표·이벤트\n지표 이벤트입니다.\n\n"
        "## ⑤ 주요 종목\n주요 종목 본문입니다.\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전 포인트입니다.\n"
    )


def _anchor(ticker: str, *, ath: bool = True) -> MarketAnchor:
    return MarketAnchor(
        ticker=ticker,
        close=Decimal("5820.40"),
        is_ath=ath,
        pct_from_52w_high=Decimal("0.00") if ath else Decimal("-1.50"),
        pct_from_52w_low=Decimal("30.00"),
    )


def test_enhance_inserts_anchor_line_after_watermark() -> None:
    enhanced = _enhance_reader_experience(
        _body(),
        target_date=date(2026, 5, 9),
        segment="us-equity",
        sections=_SECTIONS,
        market_anchors=[_anchor("^GSPC")],
    )
    # Header structure:
    # # 2026-05-09 ... 시황
    #
    # **기준 시각**: ...
    #
    # > **시장 anchor**: ^GSPC 5,820.40 ATH 경신
    # **세그먼트**: ...
    header_block = enhanced.split("## ① 요약", maxsplit=1)[0]
    watermark_idx = header_block.index("**기준 시각**")
    anchor_idx = header_block.index("> **시장 anchor**")
    nav_idx = header_block.index("**세그먼트**")
    assert watermark_idx < anchor_idx < nav_idx, (
        "anchor line must sit between watermark and segment nav"
    )
    assert "^GSPC 5,820.40 ATH 경신" in header_block


def test_enhance_omits_anchor_line_for_empty_anchors() -> None:
    enhanced = _enhance_reader_experience(
        _body(),
        target_date=date(2026, 5, 9),
        segment="us-equity",
        sections=_SECTIONS,
        market_anchors=(),
    )
    header_block = enhanced.split("## ① 요약", maxsplit=1)[0]
    assert "> **시장 anchor**" not in header_block
    # No structural breakage — the watermark and segment-nav rows
    # still exist back to back.
    assert "**기준 시각**" in header_block
    assert "**세그먼트**" in header_block


def test_enhance_omits_anchor_line_when_segment_is_none() -> None:
    """Legacy unsegmented path: ``segment=None`` returns body unchanged."""
    body = _body()
    enhanced = _enhance_reader_experience(
        body,
        target_date=date(2026, 5, 9),
        segment=None,
        sections=_SECTIONS,
        market_anchors=[_anchor("^GSPC")],
    )
    assert enhanced == body  # no header at all in unsegmented path


def test_enhance_renders_multiple_anchors_in_priority_order() -> None:
    anchors = [
        _anchor("AAPL", ath=False),
        _anchor("^GSPC", ath=True),
        _anchor("BTC-USD", ath=False),
    ]
    enhanced = _enhance_reader_experience(
        _body(),
        target_date=date(2026, 5, 9),
        segment="us-equity",
        sections=_SECTIONS,
        market_anchors=anchors,
    )
    header = enhanced.split("## ① 요약", maxsplit=1)[0]
    # Indices come before equities come before crypto in the rendered line.
    assert header.index("^GSPC") < header.index("AAPL")
    assert header.index("AAPL") < header.index("BTC-USD")


# ---------------------------------------------------------------------------
# Stage 2 system prompt rule
# ---------------------------------------------------------------------------


def test_stage2_system_carries_anchor_citation_rule() -> None:
    assert "시장 anchor 인용 룰" in STAGE2_SYSTEM
    assert "ATH 경신" in STAGE2_SYSTEM
    assert "anchor 헤더에 *없는*" in STAGE2_SYSTEM


def test_stage2_system_anchor_rule_extends_numeric_integrity() -> None:
    # Numeric integrity rule still present — anchor rule is an
    # extension, not a replacement.
    assert "numeric integrity rule" in STAGE2_SYSTEM
