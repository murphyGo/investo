"""Static financial glossary and first-appearance compliance audit.

Cross-day suppression (u68)
---------------------------
``render_glossary_callout`` labels its terms "이번 시황에서 처음 등장한
용어" (terms appearing for the first time in *this* briefing). The
audit itself is single-document scoped, so without help every baseline
term re-fires the callout every day — making the "처음 등장한" claim
false on day 2+. :func:`collect_recently_glossed` walks the same
segment's recent trading-day archives (mirroring the u52
``carryover_parser`` walk shape) and returns the canonical keys already
glossed there; the pipeline feeds that set to
:func:`audit_glossary_compliance` so a once-explained term is dropped
from today's callout. The window is the recent ≤N trading days, so
"처음 등장한" is true *within that window*.

The walk is pure (caller-injected ``today``), bounded by
:data:`_MAX_CALENDAR_DAYS`, and degrades silently on missing/malformed/
unreadable archives — it never raises during a pipeline run. The module
takes ``archive_root`` as a parameter rather than importing the
publisher's path constant, preserving the briefing↔publisher module
boundary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
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


def audit_glossary_compliance(
    markdown: str,
    *,
    segment: str,
    already_glossed: set[str] | None = None,
) -> list[GlossaryGap]:
    """Return first-appearance baseline terms lacking a parenthetical gloss.

    ``already_glossed`` is the optional u68 cross-day suppression set:
    canonical keys (the :data:`BASELINE_GLOSSARY` keys, ASCII forms
    upper-cased) that were already glossed in the same segment's recent
    archives. Any term whose canonical key is in that set is dropped
    from the returned gaps — it is no longer "처음 등장한" within the
    recent window. ``None`` / empty set reproduces the pre-u68
    single-document behavior byte-for-byte (back-compat for existing
    callers and tests).
    """
    if not markdown:
        return []
    suppressed = already_glossed or set()
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
        seen_key = _canonical_key(canonical)
        if seen_key in seen:
            continue
        seen.add(seen_key)
        if seen_key in suppressed:
            continue
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


def _canonical_key(canonical: str) -> str:
    """Normalize a :data:`BASELINE_GLOSSARY` key to its dedup form.

    ASCII keys (ETF, EPS, VIX, futures ``*`` keys) are upper-cased so
    case variants collapse; Korean keys are returned verbatim. This is
    the single source of the suppression-set / ``seen``-set key shape so
    the two always agree.
    """
    return canonical.upper() if canonical.isascii() else canonical


# ---------------------------------------------------------------------------
# u68 — cross-day glossed-term suppression (archive walk)
# ---------------------------------------------------------------------------

DEFAULT_GLOSS_LOOKBACK_DAYS: Final[int] = 3
"""Default trading-day walk-back depth (mirrors u52 carryover: 3 days)."""

# Walk-back cap in calendar days — bounded above so a fresh repo with a
# single archived day cannot turn the scan into an O(weeks) walk. Mirrors
# ``carryover_parser._MAX_CALENDAR_DAYS``.
_MAX_CALENDAR_DAYS: Final[int] = 21

# A prior briefing's own glossary callout line — terms inside it were
# explicitly explained to the reader that day, so they count as glossed.
_CALLOUT_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*용어 가이드\*\*",
)


def collect_recently_glossed(
    archive_root: Path,
    segment: str,
    today: date,
    *,
    lookback: int = DEFAULT_GLOSS_LOOKBACK_DAYS,
) -> set[str]:
    """Canonical keys already glossed in the segment's recent archives.

    Walks back ``lookback`` *trading days* from ``today - 1`` (weekends
    silently skipped), reading
    ``archive_root/segment/YYYY/MM/YYYY-MM-DD.md``. For each archived
    day, a baseline term counts as "already glossed" when it appears
    either (a) immediately followed by a Korean parenthetical gloss
    (reusing :func:`_has_immediate_korean_gloss`) or (b) inside that
    day's ``> **용어 가이드**`` callout line.

    Pure: ``today`` is caller-injected. Bounded: stops at ``lookback``
    trading days or :data:`_MAX_CALENDAR_DAYS` calendar days, whichever
    comes first. Degrades silently: a missing directory, a missing or
    unreadable file, or a malformed archive yields no contribution and
    never raises — a fresh repo returns an empty set, so the caller
    falls back to today-only behavior.
    """
    capped = max(0, min(lookback, _MAX_CALENDAR_DAYS))
    if capped == 0:
        return set()

    glossed: set[str] = set()
    cursor = today - timedelta(days=1)
    calendar_used = 0
    trading_days_loaded = 0

    while trading_days_loaded < capped and calendar_used < _MAX_CALENDAR_DAYS:
        if _is_weekday(cursor):
            path = (
                archive_root
                / segment
                / f"{cursor.year:04d}"
                / f"{cursor.month:02d}"
                / f"{cursor.isoformat()}.md"
            )
            if path.is_file():
                try:
                    content = path.read_text(encoding="utf-8")
                except OSError:
                    content = ""
                if content:
                    glossed |= _glossed_terms_in(content)
                    trading_days_loaded += 1
        cursor -= timedelta(days=1)
        calendar_used += 1

    return glossed


def _is_weekday(day: date) -> bool:
    return day.weekday() < 5


def _glossed_terms_in(content: str) -> set[str]:
    """Canonical keys glossed in one archived briefing's markdown.

    A term is glossed when it appears with an immediate Korean paren
    gloss in the body, OR when it appears anywhere on a prior
    ``> **용어 가이드**`` callout line. Never raises.
    """
    callout_text = "\n".join(
        line for line in content.splitlines() if _CALLOUT_LINE_RE.match(line.strip())
    )
    glossed: set[str] = set()
    for canonical, pattern in _TERM_PATTERNS:
        key = _canonical_key(canonical)
        if key in glossed:
            continue
        # Body: term immediately followed by a Korean parenthetical.
        for match in pattern.finditer(content):
            if _has_immediate_korean_gloss(content[match.end() : match.end() + 24]):
                glossed.add(key)
                break
        if key in glossed:
            continue
        # Prior callout line: any occurrence counts (the callout's whole
        # purpose is to explain the term to the reader).
        if callout_text and pattern.search(callout_text) is not None:
            glossed.add(key)
    return glossed


__all__ = [
    "BASELINE_GLOSSARY",
    "DEFAULT_GLOSS_LOOKBACK_DAYS",
    "GlossaryGap",
    "audit_glossary_compliance",
    "collect_recently_glossed",
    "render_glossary_callout",
]
