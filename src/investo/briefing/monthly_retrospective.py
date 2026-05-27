"""Deterministic monthly retrospective renderer."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from investo.briefing.action_tag import (
    ACTION_TAGS,
    DEFAULT_ACTION_TAG,
    LEGACY_TAG_ALIASES,
    ActionTag,
)
from investo.briefing.extract import extract_conclusion
from investo.briefing.segments import SEGMENT_LABELS, MarketSegment

_TAG_RE: Final[re.Pattern[str]] = re.compile(
    r"\[(?:관망|변동성↑|강세|약세|혼조"
    r"|상승 관찰|하락 관찰|혼재|변동성 확대"
    r"|데이터부족)\]$"
)
_TICKER_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Z0-9.])[A-Z][A-Z0-9.]{1,9}(?![A-Z0-9.])|(?<!\d)\d{6}(?!\d)"
)
_WEEKLY_STEM_RE: Final[re.Pattern[str]] = re.compile(r"^(\d{4})-W(\d{2})$")
_SEGMENT_ORDER: Final[tuple[MarketSegment, ...]] = (
    "domestic-equity",
    "us-equity",
    "crypto",
)


@dataclass(frozen=True, slots=True)
class MonthlyEntry:
    day: date
    segment: MarketSegment
    conclusion: str
    action_tag: ActionTag


def render_monthly_retrospective(year: int, month: int, *, archive_root: Path) -> str:
    """Render a byte-stable monthly retrospective markdown page."""
    entries = _load_month_entries(year, month, archive_root=archive_root)
    title = f"{year}년 {month:02d}월 회고"
    if len({entry.day for entry in entries}) < 7:
        return (
            f"# {title}\n\n"
            "> 데이터 부족 — 다음 달부터 회고 가능\n\n"
            "월간 회고를 만들기에는 보관된 일별 시황이 아직 부족합니다.\n"
        )
    tag_counts = Counter(entry.action_tag for entry in entries)
    ticker_counts: Counter[str] = Counter()
    for entry in entries:
        ticker_counts.update(_extract_tickers(entry.conclusion))

    lines: list[str] = [
        f"# {title}",
        "",
        "## 일별 결론",
        "",
        "| 날짜 | 세그먼트 | 결론 | 태그 |",
        "|------|----------|------|------|",
    ]
    for entry in entries:
        lines.append(
            "| "
            f"{entry.day.isoformat()} | {SEGMENT_LABELS[entry.segment]} | "
            f"{_escape_cell(_strip_action_tag(entry.conclusion))} | {entry.action_tag} |"
        )
    lines.extend(["", "## 결론 톤 분포", "", "| 태그 | 비율 | 표본 |", "|------|------|------|"])
    total = sum(tag_counts.values())
    for tag in sorted(ACTION_TAGS):
        count = tag_counts.get(tag, 0)
        pct = (count / total * 100) if total else 0.0
        lines.append(f"| {tag} | {pct:.1f}% | {count} |")
    lines.extend(["", "## 자주 언급된 티커·테마", ""])
    if ticker_counts:
        for ticker, count in ticker_counts.most_common(5):
            lines.append(f"- {ticker}: {count}회")
    else:
        lines.append("- 집계 가능한 티커가 없습니다.")
    weekly_links = _weekly_links(year, month, archive_root=archive_root)
    lines.extend(["", "## 주차별 회고", ""])
    lines.extend(weekly_links or ["- 해당 월의 주차별 회고가 아직 없습니다."])
    lines.append("")
    return "\n".join(lines)


def month_has_archive_days(year: int, month: int, *, archive_root: Path) -> bool:
    return bool(_load_month_entries(year, month, archive_root=archive_root))


def _load_month_entries(year: int, month: int, *, archive_root: Path) -> list[MonthlyEntry]:
    entries: list[MonthlyEntry] = []
    for segment in _SEGMENT_ORDER:
        segment_dir = archive_root / segment / f"{year:04d}" / f"{month:02d}"
        for path in sorted(segment_dir.glob("*.md")):
            try:
                day = date.fromisoformat(path.stem)
            except ValueError:
                continue
            try:
                body = path.read_text(encoding="utf-8")
            except OSError:
                continue
            conclusion = extract_conclusion(body) or "(결론 인용을 추출하지 못함)"
            entries.append(
                MonthlyEntry(
                    day=day,
                    segment=segment,
                    conclusion=conclusion,
                    action_tag=_extract_action_tag(conclusion),
                )
            )
    return sorted(entries, key=lambda item: (item.day, _SEGMENT_ORDER.index(item.segment)))


def _extract_action_tag(conclusion: str) -> ActionTag:
    # u56 — legacy stance tags in pre-cutover archive files are
    # normalised to the observation set via ``LEGACY_TAG_ALIASES``.
    match = _TAG_RE.search(conclusion.strip())
    if match is None:
        return DEFAULT_ACTION_TAG
    tag = match.group(0)
    if tag in ACTION_TAGS:
        return tag
    aliased = LEGACY_TAG_ALIASES.get(tag)
    if aliased is not None:
        return aliased
    return DEFAULT_ACTION_TAG


def _strip_action_tag(conclusion: str) -> str:
    return _TAG_RE.sub("", conclusion.strip()).strip()


def _extract_tickers(text: str) -> list[str]:
    return [match.group(0) for match in _TICKER_RE.finditer(text)]


def _weekly_links(year: int, month: int, *, archive_root: Path) -> list[str]:
    weekly_root = archive_root / "weekly"
    if not weekly_root.exists():
        return []
    links: list[str] = []
    for path in sorted(weekly_root.glob("*.md")):
        if path.name == "index.md":
            continue
        if _weekly_page_overlaps_month(path.stem, year=year, month=month):
            links.append(f"- [{path.stem}](../weekly/{path.name})")
    return links


def _weekly_page_overlaps_month(stem: str, *, year: int, month: int) -> bool:
    match = _WEEKLY_STEM_RE.fullmatch(stem)
    if match is None:
        return False
    iso_year = int(match.group(1))
    iso_week = int(match.group(2))
    try:
        week_start = date.fromisocalendar(iso_year, iso_week, 1)
    except ValueError:
        return False
    return any(
        (day.year, day.month) == (year, month)
        for day in (week_start + timedelta(days=offset) for offset in range(5))
    )


def _escape_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


__all__ = [
    "MonthlyEntry",
    "month_has_archive_days",
    "render_monthly_retrospective",
]
