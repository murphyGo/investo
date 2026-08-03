"""Final-body-centered semantic image selection (U-141).

The image ledger identifies possible assets; it does not establish editorial
relevance. This module derives a bounded context from the finalizable
reader-facing briefing and requires exact article lineage before a candidate
can become a stored hero or metadata-only source card.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final

from investo._internal.briefing_extract import extract_conclusion, extract_key_drivers
from investo.models import NormalizedItem
from investo.models.segments import MarketSegment
from investo.visuals.image_library import (
    DEFAULT_LEDGER_ROOT,
    DEFAULT_STORE_ROOT,
    ImageCandidateRecord,
    RecurrenceIndexEntry,
    current_rights_state,
    load_clearance_manifest,
    read_date_ledger,
    read_index,
    read_stored_image_dimensions,
    store_binary_path,
    store_sidecar_path,
)
from investo.visuals.policy import ExternalAssetManifest
from investo.visuals.provenance import VisualProvenanceManifest, sanitize_provenance_text

SELECTION_CONTRACT: Final[str] = "final-body-semantic-v1"
MIN_HERO_WIDTH: Final[int] = 600
MIN_HERO_HEIGHT: Final[int] = 338
_ISSUE_HEADING_PREFIX: Final[str] = "## ② 전일 핵심 이슈"
_STORE_EXTENSIONS: Final[tuple[str, ...]] = (".png", ".jpg")
_ARTICLE_URL_RE: Final[re.Pattern[str]] = re.compile(
    r"https?://[^\s<>\]\)]+",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ImageNarrativeContext:
    """Reader-visible semantic scopes captured before visual supplements."""

    segment: MarketSegment
    hero_markdown: str
    issue_markdown: str
    narrative_sha256: str


@dataclass(frozen=True, slots=True)
class StoredHeroSelection:
    """A cleared store pair selected for local hero copying."""

    candidate: ImageCandidateRecord
    binary_path: Path
    store_manifest: VisualProvenanceManifest
    clearance_manifest: ExternalAssetManifest


@dataclass(frozen=True, slots=True)
class ImageUsageSelection:
    """At most one stored hero and one distinct metadata source card."""

    hero: StoredHeroSelection | None
    card_candidate: ImageCandidateRecord | None
    narrative_sha256: str
    reason: str


def build_image_narrative_context(
    segment: MarketSegment,
    rendered_markdown: str,
) -> ImageNarrativeContext:
    """Build deterministic hero/issue scopes from finalizable Markdown.

    Missing ``## ②`` or a first H3 story fails closed to empty scopes. The
    input is stripped of already-rendered typed supplements so a retry cannot
    use an image/card as evidence for itself.
    """

    narrative = _strip_supplement_regions(rendered_markdown)
    issue = _extract_issue_section(narrative)
    first_story = _extract_first_story(issue)
    if not issue or not first_story:
        hero_markdown = ""
        issue_markdown = ""
    else:
        conclusion = extract_conclusion(narrative) or ""
        drivers = extract_key_drivers(narrative) or ""
        hero_markdown = _canonical_join((conclusion, drivers, first_story))
        issue_markdown = issue.strip()

    payload = json.dumps(
        {
            "hero_markdown": hero_markdown,
            "issue_markdown": issue_markdown,
            "segment": segment,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return ImageNarrativeContext(
        segment=segment,
        hero_markdown=hero_markdown,
        issue_markdown=issue_markdown,
        narrative_sha256=digest,
    )


def select_image_usage(
    context: ImageNarrativeContext,
    *,
    target_date: date,
    ledger_root: Path = DEFAULT_LEDGER_ROOT,
    store_root: Path = DEFAULT_STORE_ROOT,
) -> ImageUsageSelection:
    """Select feed-image usage using exact final-body article lineage.

    Rank is narrative occurrence, index ``first_seen``, candidate id. Current
    operator files are re-read for rights; ``index.json`` is recurrence/tie
    metadata only.
    """

    if not context.issue_markdown or not context.hero_markdown:
        return ImageUsageSelection(
            hero=None,
            card_candidate=None,
            narrative_sha256=context.narrative_sha256,
            reason="missing-issue-scope",
        )

    index = read_index(ledger_root=ledger_root)
    hero_candidates: list[tuple[int, date, str, StoredHeroSelection]] = []
    card_candidates: list[tuple[int, date, str, ImageCandidateRecord]] = []

    for candidate in read_date_ledger(target_date, ledger_root=ledger_root):
        if candidate.segment != context.segment:
            continue
        issue_offset = article_url_offset(context.issue_markdown, candidate.item_url)
        if issue_offset is None:
            continue
        rights_state = current_rights_state(candidate.candidate_id, ledger_root=ledger_root)
        if rights_state == "blocked":
            continue
        first_seen = _first_seen(candidate, index.get(candidate.candidate_id))
        card_candidates.append((issue_offset, first_seen, candidate.candidate_id, candidate))

        hero_offset = article_url_offset(context.hero_markdown, candidate.item_url)
        if hero_offset is None or rights_state != "cleared":
            continue
        if not _hero_dimensions_are_sufficient(candidate):
            continue
        stored = _load_valid_stored_hero(
            candidate,
            ledger_root=ledger_root,
            store_root=store_root,
        )
        if stored is not None:
            hero_candidates.append((hero_offset, first_seen, candidate.candidate_id, stored))

    hero_candidates.sort(key=lambda ranked: ranked[:3])
    card_candidates.sort(key=lambda ranked: ranked[:3])
    hero = hero_candidates[0][3] if hero_candidates else None
    hero_id = hero.candidate.candidate_id if hero is not None else None
    card = next(
        (ranked[3] for ranked in card_candidates if ranked[3].candidate_id != hero_id),
        None,
    )
    hero_reason = "none" if hero is None else hero.candidate.candidate_id
    card_reason = "none" if card is None else card.candidate_id
    return ImageUsageSelection(
        hero=hero,
        card_candidate=card,
        narrative_sha256=context.narrative_sha256,
        reason=f"hero={hero_reason};card={card_reason}",
    )


def article_url_offset(markdown: str, item_url: str) -> int | None:
    """Return the first exact URL-token offset, never a substring match."""

    return _article_url_offsets(markdown).get(item_url)


def filter_items_for_hero_context(
    context: ImageNarrativeContext,
    items: Sequence[NormalizedItem],
) -> tuple[NormalizedItem, ...]:
    """Order legacy licensed-image inputs by exact hero-body URL lineage."""

    offsets = _article_url_offsets(context.hero_markdown)
    ranked: list[tuple[int, int, NormalizedItem]] = []
    for input_order, item in enumerate(items):
        if item.url is None:
            continue
        offset = offsets.get(str(item.url))
        if offset is not None:
            ranked.append((offset, input_order, item))
    ranked.sort(key=lambda value: value[:2])
    return tuple(value[2] for value in ranked)


def render_image_source_card(candidate: ImageCandidateRecord) -> str:
    """Render metadata-only attribution with the article URL, never image URL."""

    title = _plain_text_metadata(candidate.item_title, limit=160)
    credit = _plain_text_metadata(candidate.image_credit or candidate.source_name, limit=160)
    return (
        "> **📷 오늘의 시장 이미지(원문)**\n"
        f"> {title} — {credit} · [원문 보기]({candidate.item_url})"
    )


def insert_image_source_card(markdown: str, rendered_blocks: tuple[str, ...]) -> str:
    """Insert one typed card block after the first ``## ②`` H3 story."""

    if not rendered_blocks:
        return markdown
    if len(rendered_blocks) != 1:
        raise ValueError("image source-card placement accepts exactly one block")
    block = rendered_blocks[0].rstrip()
    if block in markdown:
        return markdown

    lines = markdown.splitlines()
    section_start = next(
        (index for index, line in enumerate(lines) if line.startswith(_ISSUE_HEADING_PREFIX)),
        None,
    )
    if section_start is None:
        return markdown
    first_story = next(
        (
            index
            for index in range(section_start + 1, len(lines))
            if lines[index].startswith("### ")
        ),
        None,
    )
    if first_story is None:
        return markdown
    insert_at = len(lines)
    for index in range(first_story + 1, len(lines)):
        if lines[index].startswith("### ") or lines[index].startswith("## "):
            insert_at = index
            break
    lines[insert_at:insert_at] = ["", block, ""]
    suffix = "\n" if markdown.endswith("\n") else ""
    return "\n".join(lines) + suffix


def _strip_supplement_regions(markdown: str) -> str:
    # Marker ids are captured as ``kind:id`` and must close exactly. Inputs
    # without typed blocks pass byte-for-byte into the extraction helpers.
    pattern = re.compile(
        r"<!-- investo:block ((?:visual|chart|carryover):[^\n]+) -->.*?"
        r"<!-- /investo:block \1 -->\s*",
        flags=re.DOTALL,
    )
    return pattern.sub("", markdown)


def _extract_issue_section(markdown: str) -> str:
    lines = markdown.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.startswith(_ISSUE_HEADING_PREFIX)),
        None,
    )
    if start is None:
        return ""
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    return "\n".join(lines[start + 1 : end]).strip()


def _extract_first_story(issue_markdown: str) -> str:
    lines = issue_markdown.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.startswith("### ")),
        None,
    )
    if start is None:
        return ""
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("### ")),
        len(lines),
    )
    return "\n".join(lines[start:end]).strip()


def _canonical_join(parts: tuple[str, ...]) -> str:
    return "\n".join(part.strip() for part in parts if part.strip())


def _first_seen(
    candidate: ImageCandidateRecord,
    index_entry: RecurrenceIndexEntry | None,
) -> date:
    return candidate.collected_on if index_entry is None else index_entry.first_seen


def _hero_dimensions_are_sufficient(candidate: ImageCandidateRecord) -> bool:
    return bool(
        candidate.image_width is not None
        and candidate.image_height is not None
        and candidate.image_width >= MIN_HERO_WIDTH
        and candidate.image_height >= MIN_HERO_HEIGHT
    )


def _load_valid_stored_hero(
    candidate: ImageCandidateRecord,
    *,
    ledger_root: Path,
    store_root: Path,
) -> StoredHeroSelection | None:
    binaries = tuple(
        path
        for extension in _STORE_EXTENSIONS
        if (
            path := store_binary_path(
                candidate.candidate_id,
                extension,
                store_root=store_root,
            )
        ).is_file()
    )
    if len(binaries) != 1:
        return None
    binary_path = binaries[0]
    sidecar_path = store_sidecar_path(binary_path)
    if not sidecar_path.is_file():
        return None
    try:
        store_manifest = VisualProvenanceManifest.model_validate_json(
            sidecar_path.read_text(encoding="utf-8")
        )
        content_sha256 = hashlib.sha256(binary_path.read_bytes()).hexdigest()
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    metadata = store_manifest.additional_metadata
    actual_dimensions = read_stored_image_dimensions(binary_path)
    if (
        store_manifest.source_type != "external"
        or store_manifest.card_kind != "external-context-image"
        or metadata.get("candidate_id") != candidate.candidate_id
        or metadata.get("content_sha256") != content_sha256
        or actual_dimensions is None
        or actual_dimensions != store_manifest.dimensions
        or actual_dimensions[0] < MIN_HERO_WIDTH
        or actual_dimensions[1] < MIN_HERO_HEIGHT
    ):
        return None
    clearance_manifest = load_clearance_manifest(
        candidate.candidate_id,
        ledger_root=ledger_root,
    )
    if clearance_manifest is None:
        return None
    return StoredHeroSelection(
        candidate=candidate,
        binary_path=binary_path,
        store_manifest=store_manifest,
        clearance_manifest=clearance_manifest,
    )


def _bounded_text(value: str, *, limit: int) -> str:
    return " ".join(sanitize_provenance_text(value).split())[:limit].strip()


def _plain_text_metadata(value: str, *, limit: int) -> str:
    """Render feed metadata as inert text, never Markdown/HTML/link syntax."""

    without_urls = _ARTICLE_URL_RE.sub("링크 제거", value)
    escaped_html = html.escape(without_urls, quote=False)
    escaped_markdown = re.sub(r"([\\`*_\[\]()!])", r"\\\1", escaped_html)
    return _bounded_text(escaped_markdown, limit=limit) or "출처 표기 없음"


def _article_url_offsets(markdown: str) -> dict[str, int]:
    offsets: dict[str, int] = {}
    for match in _ARTICLE_URL_RE.finditer(markdown):
        # Sentence punctuation may follow a raw URL. Markdown destinations
        # normally terminate at ')' and are therefore unchanged.
        url = match.group(0).rstrip(".,;")
        offsets.setdefault(url, match.start())
    return offsets


__all__ = [
    "MIN_HERO_HEIGHT",
    "MIN_HERO_WIDTH",
    "SELECTION_CONTRACT",
    "ImageNarrativeContext",
    "ImageUsageSelection",
    "StoredHeroSelection",
    "article_url_offset",
    "build_image_narrative_context",
    "filter_items_for_hero_context",
    "insert_image_source_card",
    "render_image_source_card",
    "select_image_usage",
]
