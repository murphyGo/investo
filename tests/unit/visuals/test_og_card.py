"""Tests for the OG image SVG card renderer (u29 site-discovery-v2)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.models import Briefing
from investo.visuals.og_card import (
    OG_CARD_HEIGHT,
    OG_CARD_WIDTH,
    build_og_card_input,
    render_og_card_svg,
    write_og_card,
)


def _briefing(target_date: date, conclusion: str) -> Briefing:
    body = (
        f"> **오늘의 결론**: {conclusion}\n"
        "> **핵심 동인**: x\n"
        "> **주의할 점**: y\n\n"
        "## ① 요약\nA\n"
        "## ② 전일 핵심 이슈\nA\n"
        "## ③ 섹터/수급 동향\nA\n"
        "## ④ 지표·이벤트\nA\n"
        "## ⑤ 주요 종목\nA\n"
        "## ⑥ 오늘의 관전 포인트\nA\n\n"
    )
    rendered = body + DISCLAIMER
    return Briefing(
        target_date=target_date,
        market_summary="A",
        key_issues="A",
        sector_flow="A",
        indicators_events="A",
        notable_tickers="A",
        today_watch="A",
        disclaimer=DISCLAIMER,
        rendered_markdown=rendered,
    )


def test_build_og_card_input_extracts_conclusion_per_segment() -> None:
    target = date(2026, 5, 7)
    briefings = {
        DOMESTIC_EQUITY: _briefing(target, "국내 결론입니다."),
        US_EQUITY: _briefing(target, "미국 결론입니다."),
        CRYPTO: _briefing(target, "크립토 결론입니다."),
    }
    inp = build_og_card_input(target, briefings)
    assert inp.target_date == target
    assert dict(inp.segment_lines) == {
        DOMESTIC_EQUITY: "국내 결론입니다.",
        US_EQUITY: "미국 결론입니다.",
        CRYPTO: "크립토 결론입니다.",
    }


def test_render_og_card_svg_emits_canonical_size_and_disclaimer() -> None:
    target = date(2026, 5, 7)
    briefings = {
        DOMESTIC_EQUITY: _briefing(target, "Korea."),
        US_EQUITY: _briefing(target, "US."),
        CRYPTO: _briefing(target, "Crypto."),
    }
    inp = build_og_card_input(target, briefings)
    svg = render_og_card_svg(inp)

    assert f'width="{OG_CARD_WIDTH}"' in svg
    assert f'height="{OG_CARD_HEIGHT}"' in svg
    assert "투자 자문이 아닙니다" in svg
    assert "2026-05-07" in svg
    assert "국내 증시" in svg and "미국 증시" in svg and "크립토" in svg


def test_write_og_card_atomically(tmp_path: Path) -> None:
    target = date(2026, 5, 7)
    briefings = {
        DOMESTIC_EQUITY: _briefing(target, "Korea."),
        US_EQUITY: _briefing(target, "US."),
        CRYPTO: _briefing(target, "Crypto."),
    }
    out_path = tmp_path / "site_docs" / "assets" / "og-card.svg"
    written = write_og_card(target, briefings, out_path=out_path)
    assert written == out_path
    assert out_path.exists()
    assert out_path.read_text(encoding="utf-8").startswith("<svg")
    # No tmp leftovers.
    assert not (tmp_path / "site_docs" / "assets" / "og-card.svg.tmp").exists()


def test_render_og_card_svg_falls_back_when_conclusion_missing() -> None:
    target = date(2026, 5, 7)
    inp = build_og_card_input(target, segment_briefings={})
    svg = render_og_card_svg(inp)
    assert "결론 인용을 추출하지 못했습니다." in svg


def test_render_og_card_svg_is_deterministic() -> None:
    target = date(2026, 5, 7)
    briefings = {
        DOMESTIC_EQUITY: _briefing(target, "K."),
        US_EQUITY: _briefing(target, "U."),
        CRYPTO: _briefing(target, "C."),
    }
    a = render_og_card_svg(build_og_card_input(target, briefings))
    b = render_og_card_svg(build_og_card_input(target, briefings))
    assert a == b
