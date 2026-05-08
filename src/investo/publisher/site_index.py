"""Update public site discovery pages for the latest segmented briefing.

Surface refactored for u29 site-discovery-v2 (persona #2 P0):

* The Home page (``site_docs/index.md``) ships a marker-bracketed hero
  block ``<!-- u29 hero begin --> ... <!-- u29 hero end -->`` that
  publisher rewrites on every segmented publish. Inside the markers
  live the per-segment "오늘의 결론" quote cards extracted from each
  segmented briefing's first-viewport blockquote — so the first thing a
  visitor sees is the actual content of the day, not site meta-copy.
* The Archive index (``site_docs/archive/index.md``) keeps its 최신 시황
  / 과거 단일 시황 sections refreshed and additionally embeds a
  deterministic publish calendar heatmap (see
  :func:`update_archive_heatmap_section` and the
  :mod:`investo.visuals.calendar_heatmap` renderer).
* Per-segment archive landing pages (``archive/{segment}/index.md``)
  are auto-generated as a list of all archived briefings for that
  segment so the mkdocs nav can offer 미국 증시 / 크립토 / 국내 증시 entry
  points without hand-maintained content.

All filesystem writes use the same atomic tmp-then-replace pattern as
:mod:`investo.publisher.writer` so a SIGINT mid-write cannot leave a
half-rewritten index page on disk.
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path
from typing import Final

from investo.briefing.extract import extract_conclusion as _extract_conclusion_chokepoint
from investo.briefing.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    SEGMENT_LABELS,
    US_EQUITY,
    MarketSegment,
)
from investo.models import Briefing

SITE_INDEX_PATH: Final[Path] = Path("site_docs/index.md")
ARCHIVE_INDEX_PATH: Final[Path] = Path("archive/index.md")
# u32 Step 4 — public quality dashboard. Lives under ``site_docs/`` so
# mkdocs picks it up alongside the other top-nav pages. The page is
# regenerated on every successful publish; an absent file (first
# publish on a fresh checkout) gets created lazily.
QUALITY_PAGE_PATH: Final[Path] = Path("site_docs/quality.md")
SEGMENT_ARCHIVE_INDEX_PATHS: Final[dict[MarketSegment, Path]] = {
    DOMESTIC_EQUITY: Path("archive/domestic-equity/index.md"),
    US_EQUITY: Path("archive/us-equity/index.md"),
    CRYPTO: Path("archive/crypto/index.md"),
}
_SEGMENTS: Final[tuple[MarketSegment, ...]] = (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)

HERO_BEGIN: Final[str] = "<!-- u29 hero begin -->"
HERO_END: Final[str] = "<!-- u29 hero end -->"
HEATMAP_BEGIN: Final[str] = "<!-- u29 heatmap begin -->"
HEATMAP_END: Final[str] = "<!-- u29 heatmap end -->"

# Surface-specific fallback text — the chokepoint helper
# (:func:`investo.briefing.extract.extract_conclusion`) returns ``None``
# on miss and each surface owns its own fallback wording (DEBT-060
# consolidation 2026-05-08).
_HERO_FALLBACK_TEXT: Final[str] = "결론 인용을 추출하지 못했습니다."

# Match a markdown header line that *immediately* starts a top-level
# section (## 헤딩). Used to find the next section heading when
# refreshing the older ``## 최신 시황`` block-level sections (legacy
# behavior preserved alongside the new marker-bracketed hero block).
_NEXT_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^## ", re.MULTILINE)


def update_latest_index_pages(
    target_date: date,
    *,
    site_index_path: Path = SITE_INDEX_PATH,
    archive_index_path: Path = ARCHIVE_INDEX_PATH,
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
        Test seams. Production callers use the module defaults.
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
    written: list[Path] = [site_index_path, archive_index_path]

    if segment_briefings is not None:
        update_index_hero(
            target_date,
            segment_briefings,
            site_index_path=site_index_path,
        )

    _replace_section(
        site_index_path,
        "## 최신 시황",
        _site_latest_section(target_date),
    )
    _replace_section(
        archive_index_path,
        "## 최신 시황",
        _archive_latest_section(target_date),
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


# ---------------------------------------------------------------------------
# Hero block (Home page)
# ---------------------------------------------------------------------------


def update_quality_page(
    target_date: date,
    *,
    coverage_path: Path,
    archive_root: Path,
    quality_page_path: Path | None = None,
    window_days: int = 7,
) -> Path:
    """Regenerate ``site_docs/quality.md`` from the trailing-window KPIs.

    Pure I/O: reads ``coverage_path`` + scans ``archive_root``; writes
    a fresh page at ``quality_page_path``. Returns the written path.
    The file is overwritten in place — no marker-bracketed merge — so
    running the function twice with the same inputs leaves the file
    byte-identical.

    ``quality_page_path`` defaults to the module-level
    :data:`QUALITY_PAGE_PATH` resolved at *call time* (not at function
    definition time) so test-side ``monkeypatch.setattr`` redirection
    reaches this writer.
    """
    from investo.briefing.quality_eval import compute_quality_kpis, render_quality_page

    target = quality_page_path if quality_page_path is not None else QUALITY_PAGE_PATH
    kpis = compute_quality_kpis(
        target_date,
        coverage_path=coverage_path,
        archive_root=archive_root,
        window_days=window_days,
    )
    body = render_quality_page(kpis)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def update_index_hero(
    target_date: date,
    segment_briefings: dict[MarketSegment, Briefing],
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


def update_archive_heatmap_section(
    heatmap_svg: str,
    *,
    archive_index_path: Path = ARCHIVE_INDEX_PATH,
) -> Path:
    """Replace the marker-bracketed publish-calendar SVG on Archive index."""
    body = _render_heatmap_block(heatmap_svg)
    _replace_marker_block(
        archive_index_path,
        begin_marker=HEATMAP_BEGIN,
        end_marker=HEATMAP_END,
        replacement=body,
    )
    return archive_index_path


def update_segment_archive_index(
    segment: MarketSegment,
    *,
    segment_index_path: Path,
) -> Path:
    """Regenerate the archive landing page for a single market segment.

    Lists every ``YYYY-MM-DD.md`` under
    ``archive/{segment}/YYYY/MM/`` (newest first). The file is rewritten
    from scratch each time — content is fully derivable from the
    archive directory tree.
    """
    archive_dir = segment_index_path.parent
    label = SEGMENT_LABELS[segment]
    entries = _segment_entries(archive_dir)
    body = _render_segment_index(segment, label, entries)
    _write_text_atomic(segment_index_path, body)
    return segment_index_path


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
    return value


def _render_hero_block(
    target_date: date,
    segment_briefings: dict[MarketSegment, Briefing],
) -> str:
    iso = target_date.isoformat()
    cards: list[str] = []
    for segment in _SEGMENTS:
        label = SEGMENT_LABELS[segment]
        href = _site_segment_href(target_date, segment)
        briefing = segment_briefings.get(segment)
        conclusion = (
            extract_conclusion(briefing.rendered_markdown)
            if briefing is not None
            else _HERO_FALLBACK_TEXT
        )
        # Markdown blockquote cards keep the hero readable both when
        # mkdocs renders the page AND when GitHub displays the raw .md
        # — important for index reviewers using the GitHub web UI.
        cards.append(f"### [{label}]({href})\n\n> {_escape_inline(conclusion)}\n")
    body_cards = "\n".join(cards)
    return (
        f"# 오늘의 시황 ({iso})\n\n"
        "오늘 자동 발행된 세 개 세그먼트의 결론을 요약합니다. "
        "각 카드를 눌러 전체 시황으로 이동할 수 있습니다.\n\n"
        f"{body_cards}\n"
        "[전체 Archive 보기](archive/index.md) · "
        "[About](about.md) · "
        "[주차별 회고](archive/weekly/index.md)\n"
    )


def _render_heatmap_block(heatmap_svg: str) -> str:
    return (
        "## 발행 캘린더\n\n"
        "지난 주차별 게시 일자와 데이터 신뢰도(정상·부분·부족)를 "
        "한눈에 표시합니다.\n\n"
        '<figure class="u29-heatmap" markdown="1">\n'
        f"{heatmap_svg.strip()}\n"
        "<figcaption>발행 캘린더 — 색상은 데이터 신뢰도 정책을 따릅니다.</figcaption>\n"
        "</figure>\n"
    )


def _render_segment_index(
    segment: MarketSegment,
    label: str,
    entries: list[Path],
) -> str:
    lines = [
        f"# {label} 시황 아카이브",
        "",
        f"이 페이지는 `{segment}` 세그먼트로 게시된 모든 시황의 색인입니다. "
        "최근 발행이 위에 표시됩니다.",
        "",
    ]
    if not entries:
        lines.extend(
            [
                "현재 표시할 시황이 없습니다. 다음 발행 주기 이후에 자동으로 채워집니다.",
                "",
                "- [전체 Archive로 돌아가기](../index.md)",
            ]
        )
        return "\n".join(lines) + "\n"

    lines.append("- [전체 Archive로 돌아가기](../index.md)")
    lines.append("")
    for entry in entries:
        # entries are sorted newest first by ``_segment_entries``.
        rel = entry.relative_to(entry.parents[2]).as_posix()
        # rel like "2026/05/2026-05-06.md" — relative to the segment root.
        iso = entry.stem
        lines.append(f"- [{iso}]({rel})")
    lines.append("")
    return "\n".join(lines)


def _segment_entries(archive_dir: Path) -> list[Path]:
    """Return all ``YYYY-MM-DD.md`` paths under ``archive_dir``, newest first."""
    if not archive_dir.exists():
        return []
    paths = [
        path for path in archive_dir.glob("[0-9][0-9][0-9][0-9]/*/*.md") if path.name != "index.md"
    ]
    return sorted(paths, key=lambda path: path.stem, reverse=True)


# ---------------------------------------------------------------------------
# Legacy ``## 최신 시황`` / ``## 과거 단일 시황`` sections (preserved)
# ---------------------------------------------------------------------------


def _site_latest_section(target_date: date) -> str:
    return (
        "## 최신 시황\n\n"
        f"현재 보관된 최신 묶음은 **{target_date.isoformat()}**입니다.\n\n"
        + "\n".join(
            f"- [{SEGMENT_LABELS[segment]}]({_site_segment_href(target_date, segment)})"
            for segment in _SEGMENTS
        )
        + "\n\n[전체 Archive 보기](archive/index.md)"
    )


def _archive_latest_section(target_date: date) -> str:
    return (
        "## 최신 시황\n\n"
        f"현재 보관된 최신 묶음은 **{target_date.isoformat()}**입니다.\n\n"
        + "\n".join(
            f"- [{SEGMENT_LABELS[segment]}]({_archive_segment_href(target_date, segment)})"
            for segment in _SEGMENTS
        )
    )


def _legacy_section(archive_root: Path) -> str:
    legacy_paths = sorted(
        path for path in archive_root.glob("[0-9][0-9][0-9][0-9]/*/*.md") if path.name != "index.md"
    )
    body = (
        "과거 단일 시황은 세그먼트 분리 이전 형식입니다. 최신 탐색은 위의 "
        "국내 증시·미국 증시·크립토 링크를 우선 사용하세요."
    )
    if not legacy_paths:
        return f"## 과거 단일 시황\n\n{body}\n\n- 현재 표시할 레거시 단일 시황이 없습니다."
    links = "\n".join(
        f"- [{path.stem} 단일 시황 (레거시)]({path.relative_to(archive_root).as_posix()})"
        for path in legacy_paths
    )
    return f"## 과거 단일 시황\n\n{body}\n\n{links}"


def _site_segment_href(target_date: date, segment: str) -> str:
    return f"archive/{_archive_segment_href(target_date, segment)}"


def _archive_segment_href(target_date: date, segment: str) -> str:
    return f"{segment}/{target_date.year:04d}/{target_date.month:02d}/{target_date.isoformat()}.md"


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def _replace_section(path: Path, heading: str, replacement: str) -> None:
    """Replace a top-level ``## `` section between two H2 headings."""
    content = path.read_text(encoding="utf-8")
    if heading not in content:
        return  # Section was removed by a future rewrite — leave file alone.
    start = content.index(heading)
    next_heading_match = _NEXT_HEADING_RE.search(content, start + len(heading))
    end = len(content) if next_heading_match is None else next_heading_match.start()
    updated = content[:start] + replacement.rstrip() + "\n" + content[end:]
    _write_text_atomic(path, updated)


def _replace_marker_block(
    path: Path,
    *,
    begin_marker: str,
    end_marker: str,
    replacement: str,
) -> None:
    """Replace the bytes between two marker comments idempotently.

    When either marker is missing, the markers + replacement are
    appended to the file so a fresh page can bootstrap the block on
    first publish. When both markers are present the block is
    rewritten in place.
    """
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        new_content = f"{begin_marker}\n{replacement.strip()}\n{end_marker}\n"
        _write_text_atomic(path, new_content)
        return

    content = path.read_text(encoding="utf-8")
    begin_idx = content.find(begin_marker)
    end_idx = content.find(end_marker)
    if begin_idx == -1 or end_idx == -1 or end_idx < begin_idx:
        # Append a fresh block at the end of the file. A trailing
        # newline ensures the marker is on its own line even when the
        # file ends mid-line.
        suffix = "" if content.endswith("\n") else "\n"
        new_content = (
            content + suffix + "\n" + f"{begin_marker}\n{replacement.strip()}\n{end_marker}\n"
        )
        _write_text_atomic(path, new_content)
        return

    new_block = f"{begin_marker}\n{replacement.strip()}\n{end_marker}"
    end_marker_end = end_idx + len(end_marker)
    updated = content[:begin_idx] + new_block + content[end_marker_end:]
    _write_text_atomic(path, updated)


def _escape_inline(text: str) -> str:
    """Escape characters that would break a single-line markdown blockquote."""
    return text.replace("\n", " ").replace("\r", " ").strip()


def _write_text_atomic(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)


__all__ = [
    "ARCHIVE_INDEX_PATH",
    "HEATMAP_BEGIN",
    "HEATMAP_END",
    "HERO_BEGIN",
    "HERO_END",
    "QUALITY_PAGE_PATH",
    "SEGMENT_ARCHIVE_INDEX_PATHS",
    "SITE_INDEX_PATH",
    "extract_conclusion",
    "update_archive_heatmap_section",
    "update_index_hero",
    "update_latest_index_pages",
    "update_quality_page",
    "update_segment_archive_index",
]
