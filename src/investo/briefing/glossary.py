"""Static financial glossary and first-appearance compliance audit."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

BASELINE_GLOSSARY: Final[dict[str, str]] = {
    "CPI": "소비자물가",
    "PPI": "생산자물가",
    "PCE": "개인소비지출",
    "NFP": "고용지표",
    "EIA": "에너지정보청",
    "DXY": "달러지수",
    "ISM": "제조업지수",
    "JOLTS": "구인보고서",
    "FOMC": "연준회의",
    "FRB": "연준",
    "FFR": "기준금리",
    "QT": "양적긴축",
    "QE": "양적완화",
    "ESM*": "미니S&P선물",
    "NQU*": "나스닥선물",
    "CLM*": "원유선물",
    "GCM*": "금선물",
    "VIX": "변동성지수",
    "ETF": "상장지수펀드",
    "EPS": "주당순이익",
    "PER": "주가수익비율",
    "옵션만기": "옵션정산일",
    "콜옵션": "매수권리",
    "풋옵션": "매도권리",
    "프로그램매매": "기관자동주문",
    "숏커버링": "공매도상환",
    "배당락": "배당권리소멸",
    "자사주매입": "회사주식매수",
    "공매도": "차입매도",
    "시간외거래": "장외거래",
    "스테이킹": "예치보상",
    "토큰언락": "잠금해제",
    "시가총액": "시장가치",
    "거래대금": "거래총액",
}

_PAREN_GLOSS_RE: Final[re.Pattern[str]] = re.compile(r"^\s*\(([^)]*[가-힣][^)]*)\)")


@dataclass(frozen=True, slots=True)
class GlossaryGap:
    """One first-appearance glossary term missing an immediate Korean gloss."""

    segment: str
    term: str
    gloss: str


def audit_glossary_compliance(markdown: str, *, segment: str) -> list[GlossaryGap]:
    """Return first-appearance baseline terms lacking a parenthetical gloss."""
    if not markdown:
        return []
    matches: list[tuple[int, int, str, str]] = []
    for canonical, pattern in _TERM_PATTERNS:
        for match in pattern.finditer(markdown):
            matched_term = match.group(0)
            matches.append((match.start(), match.end(), canonical, matched_term))
    if not matches:
        return []

    gaps: list[GlossaryGap] = []
    seen: set[str] = set()
    for _, end, canonical, matched_term in sorted(matches, key=lambda item: item[0]):
        seen_key = canonical.upper() if canonical.isascii() else canonical
        if seen_key in seen:
            continue
        seen.add(seen_key)
        if _has_immediate_korean_gloss(markdown[end : end + 24]):
            continue
        gaps.append(
            GlossaryGap(
                segment=segment,
                term=matched_term,
                gloss=BASELINE_GLOSSARY[canonical],
            )
        )
    return gaps


def render_glossary_callout(gaps: list[GlossaryGap]) -> str:
    """Render the brief-header glossary callout for missing first-use glosses."""
    if not gaps:
        return ""
    capped = gaps[:5]
    rendered = ", ".join(f"{gap.term}({gap.gloss})" for gap in capped)
    suffix = f" 외 {len(gaps) - len(capped)}건" if len(gaps) > len(capped) else ""
    return f"> **용어 가이드**: 이번 시황에서 처음 등장한 용어 — {rendered}{suffix}\n"


def _pattern_for(term: str) -> str:
    if term.endswith("*"):
        prefix = re.escape(term[:-1])
        return rf"(?<![A-Za-z0-9]){prefix}[A-Z0-9]+(?![A-Za-z0-9])"
    escaped = re.escape(term)
    if term.isascii():
        return rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
    return rf"(?<![가-힣]){escaped}(?![가-힣])"


_TERM_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = tuple(
    (term, re.compile(_pattern_for(term)))
    for term in sorted(BASELINE_GLOSSARY, key=len, reverse=True)
)


def _has_immediate_korean_gloss(text_after_term: str) -> bool:
    return _PAREN_GLOSS_RE.match(text_after_term) is not None


__all__ = [
    "BASELINE_GLOSSARY",
    "GlossaryGap",
    "audit_glossary_compliance",
    "render_glossary_callout",
]
