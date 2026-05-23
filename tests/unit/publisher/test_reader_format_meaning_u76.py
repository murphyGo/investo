"""Unit tests for the u76 plain-language meaning-line reader aid.

Coverage map (per u76 plan Steps 1, 3, 4, 5 + AC-76.1..76.5):

* Contract (Step 1 / AC-76.1, AC-76.2):
  - exact marker ``> **그래서 의미는?** ``;
  - placement inside §②-§⑤ after the first block;
  - one line per section (duplicates dropped);
  - overlong body bounded to ``MEANING_MAX_CHARS`` at a word boundary;
  - idempotent re-run.
* Ticker-name clarity (Step 4 / AC-76.3): a meaning line carrying a
  ``ticker(name)`` form survives normalization unchanged; no name is
  fabricated by this deterministic pass.
* Compliance precedence (Step 3 / AC-76.5): a meaning line that contains
  P0 advice language is *not* silently paraphrased by the meaning pass —
  the downstream compliance scanner still sees and rejects it.
* glossary/carryover invariance (AC-76.4): u40 glossary callouts and a
  u68-style carryover block are untouched by the meaning pass.
"""

from __future__ import annotations

import pytest

from investo.publisher.compliance_language import (
    ComplianceLanguageError,
    scan_compliance,
)
from investo.publisher.reader_format import (
    MEANING_FALLBACK,
    MEANING_MARKER,
    MEANING_MAX_CHARS,
    apply_reader_format,
    normalize_meaning_lines,
)


def _doc(*section_bodies: str) -> str:
    """Build a minimal 6-section briefing body from per-section bodies."""
    headers = [
        "## ① 요약",
        "## ② 전일 핵심 이슈",
        "## ③ 섹터/수급 동향",
        "## ④ 지표·이벤트",
        "## ⑤ 주요 종목",
        "## ⑥ 오늘의 관전 포인트",
    ]
    parts: list[str] = ["# 2026-05-24 미국 증시 시황\n"]
    for header, body in zip(headers, section_bodies, strict=False):
        parts.append(f"{header}\n{body}\n")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Marker / placement / single-line
# ---------------------------------------------------------------------------


def test_meaning_line_in_eligible_section_is_kept() -> None:
    body2 = (
        "전일 미국장은 상승 마감했다.\n\n"
        f"{MEANING_MARKER}금리 흐름이 위험자산 선호를 좌우하는 국면입니다.\n"
    )
    text = _doc("요약", body2, "섹터", "지표", "종목", "관전")
    out = normalize_meaning_lines(text)
    assert f"{MEANING_MARKER}금리 흐름이 위험자산 선호를 좌우하는 국면입니다." in out


def test_meaning_line_dedupes_to_one_per_section() -> None:
    body3 = (
        "섹터 동향 문단.\n\n"
        f"{MEANING_MARKER}첫 번째 의미 라인입니다.\n\n"
        "추가 문단.\n\n"
        f"{MEANING_MARKER}두 번째 의미 라인입니다.\n"
    )
    text = _doc("요약", "이슈", body3, "지표", "종목", "관전")
    out = normalize_meaning_lines(text)
    # Section ③ body keeps only the first meaning line.
    section3 = out.split("## ④")[0].split("## ③")[1]
    assert section3.count(MEANING_MARKER) == 1
    assert "첫 번째 의미 라인입니다." in section3
    assert "두 번째 의미 라인입니다." not in section3
    # Surrounding prose ("추가 문단.") is preserved.
    assert "추가 문단." in section3


def test_meaning_line_idempotent() -> None:
    body4 = f"지표 발표 문단.\n\n{MEANING_MARKER}물가 지표가 통화정책 기대를 흔드는 변수입니다.\n"
    text = _doc("요약", "이슈", "섹터", body4, "종목", "관전")
    once = normalize_meaning_lines(text)
    twice = normalize_meaning_lines(once)
    assert once == twice


def test_overlong_meaning_body_bounded_at_word_boundary() -> None:
    long_body = "금리 상승 압력 " * 20  # well over 80 chars
    body2 = f"문단.\n\n{MEANING_MARKER}{long_body}\n"
    text = _doc("요약", body2, "섹터", "지표", "종목", "관전")
    out = normalize_meaning_lines(text)
    line = next(ln for ln in out.splitlines() if ln.startswith(MEANING_MARKER))
    visible = line[len(MEANING_MARKER) :]
    assert visible.endswith("...")
    # Visible (excluding the ... suffix) is within the cap.
    assert len(visible.rstrip(".")) <= MEANING_MAX_CHARS


def test_section_without_meaning_line_untouched() -> None:
    text = _doc("요약", "이슈 문단", "섹터", "지표", "종목", "관전")
    out = normalize_meaning_lines(text)
    # No meaning line fabricated for plain sections.
    assert MEANING_MARKER not in out


def test_section_six_is_not_eligible() -> None:
    # A meaning line wrongly placed in §⑥ is left as-is (not an eligible
    # section), but never fabricated there.
    text = _doc("요약", "이슈", "섹터", "지표", "종목", "관전 문단")
    out = normalize_meaning_lines(text)
    assert MEANING_MARKER not in out


def test_fallback_line_is_preserved() -> None:
    body2 = f"근거가 약한 문단.\n\n{MEANING_FALLBACK}\n"
    text = _doc("요약", body2, "섹터", "지표", "종목", "관전")
    out = normalize_meaning_lines(text)
    assert MEANING_FALLBACK in out


# ---------------------------------------------------------------------------
# AC-76.3 — ticker-name clarity (no fabrication by the deterministic pass)
# ---------------------------------------------------------------------------


def test_ticker_name_meaning_line_preserved() -> None:
    body5 = (
        "AAPL(애플), MSFT(마이크로소프트) 상승.\n\n"
        f"{MEANING_MARKER}AAPL(애플) 강세가 지수 상승을 견인한 흐름으로 관찰됩니다.\n"
    )
    text = _doc("요약", "이슈", "섹터", "지표", body5, "관전")
    out = normalize_meaning_lines(text)
    assert "AAPL(애플)" in out
    assert "AAPL(애플) 강세가 지수 상승을 견인한 흐름으로 관찰됩니다." in out


# ---------------------------------------------------------------------------
# AC-76.4 — glossary (u40) / carryover (u68) invariance
# ---------------------------------------------------------------------------


def test_glossary_callout_untouched() -> None:
    body2 = (
        "> **용어 가이드**: DXY(달러지수)\n\n"
        "전일 이슈 문단.\n\n"
        f"{MEANING_MARKER}달러 강세가 위험자산에 부담을 주는 국면으로 봅니다.\n"
    )
    text = _doc("요약", body2, "섹터", "지표", "종목", "관전")
    out = normalize_meaning_lines(text)
    assert "> **용어 가이드**: DXY(달러지수)" in out


def test_carryover_block_untouched() -> None:
    body2 = f"전일 이슈 문단.\n\n{MEANING_MARKER}연준 발표가 시장 방향을 좌우하는 변수입니다.\n"
    carryover = "\n## Watchlist Carryover\n\n| 항목 | 상태 |\n| --- | --- |\n| CPI | 미확인 |\n"
    text = _doc("요약", body2, "섹터", "지표", "종목", "관전") + carryover
    out = normalize_meaning_lines(text)
    assert "## Watchlist Carryover" in out
    assert "| CPI | 미확인 |" in out


# ---------------------------------------------------------------------------
# AC-76.5 — compliance precedence (no silent paraphrase)
# ---------------------------------------------------------------------------


def test_advice_meaning_line_rejected_by_compliance() -> None:
    body2 = f"전일 이슈 문단.\n\n{MEANING_MARKER}지금 매수 검토 구간으로 봅니다.\n"
    text = _doc("요약", body2, "섹터", "지표", "종목", "관전")
    out = normalize_meaning_lines(text)
    # The meaning pass does NOT paraphrase advice away — the line survives.
    assert f"{MEANING_MARKER}지금 매수 검토 구간으로 봅니다." in out
    # The compliance scanner is the gate that rejects it.
    with pytest.raises(ComplianceLanguageError):
        scan_compliance(out, "us-equity")


# ---------------------------------------------------------------------------
# Integration with apply_reader_format chain
# ---------------------------------------------------------------------------


def test_apply_reader_format_bounds_meaning_line() -> None:
    long_body = "변동성 확대 관찰 " * 20
    body2 = f"> **오늘의 결론**: 상승 [강세]\n\n문단.\n\n{MEANING_MARKER}{long_body}\n"
    text = _doc("요약", body2, "섹터", "지표", "종목", "관전")
    out = apply_reader_format(text, segment="us-equity")
    line = next(ln for ln in out.splitlines() if ln.startswith(MEANING_MARKER))
    visible = line[len(MEANING_MARKER) :]
    assert len(visible.rstrip(".")) <= MEANING_MAX_CHARS
