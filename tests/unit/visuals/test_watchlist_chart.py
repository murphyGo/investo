"""Tests for u33 Step 5 — cumulative match SVG chart."""

from __future__ import annotations

from investo.visuals.watchlist_chart import render_cumulative_match_chart


def test_empty_chart_includes_no_data_message() -> None:
    out = render_cumulative_match_chart({})
    assert "집계할 매칭이 아직 없습니다" in out
    assert "<svg" in out


def test_chart_lists_terms_sorted_by_count_desc() -> None:
    out = render_cumulative_match_chart({"NVDA": 3, "AAPL": 7, "TSLA": 1})
    # AAPL (7) appears before NVDA (3) appears before TSLA (1).
    assert out.find("AAPL") < out.find("NVDA") < out.find("TSLA")


def test_chart_breaks_ties_alphabetically() -> None:
    out = render_cumulative_match_chart({"NVDA": 3, "AAPL": 3, "MSFT": 3})
    assert out.find("AAPL") < out.find("MSFT") < out.find("NVDA")


def test_chart_caps_visible_bars_and_collapses_overflow() -> None:
    counts = {f"T{i:02d}": 20 - i for i in range(12)}  # T00=20 ... T11=9 (all positive)
    out = render_cumulative_match_chart(counts)
    # Top 8 individual bars + a "기타" overflow row aggregating the rest.
    assert "기타" in out
    # Bars beyond top-8 must NOT appear individually.
    assert "T08" not in out
    assert "T09" not in out
    assert "T10" not in out
    assert "T11" not in out


def test_chart_is_deterministic() -> None:
    a = render_cumulative_match_chart({"NVDA": 3, "AAPL": 7})
    b = render_cumulative_match_chart({"AAPL": 7, "NVDA": 3})
    assert a == b


def test_chart_escapes_xml_unsafe_terms() -> None:
    out = render_cumulative_match_chart({"<bad>": 3})
    assert "<bad>" not in out
    assert "&lt;bad&gt;" in out


def test_chart_uses_self_contained_svg() -> None:
    out = render_cumulative_match_chart({"NVDA": 3})
    assert out.startswith("<svg")
    assert out.endswith("</svg>")
    assert "xmlns=" in out
