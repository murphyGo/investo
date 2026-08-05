"""Neutral deterministic six-section fallback shared by briefing/publisher."""

from __future__ import annotations

from datetime import date
from typing import Final

from investo._internal.disclaimer import DISCLAIMER, DISCLAIMER_CRYPTO, append_disclaimer
from investo.models.briefing import Briefing
from investo.models.segments import SEGMENT_LABELS, MarketSegment

_SECTION_HEADERS: Final[tuple[str, str, str, str, str, str]] = (
    "## ① 요약",
    "## ② 전일 핵심 이슈",
    "## ③ 섹터/수급 동향",
    "## ④ 지표·이벤트",
    "## ⑤ 주요 종목",
    "## ⑥ 오늘의 관전 포인트",
)


def _section_values(target_date: date, segment: MarketSegment) -> tuple[str, ...]:
    label = SEGMENT_LABELS[segment]
    return (
        f"{target_date.isoformat()} {label} 세그먼트는 정식 시황을 만들 만큼 "
        "검증된 입력 데이터가 수집되지 않았습니다. 오늘 문서는 시장 방향을 단정하지 않고, "
        "수집 공백과 확인할 항목만 짧게 남깁니다.",
        "확인된 핵심 이슈 없음 — 해당 세그먼트의 뉴스/공시 입력이 충분하지 않아 "
        "주요 이벤트를 선별하지 않았습니다.",
        "가격·수급 데이터 미확인 — 섹터, 자금 흐름, 상대강도 판단은 다음 정상 "
        "수집 이후로 보류합니다.",
        "일정·거시 이벤트 미확인 — 세그먼트에 직접 연결되는 지표와 이벤트 근거가 부족합니다.",
        "개별 종목·자산 선별 보류 — 충분한 가격/뉴스 근거 없이 티커를 나열하지 않습니다.",
        "1. 데이터 수집 로그에서 실패한 소스와 성공했지만 0건을 반환한 소스를 구분합니다.\n"
        "2. 해당 시장의 대표 가격 지표와 주요 뉴스 소스가 회복됐는지 확인합니다.\n"
        "3. 다음 발행 전까지는 공신력 있는 원천 데이터로 가격과 이벤트를 별도 확인합니다.",
    )


def build_data_limited_body(target_date: date, segment: MarketSegment) -> str:
    """Return the canonical base six-H2 Markdown without reader assembly."""

    values = _section_values(target_date, segment)
    return (
        "\n\n".join(
            f"{heading}\n{value}" for heading, value in zip(_SECTION_HEADERS, values, strict=True)
        )
        + "\n"
    )


def build_data_limited_briefing(target_date: date, segment: MarketSegment) -> Briefing:
    """Build a no-I/O/no-LLM minimal source for the normal finalizer."""

    values = _section_values(target_date, segment)
    first_viewport = (
        "> **오늘의 결론**: 검증된 입력이 부족해 시장 방향 판단을 보류합니다.\n"
        "> **핵심 동인**: 대표 가격과 주요 뉴스의 수집 공백을 우선 확인해야 합니다.\n"
        "> **주의할 점**: 다음 정상 수집 전까지 정밀 수치와 방향을 단정하지 않습니다.\n\n"
    )
    diagnostics = (
        "\n<details><summary>수집/품질 진단</summary>\n"
        "데이터 부족 안내: 검증된 공개 입력 부족으로 최소 문서를 사용했습니다.\n"
        "</details>\n"
    )
    markdown = append_disclaimer(
        first_viewport + build_data_limited_body(target_date, segment) + diagnostics,
        segment,
    )
    return Briefing(
        target_date=target_date,
        market_summary=values[0],
        key_issues=values[1],
        sector_flow=values[2],
        indicators_events=values[3],
        notable_tickers=values[4],
        today_watch=values[5],
        disclaimer=DISCLAIMER_CRYPTO if segment == "crypto" else DISCLAIMER,
        rendered_markdown=markdown,
    )


__all__ = ["build_data_limited_body", "build_data_limited_briefing"]
