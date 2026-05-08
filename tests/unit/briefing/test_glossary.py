"""Tests for u40 financial glossary compliance helpers."""

from __future__ import annotations

import re

from investo.briefing.glossary import (
    BASELINE_GLOSSARY,
    audit_glossary_compliance,
    render_glossary_callout,
)


def test_baseline_glossary_has_minimum_curated_entries() -> None:
    assert len(BASELINE_GLOSSARY) >= 30
    for term, gloss in BASELINE_GLOSSARY.items():
        assert term.strip() == term
        assert gloss.strip() == gloss
        assert re.fullmatch(r"[가-힣A-Za-z& ]{1,12}", gloss)


def test_audit_reports_first_appearance_without_gloss() -> None:
    gaps = audit_glossary_compliance(
        "EIA 주간 재고는 DXY 흐름과 함께 확인됩니다.",
        segment="us-equity",
    )

    assert [(gap.term, gap.gloss) for gap in gaps] == [
        ("EIA", "에너지정보청"),
        ("DXY", "달러지수"),
    ]


def test_audit_accepts_korean_gloss_on_first_appearance() -> None:
    gaps = audit_glossary_compliance(
        "EIA(에너지정보청) 주간 재고는 중요합니다. 다음 EIA 발표도 봅니다.",
        segment="us-equity",
    )

    assert gaps == []


def test_audit_accepts_korean_substring_inside_mixed_parentheses() -> None:
    gaps = audit_glossary_compliance("EIA(EIA, 에너지정보청) 주간 재고", segment="us-equity")

    assert gaps == []


def test_audit_matches_futures_code_wildcards() -> None:
    gaps = audit_glossary_compliance("ESM26 선물과 NQU25 선물이 엇갈렸습니다.", segment="us-equity")

    assert [(gap.term, gap.gloss) for gap in gaps] == [
        ("ESM26", "미니S&P선물"),
        ("NQU25", "나스닥선물"),
    ]


def test_audit_empty_input_is_quiet() -> None:
    assert audit_glossary_compliance("", segment="crypto") == []


def test_render_glossary_callout_caps_terms() -> None:
    gaps = audit_glossary_compliance(
        "EIA DXY CPI FOMC VIX ETF EPS 모두 설명이 없습니다.",
        segment="us-equity",
    )

    callout = render_glossary_callout(gaps)

    assert callout.startswith("> **용어 가이드**")
    assert "EIA(에너지정보청)" in callout
    assert "외 2건" in callout
