"""Home-page hero block surface (u29 site-discovery-v2).

The Home page (``site_docs/index.md``) ships a marker-bracketed hero
block ``<!-- u29 hero begin --> ... <!-- u29 hero end -->`` that the
publisher rewrites on every segmented publish. Inside the markers live
the per-segment "오늘의 결론" quote cards extracted from each segmented
briefing's first-viewport blockquote.

Move-only split out of the original ``site_index.py`` module (u82).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import quote

from investo._internal.briefing_extract import extract_conclusion as _extract_conclusion_chokepoint
from investo._internal.public_quality_language import project_public_quality_language
from investo.models import Briefing
from investo.models.segments import COVERAGE_STATUS_LABELS, MarketSegment
from investo.publisher.quality_consistency import parse_segment_status_block

from . import _constants
from ._blocks import _replace_marker_block
from ._constants import (
    _HERO_FALLBACK_TEXT,
    _SEGMENTS,
    HERO_BEGIN,
    HERO_END,
)
from .archive_sections import SegmentBundleState, _build_bundle_states, _site_segment_href


def update_index_hero(
    target_date: date,
    segment_briefings: dict[MarketSegment, Briefing],
    *,
    site_index_path: Path | None = None,
    bundle_states: tuple[SegmentBundleState, ...] | None = None,
    terminal_summaries: Mapping[MarketSegment, str] | None = None,
) -> Path:
    """Rewrite the marker-bracketed hero block on the Home page.

    The hero block is delimited by the constants :data:`HERO_BEGIN` and
    :data:`HERO_END`. Idempotent: running the function twice with the
    same inputs leaves the file byte-identical.
    """
    site_index_path = site_index_path if site_index_path is not None else _constants.SITE_INDEX_PATH
    if bundle_states is None:
        bundle_states = _build_bundle_states(
            target_date,
            archive_root=site_index_path.parent.parent / "archive",
            segment_briefings=segment_briefings,
        )
    hero_body = _render_hero_block(
        target_date,
        segment_briefings,
        bundle_states=bundle_states,
        terminal_summaries=terminal_summaries,
    )
    _replace_marker_block(
        site_index_path,
        begin_marker=HERO_BEGIN,
        end_marker=HERO_END,
        replacement=hero_body,
        content_transform=_migrate_home,
    )
    return site_index_path


def extract_conclusion(rendered_markdown: str) -> str:
    """Pull the first ``> **오늘의 결론**:`` line from a rendered briefing.

    Thin wrapper over :func:`investo.briefing.extract.extract_conclusion`
    that substitutes the surface's hero-fallback text on miss. Kept as
    a public entry point because the orchestrator and tests historically
    imported this function name from this module; the behavior is
    unchanged after the DEBT-060 consolidation 2026-05-08.
    """
    value = _extract_conclusion_chokepoint(rendered_markdown)
    if value is None:
        return _HERO_FALLBACK_TEXT
    return project_public_quality_language(value)


def _render_hero_block(
    target_date: date,
    segment_briefings: dict[MarketSegment, Briefing],
    *,
    bundle_states: tuple[SegmentBundleState, ...] | None = None,
    terminal_summaries: Mapping[MarketSegment, str] | None = None,
) -> str:
    iso = target_date.isoformat()
    cards: list[str] = []
    states = bundle_states or tuple(
        SegmentBundleState(segment, target_date, segment in segment_briefings, "")
        for segment in _SEGMENTS
    )
    quick: list[str] = []
    for state in states:
        segment = state.segment
        label = escape(state.label)
        briefing = segment_briefings.get(segment)
        generated = state.generated and briefing is not None
        if generated:
            assert briefing is not None
            status = parse_segment_status_block(briefing.rendered_markdown, segment).status
            quality = (
                f"근거 상태: {COVERAGE_STATUS_LABELS[status]}" if status else "근거 상태 미확인"
            )
            summary = (
                terminal_summaries[segment]
                if terminal_summaries is not None and segment in terminal_summaries
                else extract_conclusion(briefing.rendered_markdown)
            )
            summary_mode = (
                "0" if terminal_summaries is not None and segment in terminal_summaries else "span"
            )
            detail = (
                f'<p class="investo-market-summary" markdown="{summary_mode}">{escape(summary)}</p>'
            )
            date_label = f"발행 {iso}"
            href = (
                "archive/" + quote(state.href, safe="/-.")
                if state.href
                else _site_segment_href(target_date, segment)
            )
            link_label = f"{state.label} {iso} 시황 읽기"
            quality_key: str = status or "unknown"
        else:
            quality, quality_key = "근거 상태 해당 없음", "absent"
            date_label = f"{iso} 미발행"
            if state.fallback_date is not None and state.fallback_href is not None:
                prior = state.fallback_date.isoformat()
                detail = f'<p markdown="0">최근 발행 {prior}</p>'
                href = "archive/" + quote(state.fallback_href, safe="/-.")
                link_label = f"{state.label} {prior} 이전 시황 읽기"
            else:
                detail = '<p markdown="0">이전 발행 없음</p>'
                href = f"archive/{segment}/index.md"
                link_label = f"{state.label} 아카이브 보기"
        quick.append(f'<a href="#{segment}">{label}</a>')
        cards.append(
            f'<article id="{segment}" markdown="1" class="investo-market-card" '
            f'data-segment="{segment}" '
            f'data-target-date="{iso}" data-generated="{str(generated).lower()}" '
            f'data-quality="{quality_key}">\n'
            f'<h2 data-investo-field="market" markdown="0">{label}</h2>\n'
            '<p class="investo-market-date" data-investo-field="date" markdown="0">'
            f"{date_label}</p>\n"
            '<p class="investo-market-status" data-investo-field="quality" markdown="0">'
            f"{quality}</p>\n"
            f"{detail}\n\n[{link_label}]({href}){{ .investo-market-link }}\n\n</article>"
        )
    return (
        f"# 최신 발행 시황\n\n묶음 기준일 **{iso}** · 국내 증시 · 미국 증시 · 크립토\n\n"
        '<section class="investo-home" aria-label="최신 발행 시장별 시황" markdown="1">\n'
        '<nav class="investo-home-quick-links" aria-label="시장 바로가기">'
        + "".join(quick)
        + '</nav>\n<div class="investo-market-grid" markdown="1">\n'
        + "\n".join(cards)
        + "</div>\n</section>\n\n"
        "[전체 아카이브](archive/index.md) · [운영 원칙·면책](about.md) · "
        "[주차별 회고](archive/weekly/index.md)\n"
    )


def _migrate_home(content: str) -> str:
    """Remove only the old owner-controlled intro/sections, preserve footer and unknown sections."""
    intro = (
        "# Investo — 데일리 시황\n\n"
        "매일 KST 평일 07:00 (미국장 마감 직후) + 토요일 09:00 (전일 미국장\n"
        "요약)에 국내 증시·미국 증시·크립토 시황을 한국어로 자동 생성·게시합니다.\n\n"
    )
    if content.startswith(intro):
        content = content[len(intro) :]
    begin = content.find(HERO_BEGIN)
    end = content.find(HERO_END, begin + len(HERO_BEGIN)) if begin >= 0 else -1
    if begin >= 0 and end >= 0:
        end += len(HERO_END)
        return (
            _remove_legacy_sections(content[:begin])
            + content[begin:end]
            + _remove_legacy_sections(content[end:])
        )
    return _remove_legacy_sections(content)


def _remove_legacy_sections(content: str) -> str:
    for heading in ("## 최신 시황", "## 사이트 안내"):
        start = 0 if content.startswith(heading + "\n") else content.find("\n" + heading + "\n")
        if start < 0:
            continue
        candidates = [
            pos
            for marker in ("\n## ", "\n---\n")
            if (pos := content.find(marker, start + len(heading) + 2)) >= 0
        ]
        end = min(candidates) if candidates else len(content)
        content = content[:start] + content[end:]
    return content
