"""Tests for the OG image SVG card renderer (u29 site-discovery-v2)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.models import Briefing
from investo.visuals.og_card import (
    OG_CARD_HEIGHT,
    OG_CARD_PNG_RELATIVE_PATH,
    OG_CARD_WIDTH,
    build_og_card_input,
    render_og_card_png,
    render_og_card_svg,
    write_og_card,
)
from investo.visuals.provenance import read_manifest


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
    png_path = out_path.with_suffix(".png")
    assert written == (
        out_path,
        png_path,
        out_path.with_suffix(".svg.json"),
        png_path.with_suffix(".png.json"),
    )
    assert out_path.exists()
    assert png_path.exists()
    assert out_path.read_text(encoding="utf-8").startswith("<svg")
    assert _png_dimensions(png_path.read_bytes()) == (OG_CARD_WIDTH, OG_CARD_HEIGHT)
    # No tmp leftovers.
    assert not (tmp_path / "site_docs" / "assets" / "og-card.svg.tmp").exists()
    assert not (tmp_path / "site_docs" / "assets" / "og-card.png.tmp").exists()


def test_render_og_card_png_writes_canonical_dimensions(tmp_path: Path) -> None:
    svg = render_og_card_svg(
        build_og_card_input(
            date(2026, 5, 7),
            {
                DOMESTIC_EQUITY: _briefing(date(2026, 5, 7), "K."),
                US_EQUITY: _briefing(date(2026, 5, 7), "U."),
                CRYPTO: _briefing(date(2026, 5, 7), "C."),
            },
        )
    )
    png_path = tmp_path / "og-card.png"

    written = render_og_card_png(svg.encode("utf-8"), output_path=png_path)

    assert written == png_path
    assert _png_dimensions(png_path.read_bytes()) == (OG_CARD_WIDTH, OG_CARD_HEIGHT)


def test_write_og_card_writes_matching_png_manifest(tmp_path: Path) -> None:
    target = date(2026, 5, 7)
    out_path = tmp_path / "site_docs" / "assets" / "og-card.svg"

    write_og_card(
        target,
        {
            DOMESTIC_EQUITY: _briefing(target, "K."),
            US_EQUITY: _briefing(target, "U."),
            CRYPTO: _briefing(target, "C."),
        },
        out_path=out_path,
    )

    svg_manifest = read_manifest(out_path)
    png_manifest = read_manifest(out_path.with_suffix(".png"))
    assert png_manifest.source_type == "generated_svg"
    assert png_manifest.content_type == "image/png"
    assert png_manifest.dimensions == (OG_CARD_WIDTH, OG_CARD_HEIGHT)
    assert png_manifest.generator == svg_manifest.generator
    assert png_manifest.version == svg_manifest.version
    assert png_manifest.additional_metadata["source_svg"] == out_path.name


def test_write_og_card_rolls_back_svg_when_png_render_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from investo.visuals import og_card as og_card_module

    def fail_png(*args: object, **kwargs: object) -> Path:
        raise RuntimeError("png failed")

    target = date(2026, 5, 7)
    out_path = tmp_path / "site_docs" / "assets" / "og-card.svg"
    monkeypatch.setattr(og_card_module, "render_og_card_png", fail_png)

    with pytest.raises(RuntimeError, match="png failed"):
        write_og_card(
            target,
            {
                DOMESTIC_EQUITY: _briefing(target, "K."),
                US_EQUITY: _briefing(target, "U."),
                CRYPTO: _briefing(target, "C."),
            },
            out_path=out_path,
        )

    assert not out_path.exists()
    assert not out_path.with_suffix(".png").exists()


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


def test_png_relative_path_matches_svg_twin() -> None:
    assert Path("site_docs/assets/og-card.png") == OG_CARD_PNG_RELATIVE_PATH


def _png_dimensions(content: bytes) -> tuple[int, int]:
    assert content.startswith(b"\x89PNG\r\n\x1a\n")
    return int.from_bytes(content[16:20], "big"), int.from_bytes(content[20:24], "big")
