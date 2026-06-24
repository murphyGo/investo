"""Per-segment archive landing pages (u29 site-discovery-v2).

Per-segment archive landing pages (``archive/{segment}/index.md``) are
auto-generated as a list of all archived briefings for that segment so
the mkdocs nav can offer 미국 증시 / 크립토 / 국내 증시 entry points
without hand-maintained content.

Move-only split out of the original ``site_index.py`` module (u82). The
``_segment_entries`` directory scan also backs the archive-sections
fallback lookup, so it lives here as the single home.
"""

from __future__ import annotations

from pathlib import Path

from investo.models.segments import SEGMENT_LABELS, MarketSegment

from ._blocks import _write_text_atomic


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
