"""Stage 2 evidence rendering — grouped / unassigned / required-macro.

These renderers produce the *classified-evidence bullet blocks* that
feed the Stage 2 LLM prompt (and the cap helper used by lineage). They
are LLM-input rendering, NOT the reader-facing output blocks (those
live in :mod:`investo.briefing._reader_enhance`).

Moved verbatim from ``briefing/pipeline.py`` in the u83 decomposition;
behavior-preserving (move-only).
"""

from __future__ import annotations

from typing import Final

from investo.briefing._assembly.prompt_fields import (
    _STAGE2_URL_MAX_CHARS,
    _render_prompt_url,
    _truncate_prompt_field,
)
from investo.briefing._core.section_planning import SectionPlan, StoryMetadata, story_identity
from investo.models import NormalizedItem
from investo.models.macro import macro_prompt_payload
from investo.models.segments import MarketSegment

# Stage 2 receives the richer prompt: segment rules, recent context,
# carryover, bundle context, and the classified evidence rows. Keep the
# evidence block materially smaller than Stage 1 so high-volume days do
# not spend the whole cron window synthesizing a single segment.
_MAX_STAGE2_ITEMS_TOTAL: Final[int] = 48
_MAX_STAGE2_ITEMS_PER_SECTION: Final[int] = 14
_MAX_STAGE2_UNASSIGNED_ITEMS: Final[int] = 8
_CRYPTO_MAX_STAGE2_ITEMS_TOTAL: Final[int] = 32
_CRYPTO_MAX_STAGE2_ITEMS_PER_SECTION: Final[int] = 8
_CRYPTO_MAX_STAGE2_UNASSIGNED_ITEMS: Final[int] = 4
_STAGE2_RETRY_FEEDBACK_MAX_CHARS: Final[int] = 360
_STAGE2_TITLE_MAX_CHARS: Final[int] = 180
_STAGE2_SUMMARY_MAX_CHARS: Final[int] = 260


def _render_grouped_sections(
    items_by_section: dict[int, tuple[NormalizedItem, ...]],
    *,
    story_metadata: dict[str, StoryMetadata] | None = None,
    segment: MarketSegment | None = None,
) -> str:
    """Render the per-section items as bullet text for Stage 2 prompt.

    Sections without items emit ``(no items)`` so the LLM sees an
    explicit "empty" signal rather than a missing entry — Stage 2's
    system prompt instructs it to write ``특이사항 없음`` for empty
    sections.
    """
    parts: list[str] = []
    max_total = _CRYPTO_MAX_STAGE2_ITEMS_TOTAL if segment == "crypto" else _MAX_STAGE2_ITEMS_TOTAL
    max_per_section = (
        _CRYPTO_MAX_STAGE2_ITEMS_PER_SECTION
        if segment == "crypto"
        else _MAX_STAGE2_ITEMS_PER_SECTION
    )
    remaining_total = max_total
    for section_id in (2, 3, 4, 5):
        items = items_by_section.get(section_id, ())
        parts.append(f"Section {section_id}:")
        if not items:
            parts.append("  (no items)")
        else:
            section_limit = min(max_per_section, remaining_total)
            sorted_items = _sort_for_story(items, story_metadata=story_metadata)
            rendered_items = sorted_items[:section_limit]
            for item in rendered_items:
                title = _truncate_prompt_field(item.title, _STAGE2_TITLE_MAX_CHARS)
                summary = _truncate_prompt_field(
                    (item.summary or "").strip(),
                    _STAGE2_SUMMARY_MAX_CHARS,
                )
                url = _render_prompt_url(item.url)
                story_prefix = _render_story_prefix(item, story_metadata=story_metadata)
                if summary:
                    parts.append(f"  - {story_prefix}[{item.source_name}] {title}{url} — {summary}")
                else:
                    parts.append(f"  - {story_prefix}[{item.source_name}] {title}{url}")
            omitted = len(items) - len(rendered_items)
            if omitted > 0:
                parts.append(
                    f"  - ({omitted} additional classified items omitted for prompt budget)"
                )
            remaining_total -= len(rendered_items)
        parts.append("")
    return "\n".join(parts).rstrip()


def _render_unassigned(
    unassigned: tuple[NormalizedItem, ...],
    *,
    segment: MarketSegment | None = None,
) -> str:
    """Render the unassigned items as bullet text. Empty → ``(none)``."""
    if not unassigned:
        return "(none)"
    lines: list[str] = []
    max_items = (
        _CRYPTO_MAX_STAGE2_UNASSIGNED_ITEMS if segment == "crypto" else _MAX_STAGE2_UNASSIGNED_ITEMS
    )
    rendered_items = unassigned[:max_items]
    for item in rendered_items:
        title = _truncate_prompt_field(item.title, _STAGE2_TITLE_MAX_CHARS)
        lines.append(f"  - [{item.source_name}] {title}{_render_prompt_url(item.url)}")
    omitted = len(unassigned) - len(rendered_items)
    if omitted > 0:
        lines.append(f"  - ({omitted} additional unassigned items omitted for prompt budget)")
    return "\n".join(lines)


def _render_required_macro_actuals(items: tuple[NormalizedItem, ...]) -> str:
    """Render required macro actuals outside generic Stage 2 caps."""

    if not items:
        return "(none)"

    lines: list[str] = []
    for item in items:
        payload = macro_prompt_payload(item) or {}
        parts = [f"- [{item.source_name}] {item.title}"]
        for key in ("event_key", "label", "actual", "prior", "forecast", "consensus", "surprise"):
            value = payload.get(key)
            if value:
                parts.append(f"{key}={value}")
        if item.url is not None:
            parts.append(f"url={_truncate_prompt_field(str(item.url), _STAGE2_URL_MAX_CHARS)}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _grouped_stage2_rendered_items(
    plan: SectionPlan,
    *,
    segment: MarketSegment | None = None,
) -> tuple[NormalizedItem, ...]:
    """Return items that survive the generic Stage 2 grouped-section caps."""
    rendered: list[NormalizedItem] = []
    max_total = _CRYPTO_MAX_STAGE2_ITEMS_TOTAL if segment == "crypto" else _MAX_STAGE2_ITEMS_TOTAL
    max_per_section = (
        _CRYPTO_MAX_STAGE2_ITEMS_PER_SECTION
        if segment == "crypto"
        else _MAX_STAGE2_ITEMS_PER_SECTION
    )
    remaining_total = max_total
    for section_id in (2, 3, 4, 5):
        items = plan.items_by_section.get(section_id, ())
        section_limit = min(max_per_section, remaining_total)
        sorted_items = _sort_for_story(items, story_metadata=plan.story_metadata)
        rendered.extend(sorted_items[:section_limit])
        remaining_total -= min(len(items), section_limit)
    return tuple(rendered)


def _sort_for_story(
    items: tuple[NormalizedItem, ...],
    *,
    story_metadata: dict[str, StoryMetadata] | None,
) -> tuple[NormalizedItem, ...]:
    if not story_metadata:
        return items
    return tuple(
        sorted(
            items,
            key=lambda item: (
                -story_metadata.get(story_identity(item), StoryMetadata("context", 100, ())).score,
                -item.published_at.timestamp(),
                item.source_name,
                item.title,
                story_identity(item),
            ),
        )
    )


def _render_story_prefix(
    item: NormalizedItem,
    *,
    story_metadata: dict[str, StoryMetadata] | None,
) -> str:
    if not story_metadata:
        return ""
    metadata = story_metadata.get(story_identity(item))
    if metadata is None:
        return ""
    reasons = ",".join(metadata.reasons)
    return f"[tier={metadata.tier} score={metadata.score} reasons={reasons}] "


def _stage2_retry_feedback(cause: BaseException | None) -> str:
    if cause is None:
        return ""
    message = _truncate_prompt_field(str(cause), _STAGE2_RETRY_FEEDBACK_MAX_CHARS)
    return (
        "\n\nPrevious Stage 2 output failed validation. Retry from scratch as a complete "
        "document. The first non-empty line MUST be `## ① 요약`; then emit the exact "
        "six required H2 headers in order through `## ⑥ 오늘의 관전 포인트`. Do not "
        "continue from the failed output, do not begin mid-section, and do not omit "
        f"earlier sections. Validation error: {message}\n"
    )


__all__ = [
    "_grouped_stage2_rendered_items",
    "_render_grouped_sections",
    "_render_required_macro_actuals",
    "_render_unassigned",
    "_stage2_retry_feedback",
]
