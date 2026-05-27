"""Reader-facing header enhancement + data-limited body.

``_enhance_reader_experience`` prepends the title / segment nav /
watermark / market-anchor / coverage badge / watchlist callout /
numeric-warning / glossary callout / 3-line summary header to the
synthesized body. ``_build_data_limited_body`` is the zero-input
shortcut body.

Moved verbatim from ``briefing/pipeline.py`` in the u83 decomposition;
behavior-preserving (move-only). ``_enhance_reader_experience`` /
``_render_timestamp_watermark`` keep their import path via re-export
from ``briefing/pipeline.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Final

from investo.briefing import numeric_self_check
from investo.briefing._assembly.summary_extraction import _build_summary_header
from investo.briefing._reader_enhance.coverage_badge import _render_coverage_badge
from investo.briefing.glossary import (
    audit_glossary_compliance,
    collect_recently_glossed,
    render_glossary_callout,
)
from investo.briefing.market_anchor import MarketAnchor, render_market_anchor_line
from investo.briefing.prompts import STAGE2_SECTION_HEADERS
from investo.briefing.segments import SEGMENT_LABELS, MarketSegment, SegmentCoverage
from investo.briefing.watchlist import WatchlistImpact, render_watchlist_impact
from investo.models import NormalizedItem
from investo.models.segments import SEGMENT_MARKET_TZ, SEGMENT_MARKET_TZ_LABEL

_SEGMENT_NAV_LABELS: Final[dict[MarketSegment, str]] = {
    "domestic-equity": "국내 증시",
    "us-equity": "미국 증시",
    "crypto": "크립토",
}


def _build_data_limited_body(target_date: date, segment: MarketSegment) -> str:
    """Return a concise six-section body for a segment with zero routed items."""
    label = SEGMENT_LABELS[segment]
    h1, h2, h3, h4, h5, h6 = STAGE2_SECTION_HEADERS
    return (
        f"{h1}\n{target_date.isoformat()} {label} 세그먼트는 정식 시황을 만들 만큼 "
        "검증된 입력 데이터가 수집되지 않았습니다. 오늘 문서는 시장 방향을 단정하지 않고, "
        "수집 공백과 확인할 항목만 짧게 남깁니다.\n\n"
        f"{h2}\n확인된 핵심 이슈 없음 — 해당 세그먼트의 뉴스/공시 입력이 충분하지 않아 "
        "주요 이벤트를 선별하지 않았습니다.\n\n"
        f"{h3}\n가격·수급 데이터 미확인 — 섹터, 자금 흐름, 상대강도 판단은 다음 정상 "
        "수집 이후로 보류합니다.\n\n"
        f"{h4}\n일정·거시 이벤트 미확인 — 세그먼트에 직접 연결되는 지표와 이벤트 근거가 "
        "부족합니다.\n\n"
        f"{h5}\n개별 종목·자산 선별 보류 — 충분한 가격/뉴스 근거 없이 티커를 나열하지 "
        "않습니다.\n\n"
        f"{h6}\n"
        "1. 데이터 수집 로그에서 실패한 소스와 성공했지만 0건을 반환한 소스를 구분합니다.\n"
        "2. 해당 시장의 대표 가격 지표와 주요 뉴스 소스가 회복됐는지 확인합니다.\n"
        "3. 다음 발행 전까지는 공신력 있는 원천 데이터로 가격과 이벤트를 별도 확인합니다.\n"
    )


def _segment_nav(target_date: date, segment: MarketSegment) -> str:
    filename = f"{target_date.isoformat()}.md"
    links: list[str] = []
    for target_segment, label in _SEGMENT_NAV_LABELS.items():
        href = (
            filename
            if target_segment == segment
            else f"../../../{target_segment}/{target_date.year}/{target_date.month:02d}/{filename}"
        )
        links.append(f"[{label}]({href})")
    return " | ".join(links)


def _render_watchlist_callout(impact: WatchlistImpact) -> str:
    """Render the site-channel watchlist callout (u28).

    Always emits a callout for the public site, including the ``unconfigured``
    onboarding nudge and the ``coverage_hold`` branch. The Telegram surface
    is rendered separately via :func:`render_watchlist_impact` with
    ``channel='telegram'`` and is allowed to skip these branches.
    """
    return f"> **내 관심 자산 영향**: {render_watchlist_impact(impact, channel='site')}\n"


def _render_timestamp_watermark(target_date: date, segment: MarketSegment) -> str:
    """Render the per-segment data-window watermark line.

    Format::

        **기준 시각**: 2026-05-06 KST · [2026-05-05T15:00Z, 2026-05-06T15:00Z)

    The local-clock label (KST / NY / UTC) is the segment's market
    clock — domestic-equity uses KST, us-equity uses America/New_York,
    crypto uses UTC. The bracketed window is the half-open UTC range
    used by the adapters that fed this segment, so the line reads
    "this is what trading day this is, and what slice of UTC it
    covered". Pure: no I/O, no clock reads — the value is a function
    of ``(target_date, segment)`` only.
    """
    market_tz = SEGMENT_MARKET_TZ[segment]
    tz_label = SEGMENT_MARKET_TZ_LABEL[segment]
    start_local = datetime.combine(target_date, time.min, tzinfo=market_tz)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(UTC)
    end_utc = end_local.astimezone(UTC)
    start_str = start_utc.strftime("%Y-%m-%dT%H:%MZ")
    end_str = end_utc.strftime("%Y-%m-%dT%H:%MZ")
    return f"**기준 시각**: {target_date.isoformat()} {tz_label} · [{start_str}, {end_str})"


def _enhance_reader_experience(
    body_markdown: str,
    *,
    target_date: date,
    segment: MarketSegment | None,
    sections: tuple[str, str, str, str, str, str],
    coverage: SegmentCoverage | None = None,
    watchlist_impact: WatchlistImpact | None = None,
    data_limited: bool = False,
    candidates: Sequence[NormalizedItem] | None = None,
    market_anchors: Sequence[MarketAnchor] = (),
    archive_root: Path | None = None,
) -> str:
    """Prepend the reader-facing title, segment nav, and 3-line brief."""
    if segment is None:
        return body_markdown

    label = SEGMENT_LABELS[segment]
    effective_data_limited = data_limited or (coverage is not None and coverage.status != "normal")
    summary_header = _build_summary_header(sections, data_limited=effective_data_limited)
    watermark = _render_timestamp_watermark(target_date, segment)
    # u49 — deterministic market anchor line (ATH / 52w / MTD / YTD).
    # Empty when no anchors landed (history fetch failed or empty
    # input); the helper returns "" so the f-string collapses cleanly.
    anchor_line = render_market_anchor_line(market_anchors)
    # u32 Step 2 — Stage 3 numeric self-check. Compare flaggable numeric
    # tokens in the body against the Stage 1 candidate haystack and
    # render a single-line warning callout when mismatches are found.
    numeric_warning_line = ""
    if candidates is not None:
        unverified = numeric_self_check.find_unverified(body_markdown, candidates)
        numeric_warning_line = numeric_self_check.render_warning_line(unverified)
    # u68 — cross-day suppression. Terms already glossed in this
    # segment's recent archives are dropped so the "처음 등장한 용어"
    # callout stays truthful within the recent window. A missing
    # archive_root (fresh repo / data-limited) yields an empty set →
    # today-only behavior (no regression).
    already_glossed = (
        collect_recently_glossed(archive_root, segment, target_date)
        if archive_root is not None
        else set()
    )
    glossary_line = render_glossary_callout(
        audit_glossary_compliance(
            body_markdown,
            segment=segment,
            already_glossed=already_glossed,
        )
    )
    header = (
        f"# {target_date.isoformat()} {label} 시황\n\n"
        f"{watermark}\n\n"
        f"{anchor_line}"
        f"**세그먼트**: {_segment_nav(target_date, segment)}\n\n"
        f"{_render_coverage_badge(coverage) if coverage is not None else ''}"
        f"{_render_watchlist_callout(watchlist_impact) if watchlist_impact is not None else ''}"
        f"{numeric_warning_line}"
        f"{glossary_line}"
        f"> **오늘의 결론**: {summary_header.conclusion}\n"
        f"> **핵심 동인**: {summary_header.driver}\n"
        f"> **주의할 점**: {summary_header.caution}\n\n"
    )
    return f"{header}{body_markdown}"


__all__ = [
    "_build_data_limited_body",
    "_enhance_reader_experience",
    "_render_timestamp_watermark",
    "_render_watchlist_callout",
    "_segment_nav",
]
