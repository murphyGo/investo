"""Tests for u40 financial glossary compliance helpers."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from investo.briefing.glossary import (
    BASELINE_GLOSSARY,
    audit_glossary_compliance,
    collect_recently_glossed,
    render_glossary_callout,
)


def _write_archive(root: Path, segment: str, day: date, body: str) -> None:
    path = root / segment / f"{day.year:04d}" / f"{day.month:02d}" / f"{day.isoformat()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


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


# ---------------------------------------------------------------------------
# u68 — cross-day glossed-term suppression
# ---------------------------------------------------------------------------


def test_audit_default_suppression_is_byte_equal_to_legacy() -> None:
    # AC-68.2 — passing no / empty suppression reproduces today-only output.
    md = "EIA 주간 재고는 DXY 흐름과 함께 확인됩니다."
    base = audit_glossary_compliance(md, segment="us-equity")
    assert audit_glossary_compliance(md, segment="us-equity", already_glossed=None) == base
    assert audit_glossary_compliance(md, segment="us-equity", already_glossed=set()) == base


def test_audit_drops_suppressed_canonical_keys() -> None:
    gaps = audit_glossary_compliance(
        "EIA 주간 재고는 DXY 흐름과 함께 확인됩니다.",
        segment="us-equity",
        already_glossed={"EIA"},
    )

    assert [gap.term for gap in gaps] == ["DXY"]


def test_collect_glossed_detects_immediate_paren_gloss(tmp_path: Path) -> None:
    # AC-68.1 — a body paren-glossed term in a prior archive is collected.
    _write_archive(
        tmp_path,
        "us-equity",
        date(2026, 5, 21),
        "> **오늘의 결론**: 요약.\n\nEIA(에너지정보청) 주간 재고가 발표됐습니다.\n",
    )

    glossed = collect_recently_glossed(tmp_path, "us-equity", date(2026, 5, 22))

    assert "EIA" in glossed


def test_collect_glossed_detects_prior_callout_line(tmp_path: Path) -> None:
    _write_archive(
        tmp_path,
        "us-equity",
        date(2026, 5, 21),
        "> **용어 가이드**: 이번 시황에서 처음 등장한 용어 — ETF(상장지수펀드), VIX(변동성지수)\n"
        "> **오늘의 결론**: 요약.\n",
    )

    glossed = collect_recently_glossed(tmp_path, "us-equity", date(2026, 5, 22))

    assert {"ETF", "VIX"} <= glossed


def test_collect_glossed_segment_scoped(tmp_path: Path) -> None:
    # A gloss in a DIFFERENT segment must not leak into this segment.
    _write_archive(
        tmp_path,
        "crypto",
        date(2026, 5, 21),
        "ETF(상장지수펀드) 자금이 유입됐습니다.\n> **오늘의 결론**: 요약.\n",
    )

    glossed = collect_recently_glossed(tmp_path, "us-equity", date(2026, 5, 22))

    assert glossed == set()


def test_collect_glossed_fresh_repo_returns_empty(tmp_path: Path) -> None:
    # AC-68.4 — no prior archive → empty set → caller falls back to all.
    assert collect_recently_glossed(tmp_path, "us-equity", date(2026, 5, 22)) == set()


def test_collect_glossed_skips_weekend_cursor(tmp_path: Path) -> None:
    # today=Monday 2026-05-25 → cursor starts Sunday 24th (skipped),
    # Saturday 23rd (skipped), reaches Friday 22nd as the first trading day.
    _write_archive(
        tmp_path,
        "us-equity",
        date(2026, 5, 22),
        "EIA(에너지정보청) 재고.\n> **오늘의 결론**: 요약.\n",
    )

    glossed = collect_recently_glossed(tmp_path, "us-equity", date(2026, 5, 25))

    assert "EIA" in glossed


def test_collect_glossed_bounded_lookback(tmp_path: Path) -> None:
    # Bound counts *loaded* trading days (mirrors u52 carryover). With
    # the default 3-day window and four consecutive archived days, the
    # 4th-most-recent day (and its unique term VIX) is never read.
    # today=Fri 2026-05-22 → walk loads Thu 21, Wed 20, Tue 19 (3 days);
    # Mon 18's VIX is outside the window.
    for day in (date(2026, 5, 19), date(2026, 5, 20), date(2026, 5, 21)):
        _write_archive(
            tmp_path,
            "us-equity",
            day,
            "EIA(에너지정보청) 재고.\n> **오늘의 결론**: 요약.\n",
        )
    _write_archive(
        tmp_path,
        "us-equity",
        date(2026, 5, 18),
        "VIX(변동성지수) 급등.\n> **오늘의 결론**: 요약.\n",
    )

    glossed = collect_recently_glossed(tmp_path, "us-equity", date(2026, 5, 22))

    assert "EIA" in glossed
    assert "VIX" not in glossed


def test_collect_glossed_zero_lookback_returns_empty(tmp_path: Path) -> None:
    _write_archive(
        tmp_path,
        "us-equity",
        date(2026, 5, 21),
        "EIA(에너지정보청) 재고.\n> **오늘의 결론**: 요약.\n",
    )

    assert collect_recently_glossed(tmp_path, "us-equity", date(2026, 5, 22), lookback=0) == set()


def test_collect_glossed_malformed_archive_degrades(tmp_path: Path) -> None:
    # A non-briefing markdown file with no gloss / callout contributes
    # nothing but does not raise.
    _write_archive(tmp_path, "us-equity", date(2026, 5, 21), "그냥 텍스트, 용어 없음.\n")

    assert collect_recently_glossed(tmp_path, "us-equity", date(2026, 5, 22)) == set()


def test_collect_glossed_unglossed_term_not_collected(tmp_path: Path) -> None:
    # A term that appeared WITHOUT a gloss yesterday is still "new" today
    # (the reader never had it explained) — must NOT be suppressed.
    _write_archive(
        tmp_path,
        "us-equity",
        date(2026, 5, 21),
        "EIA 주간 재고가 발표됐습니다.\n> **오늘의 결론**: 요약.\n",
    )

    glossed = collect_recently_glossed(tmp_path, "us-equity", date(2026, 5, 22))

    assert "EIA" not in glossed
