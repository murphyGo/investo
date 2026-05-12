"""Forecast accuracy aggregation for closed-set action tags."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from investo.briefing.segments import SEGMENT_LABELS, MarketSegment

# u56 — both legacy stance tags and the new observation tags resolve to
# the same directional buckets so historical forecast-log entries from
# pre-2026-05-13 archives still aggregate cleanly.
_DIRECTIONAL_TAGS: Final[set[str]] = {
    # legacy stance set (pre-u56 archive entries)
    "[강세]",
    "[약세]",
    "[혼조]",
    "[변동성↑]",
    # new observation set (u56 onwards)
    "[상승 관찰]",
    "[하락 관찰]",
    "[혼재]",
    "[변동성 확대]",
}
_NA_TAGS: Final[set[str]] = {"[관망]", "[데이터부족]"}


@dataclass(frozen=True, slots=True)
class PriceMove:
    pct_change: float
    volatility_percentile: float | None = None


@dataclass(frozen=True, slots=True)
class AccuracyRow:
    segment: MarketSegment
    action_tag: str
    sample_size: int
    hits: int
    na: bool = False

    @property
    def hit_rate(self) -> float | None:
        if self.na or self.sample_size == 0:
            return None
        return self.hits / self.sample_size


@dataclass(frozen=True, slots=True)
class AccuracyReport:
    window_days: int
    rows: tuple[AccuracyRow, ...]


@dataclass(frozen=True, slots=True)
class ForecastEntry:
    target_date: date
    segment: MarketSegment
    action_tag: str


PriceLookup = Callable[[MarketSegment, date, int], PriceMove | None]


def compute_accuracy(
    window_days: int,
    *,
    log_path: Path,
    price_lookup: PriceLookup,
    today: date | None = None,
) -> AccuracyReport:
    """Compute hit-rate rows from the forecast log and injected price lookup."""
    entries = _load_entries(log_path)
    if not entries:
        return AccuracyReport(window_days=window_days, rows=())
    end_day = today if today is not None else max(entry.target_date for entry in entries)
    start_day = end_day - timedelta(days=window_days - 1)
    grouped: dict[tuple[MarketSegment, str], list[bool | None]] = defaultdict(list)
    for entry in entries:
        target_date = entry.target_date
        if target_date < start_day or target_date > end_day:
            continue
        segment = entry.segment
        tag = entry.action_tag
        if tag in _NA_TAGS:
            grouped[(segment, tag)].append(None)
            continue
        move = price_lookup(segment, target_date, window_days)
        if move is None:
            continue
        grouped[(segment, tag)].append(_is_hit(tag, move))
    rows: list[AccuracyRow] = []
    for (segment, tag), values in sorted(
        grouped.items(),
        key=lambda item: (item[0][0], item[0][1]),
    ):
        if tag in _NA_TAGS:
            rows.append(
                AccuracyRow(segment=segment, action_tag=tag, sample_size=0, hits=0, na=True)
            )
            continue
        scored = [value for value in values if value is not None]
        rows.append(
            AccuracyRow(
                segment=segment,
                action_tag=tag,
                sample_size=len(scored),
                hits=sum(1 for value in scored if value),
            )
        )
    return AccuracyReport(window_days=window_days, rows=tuple(rows))


def render_accuracy_page(reports: tuple[AccuracyReport, ...]) -> str:
    """Render the public forecast accuracy page."""
    lines = [
        "# 예측 정확도",
        "",
        "과거 시황의 닫힌 액션 태그를 이후 가격 움직임과 대조한 롤링 지표입니다.",
        "표본 크기가 작으면 방향성 검증보다 누적 상태 확인용으로 봐야 합니다.",
        "",
    ]
    if not any(report.rows for report in reports):
        lines.extend(["표본 누적 중 — 첫 30일 후 산출", ""])
        return "\n".join(lines)
    for report in reports:
        lines.extend(
            [
                f"## 최근 {report.window_days}일",
                "",
                "| 세그먼트 | 태그 | 적중률 | 표본 크기 |",
                "|----------|------|--------|-----------|",
            ]
        )
        if not report.rows:
            lines.append("| 전체 | - | 표본 누적 중 | 0 |")
        for row in report.rows:
            rate = "N/A" if row.hit_rate is None else f"{row.hit_rate * 100:.1f}%"
            lines.append(
                f"| {SEGMENT_LABELS[row.segment]} | {row.action_tag} | {rate} | {row.sample_size} |"
            )
        lines.append("")
    return "\n".join(lines)


def _load_entries(path: Path) -> list[ForecastEntry]:
    if not path.exists():
        return []
    rows: list[ForecastEntry] = []
    with path.open("r", encoding="utf-8") as fp:
        for raw_line in fp:
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            row = _parse_entry(parsed)
            if row is not None:
                rows.append(row)
    return rows


def _parse_entry(payload: object) -> ForecastEntry | None:
    if not isinstance(payload, dict):
        return None
    try:
        target_date = date.fromisoformat(str(payload["target_date"]))
    except (KeyError, ValueError):
        return None
    segment = payload.get("segment")
    tag = payload.get("action_tag")
    if segment not in SEGMENT_LABELS or not isinstance(tag, str):
        return None
    if tag not in _DIRECTIONAL_TAGS and tag not in _NA_TAGS:
        return None
    return ForecastEntry(target_date=target_date, segment=segment, action_tag=tag)


def _is_hit(tag: str, move: PriceMove) -> bool:
    # u56 — observation set + legacy stance set both map to the same
    # quantitative hit predicate (directional buckets unchanged).
    if tag in ("[강세]", "[상승 관찰]"):
        return move.pct_change >= 0.0
    if tag in ("[약세]", "[하락 관찰]"):
        return move.pct_change <= 0.0
    if tag in ("[혼조]", "[혼재]"):
        return abs(move.pct_change) <= 1.0
    if tag in ("[변동성↑]", "[변동성 확대]"):
        return (move.volatility_percentile or 0.0) >= 0.8
    return False


__all__ = [
    "AccuracyReport",
    "AccuracyRow",
    "ForecastEntry",
    "PriceLookup",
    "PriceMove",
    "compute_accuracy",
    "render_accuracy_page",
]
