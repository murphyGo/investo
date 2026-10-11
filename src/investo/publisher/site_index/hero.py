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
from pathlib import Path

from investo._internal.briefing_extract import extract_conclusion as _extract_conclusion_chokepoint
from investo._internal.event_public_text import document_excerpt, markdown_literal
from investo._internal.public_quality_language import project_public_quality_language
from investo.models.event_document import PublicEditionView, ReadablePublicDocument
from investo.models.segments import SEGMENT_LABELS, MarketSegment

from ._blocks import _escape_inline, _replace_marker_block
from ._constants import (
    _HERO_FALLBACK_TEXT,
    _SEGMENTS,
    HERO_BEGIN,
    HERO_END,
    SITE_INDEX_PATH,
)
from .archive_sections import _site_segment_href


def update_index_hero(
    target_date: date,
    segment_briefings: Mapping[MarketSegment, ReadablePublicDocument],
    *,
    site_index_path: Path = SITE_INDEX_PATH,
) -> Path:
    """Rewrite the marker-bracketed hero block on the Home page.

    The hero block is delimited by the constants :data:`HERO_BEGIN` and
    :data:`HERO_END`. Idempotent: running the function twice with the
    same inputs leaves the file byte-identical.
    """
    hero_body = _render_hero_block(target_date, segment_briefings)
    _replace_marker_block(
        site_index_path,
        begin_marker=HERO_BEGIN,
        end_marker=HERO_END,
        replacement=hero_body,
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
    segment_briefings: Mapping[MarketSegment, ReadablePublicDocument],
) -> str:
    iso = target_date.isoformat()
    cards: list[str] = []
    for segment in _SEGMENTS:
        briefing = segment_briefings.get(segment)
        if briefing is None:
            continue
        label = SEGMENT_LABELS[segment]
        href = _site_segment_href(target_date, segment)
        conclusion = (
            document_excerpt(briefing)
            if isinstance(briefing, PublicEditionView)
            else extract_conclusion(briefing.rendered_markdown)
        )
        # Markdown blockquote cards keep the hero readable both when
        # mkdocs renders the page AND when GitHub displays the raw .md
        # — important for index reviewers using the GitHub web UI.
        if isinstance(briefing, PublicEditionView):
            digests = {d.event_id: d.text for d in briefing.edition.digests}
            events = "\n".join(
                f"- {markdown_literal(digests.get(e.event_id, e.headline))}"
                for e in briefing.edition.events
            )
            cards.append(f"### [{label}]({href})\n\n{events or markdown_literal(conclusion)}\n")
            if briefing.edition.availability.status == "source_limited":
                cards.append("출처 수집이 제한되어 중요 사건을 판단하기 어렵습니다.\n")
        else:
            cards.append(f"### [{label}]({href})\n\n> {_escape_inline(conclusion)}\n")
    body_cards = "\n".join(cards)
    return (
        f"# 오늘의 시황 ({iso})\n\n"
        "오늘 발행된 시장별 주요 내용을 요약합니다. "
        "각 카드를 눌러 전체 시황으로 이동할 수 있습니다.\n\n"
        f"{body_cards}\n"
        "[전체 Archive 보기](archive/index.md) · "
        "[About](about.md) · "
        "[주차별 회고](archive/weekly/index.md)\n"
    )
