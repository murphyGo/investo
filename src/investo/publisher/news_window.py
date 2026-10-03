"""Pure reader projection of the exact consumed news observation windows."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC

from investo.models.coverage import SourceWindowCoverage
from investo.models.news_quality import NewsObservationQuality, NewsSourceObservation
from investo.models.news_window import NewsWindowConsumption, NewsWindowPlan
from investo.models.segments import MarketSegment


def news_observation_quality(
    plan: NewsWindowPlan,
    *,
    segment: MarketSegment,
    consumed: Sequence[NewsWindowConsumption],
    coverage: Sequence[SourceWindowCoverage],
) -> NewsObservationQuality | None:
    """Use the same terminal measurements for the reader and public history."""
    if not consumed:
        return None
    observed = {entry.source_name: entry for entry in coverage}
    rows: list[NewsSourceObservation] = []
    for receipt in sorted(consumed, key=lambda entry: entry.source_name):
        window = plan.windows[(receipt.source_name, segment)]
        source_coverage = observed.get(receipt.source_name)
        source_windows = tuple(
            value
            for (name, _), value in plan.windows.items()
            if name == receipt.source_name and value.fetch_required
        )
        matching = (
            source_coverage is not None
            and source_coverage.requested_start
            == min(row.requested_start for row in source_windows)
            and source_coverage.end_utc == max(row.end_utc for row in source_windows)
        )
        rows.append(
            NewsSourceObservation(
                source_name=receipt.source_name,
                requested_start=receipt.requested_start,
                end_utc=receipt.end_utc,
                gap_seconds=window.gap_seconds,
                completeness=(
                    source_coverage.completeness
                    if matching and source_coverage is not None
                    else "unknown"
                ),
            )
        )
    return NewsObservationQuality(price_reference_date=plan.target_date, sources=tuple(rows))


def render_news_observation(
    plan: NewsWindowPlan,
    *,
    segment: MarketSegment,
    consumed: Sequence[NewsWindowConsumption],
    coverage: Sequence[SourceWindowCoverage],
) -> str:
    """The envelope describes requested intervals, never worldwide coverage."""
    quality = news_observation_quality(plan, segment=segment, consumed=consumed, coverage=coverage)
    if quality is None:
        return ""
    labels = {"full": "조회 완료", "partial": "일부 조회", "unknown": "완전성 미확인"}
    rows: list[str] = []
    for source in quality.sources:
        start_label = source.requested_start.astimezone(UTC).isoformat(timespec="seconds")
        end_label = source.end_utc.astimezone(UTC).isoformat(timespec="seconds")
        gap = " · 최대 조회기간 이전에 미관측 구간 있음" if source.gap_seconds else ""
        rows.append(
            f"- {source.source_name}: {start_label} ~ {end_label} · "
            f"{labels[source.completeness]}{gap}"
        )
    return (
        f"**뉴스 관측기간**: {quality.requested_start.isoformat(timespec='seconds')} ~ "
        f"{quality.end_utc.isoformat(timespec='seconds')} (종료 미포함) · "
        f"가격 기준일 {plan.target_date.isoformat()}\n\n"
        f"소스 조회 상태: 완료 {quality.full_sources}개 · 일부 {quality.partial_sources}개 · "
        f"완전성 미확인 {quality.unknown_sources}개. "
        "소스별 조회 범위를 합쳐 표시했으며 전체 뉴스의 완전 수집을 뜻하지 않습니다. "
        "장후·주말 발표와 그 이전 종가 반응은 구분합니다.\n\n"
        '<details markdown="1"><summary>소스별 뉴스 관측 범위</summary>\n\n'
        + "\n".join(rows)
        + "\n\n지연·수정 보도의 재관측은 24시간 중첩 범위에서 수행합니다. "
        "그보다 늦게 도착한 보도는 놓칠 수 있습니다.\n\n</details>"
    )


def news_observation_matches(markdown: str, expected: str) -> bool:
    """A hidden canonical copy cannot stand in for the unique visible block."""
    without_comments = re.sub(r"<!--.*?(?:-->|\Z)", "", markdown, flags=re.DOTALL)
    lines: list[str] = []
    fence: tuple[str, int] | None = None
    for line in without_comments.splitlines():
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if match is not None:
            marker, suffix = match.groups()
            if fence is None:
                if marker[0] != "`" or "`" not in suffix:
                    fence = marker[0], len(marker)
                    continue
            elif marker[0] == fence[0] and len(marker) >= fence[1] and not suffix.strip():
                fence = None
                continue
        if fence is None:
            lines.append(line)
    visible = "\n".join(lines)
    return visible.count("**뉴스 관측기간**:") == 1 and expected in visible
