"""Update public site discovery pages for the latest segmented briefing.

Surface refactored for u29 site-discovery-v2 (persona #2 P0) and split
into a package in u82 (one module per surface):

* The Home page hero block — :mod:`.hero`.
* The Archive index 최신/과거 sections + publish-calendar heatmap —
  :mod:`.archive_sections`.
* Per-segment archive landing pages — :mod:`.segment_archives`.
* The public quality / accuracy dashboard pages — :mod:`.quality_dashboard`.

Shared block-replacement / inline-escape / atomic-write helpers live in
:mod:`._blocks`; path / marker constants in :mod:`._constants`.

All filesystem writes use the same atomic tmp-then-replace pattern as
:mod:`investo.publisher.writer` (via the shared u78 primitive
:func:`investo._internal._io.write_atomic`) so a SIGINT mid-write cannot
leave a half-rewritten index page on disk.

The package ``__init__`` is the public face: it keeps the original
``update_latest_index_pages`` driver and re-exports every name that was
importable from the single-file module, so no caller changes its import
path.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from investo.models import Briefing
from investo.models.segments import MarketSegment

from ._blocks import (
    _NEXT_HEADING_RE as _NEXT_HEADING_RE,
)
from ._blocks import (
    _escape_inline as _escape_inline,
)
from ._blocks import (
    _replace_marker_block as _replace_marker_block,
)
from ._blocks import (
    _replace_section,
)
from ._blocks import (
    _write_text_atomic as _write_text_atomic,
)
from ._constants import (
    _HERO_FALLBACK_TEXT as _HERO_FALLBACK_TEXT,
)
from ._constants import (
    _SEGMENTS,
    ACCURACY_PAGE_PATH,
    ARCHIVE_INDEX_PATH,
    HEATMAP_BEGIN,
    HEATMAP_END,
    HERO_BEGIN,
    HERO_END,
    QUALITY_PAGE_PATH,
    SEGMENT_ARCHIVE_INDEX_PATHS,
    SITE_INDEX_PATH,
)
from .archive_sections import (
    SegmentBundleState,
    _build_bundle_states,
    _legacy_section,
    _site_latest_section,
    update_archive_heatmap_section,
)
from .archive_sections import (
    _archive_latest_section as _archive_latest_section,
)
from .archive_sections import (
    _archive_segment_href as _archive_segment_href,
)
from .archive_sections import (
    _latest_segment_entry_before as _latest_segment_entry_before,
)
from .archive_sections import (
    _render_bundle_state_line as _render_bundle_state_line,
)
from .archive_sections import (
    _render_heatmap_block as _render_heatmap_block,
)
from .archive_sections import (
    _site_segment_href as _site_segment_href,
)
from .hero import (
    _render_hero_block as _render_hero_block,
)
from .hero import (
    extract_conclusion,
    update_index_hero,
)
from .quality_dashboard import (
    _render_quality_page_with_history as _render_quality_page_with_history,
)
from .quality_dashboard import (
    update_accuracy_page,
    update_quality_page,
)
from .segment_archives import (
    _render_segment_index as _render_segment_index,
)
from .segment_archives import (
    _segment_entries as _segment_entries,
)
from .segment_archives import (
    update_segment_archive_index,
)


def update_latest_index_pages(
    target_date: date,
    *,
    site_index_path: Path | None = None,
    archive_index_path: Path | None = None,
    segment_briefings: dict[MarketSegment, Briefing] | None = None,
    heatmap_svg: str | None = None,
) -> tuple[Path, ...]:
    """Refresh Home + Archive landing surfaces for ``target_date``.

    Parameters
    ----------
    target_date:
        Publish date threaded into both the hero card and the
        ``## 최신 시황`` section.
    site_index_path / archive_index_path:
        Test seams. ``None`` (the production default) resolves the
        module-level constants AT CALL TIME — DEBT-089: binding them as
        default ARGUMENT values froze them at import, so a
        ``monkeypatch.setattr(site_index, "SITE_INDEX_PATH", …)`` could
        never redirect the writer and test runs rewrote the committed
        ``site_docs/index.md`` / ``archive/index.md``.
    segment_briefings:
        u29 hero feed — when supplied, the rendered "오늘의 결론" quotes
        for each segment are inlined into the hero block on the Home
        page. ``None`` (legacy / non-segmented test path) keeps the
        existing hero block intact rather than overwriting with a
        useless placeholder.
    heatmap_svg:
        u29 heatmap feed for the Archive index. ``None`` keeps the
        existing inline SVG (i.e. the prior heatmap survives until the
        next call that supplies a new one).

    Returns
    -------
    tuple[Path, ...]
        All paths that were rewritten — orchestrator passes these to
        ``commit_and_push`` so mkdocs picks up the regenerated copy.
    """
    site_index_path = site_index_path if site_index_path is not None else SITE_INDEX_PATH
    archive_index_path = (
        archive_index_path if archive_index_path is not None else ARCHIVE_INDEX_PATH
    )
    written: list[Path] = [site_index_path, archive_index_path]

    if segment_briefings is not None:
        update_index_hero(
            target_date,
            segment_briefings,
            site_index_path=site_index_path,
        )
    bundle_states = _build_bundle_states(
        target_date,
        archive_root=archive_index_path.parent,
        segment_briefings=segment_briefings,
    )

    _replace_section(
        site_index_path,
        "## 최신 시황",
        _site_latest_section(target_date, bundle_states),
    )
    _replace_section(
        archive_index_path,
        "## 최신 시황",
        _archive_latest_section(target_date, bundle_states),
    )
    _replace_section(
        archive_index_path,
        "## 과거 단일 시황",
        _legacy_section(archive_index_path.parent),
    )

    if heatmap_svg is not None:
        update_archive_heatmap_section(
            heatmap_svg,
            archive_index_path=archive_index_path,
        )

    # Per-segment archive index pages — best-effort: each lands at
    # ``archive/{segment}/index.md`` (relative to repo root) because
    # mkdocs picks them up via the ``site_docs/archive`` symlink.
    archive_root = archive_index_path.parent
    for segment in _SEGMENTS:
        segment_index = archive_root / segment / "index.md"
        update_segment_archive_index(segment, segment_index_path=segment_index)
        written.append(segment_index)

    return tuple(written)


__all__ = [
    "ACCURACY_PAGE_PATH",
    "ARCHIVE_INDEX_PATH",
    "HEATMAP_BEGIN",
    "HEATMAP_END",
    "HERO_BEGIN",
    "HERO_END",
    "QUALITY_PAGE_PATH",
    "SEGMENT_ARCHIVE_INDEX_PATHS",
    "SITE_INDEX_PATH",
    "SegmentBundleState",
    "extract_conclusion",
    "update_accuracy_page",
    "update_archive_heatmap_section",
    "update_index_hero",
    "update_latest_index_pages",
    "update_quality_page",
    "update_segment_archive_index",
]
