"""Pipeline header rendering tests for u40 glossary callouts."""

from __future__ import annotations

from datetime import date

from investo.briefing.pipeline import _enhance_reader_experience

_SECTIONS = (
    "요약 문장입니다. [관망]",
    "EIA 주간 재고와 DXY 흐름이 핵심입니다.",
    "섹터 흐름입니다.",
    "지표 이벤트입니다.",
    "주요 종목입니다.",
    "관전 포인트입니다.",
)


def _body(section_2: str) -> str:
    return (
        "## ① 요약\n요약 문장입니다. [관망]\n\n"
        f"## ② 전일 핵심 이슈\n{section_2}\n\n"
        "## ③ 섹터/수급 동향\n섹터 흐름입니다.\n\n"
        "## ④ 지표·이벤트\n지표 이벤트입니다.\n\n"
        "## ⑤ 주요 종목\n주요 종목입니다.\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전 포인트입니다.\n"
    )


def test_enhance_reader_experience_adds_glossary_callout_for_gaps() -> None:
    enhanced = _enhance_reader_experience(
        _body("EIA 주간 재고와 DXY 흐름이 핵심입니다."),
        target_date=date(2026, 5, 9),
        segment="us-equity",
        sections=_SECTIONS,
    )

    header = enhanced.split("## ① 요약", maxsplit=1)[0]
    assert "> **용어 가이드**: 이번 시황에서 처음 등장한 용어" in header
    assert "EIA(에너지정보청), DXY(달러지수)" in header


def test_enhance_reader_experience_skips_callout_when_first_use_is_glossed() -> None:
    enhanced = _enhance_reader_experience(
        _body("EIA(에너지정보청) 주간 재고가 중요합니다. 다음 EIA 발표도 봅니다."),
        target_date=date(2026, 5, 9),
        segment="us-equity",
        sections=_SECTIONS,
    )

    header = enhanced.split("## ① 요약", maxsplit=1)[0]
    assert "용어 가이드" not in header


def test_enhance_reader_experience_caps_glossary_callout() -> None:
    enhanced = _enhance_reader_experience(
        _body("EIA DXY CPI FOMC VIX ETF EPS 모두 설명이 없습니다."),
        target_date=date(2026, 5, 9),
        segment="us-equity",
        sections=_SECTIONS,
    )

    header = enhanced.split("## ① 요약", maxsplit=1)[0]
    assert "EIA(에너지정보청)" in header
    assert "외 2건" in header
