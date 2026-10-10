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

from collections.abc import Mapping
from datetime import date
from html import escape
from pathlib import Path
from stat import S_ISDIR, S_ISREG
from typing import TYPE_CHECKING
from urllib.parse import quote

from investo._internal.briefing_extract import extract_conclusion
from investo._internal.public_summary_extract import clean_public_summary_text
from investo._internal.text import bound_at_sentence
from investo.models.segments import SEGMENT_LABELS, MarketSegment

from ._blocks import _write_text_atomic

if TYPE_CHECKING:
    from investo.publisher.public_document import FinalizedPublicDocument


def update_segment_archive_index(
    segment: MarketSegment,
    *,
    segment_index_path: Path,
    finalized_documents: Mapping[Path, FinalizedPublicDocument] | None = None,
    terminal_snippets: Mapping[Path, str] | None = None,
    terminal_limitations: Mapping[Path, str] | None = None,
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
    body = _render_segment_index(
        segment,
        label,
        entries,
        finalized_documents=finalized_documents,
        terminal_snippets=terminal_snippets,
        terminal_limitations=terminal_limitations,
    )
    _write_text_atomic(segment_index_path, body)
    return segment_index_path


def _render_segment_index(
    segment: MarketSegment,
    label: str,
    entries: list[Path],
    *,
    finalized_documents: Mapping[Path, FinalizedPublicDocument] | None = None,
    terminal_snippets: Mapping[Path, str] | None = None,
    terminal_limitations: Mapping[Path, str] | None = None,
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
                "- [전체 아카이브로 돌아가기](../index.md)",
            ]
        )
        return "\n".join(lines) + "\n"

    groups: dict[str, list[Path]] = {}
    extra: list[Path] = []
    for entry in entries:
        parsed = _entry_date(entry)
        if parsed is None:
            extra.append(entry)
        else:
            groups.setdefault(parsed.isoformat()[:7], []).append(entry)
    months = sorted(groups, reverse=True)
    lines.extend(
        [
            "[전체 아카이브로 돌아가기](../index.md)",
            "",
            f'<div class="investo-archive" data-segment="{segment}" markdown="1">',
            '<details class="investo-archive-month-nav" markdown="1">',
            "<summary>보관 월 바로가기</summary>",
            "",
            " · ".join(f"[{month} ({len(groups[month])})](#month-{month})" for month in months),
            "",
            "</details>",
            '<form class="investo-archive-controls" hidden>',
            '<label>보관 월<select name="month" aria-label="보관 월">'
            '<option value="">전체 기간</option>'
            + "".join(f'<option value="{month}">{month}</option>' for month in months)
            + "</select></label>",
            '<label>날짜 찾기<input type="search" name="date" '
            'placeholder="예: 2026-10-07"></label>',
            '<button type="reset">전체 목록</button></form>',
            '<p class="investo-archive-result" role="status" aria-live="polite"></p>',
            "",
        ]
    )
    for month in months:
        lines.extend(
            [
                f'<section class="investo-archive-month" data-month="{month}" markdown="1">',
                "",
                f'## {month[:4]}년 {month[5:]}월 {{ #month-{month} tabindex="-1" }}',
                "",
            ]
        )
        for entry in sorted(groups[month], key=lambda p: p.stem, reverse=True):
            lines.append(
                _render_archive_entry(
                    entry,
                    segment=segment,
                    finalized=(finalized_documents or {}).get(entry),
                    terminal_snippet=(terminal_snippets or {}).get(entry),
                    terminal_limitation=(terminal_limitations or {}).get(entry),
                    terminal_mode=terminal_snippets is not None or terminal_limitations is not None,
                )
            )
        lines.extend(["", "</section>", ""])
    if extra:
        lines.extend(
            [
                "## 경로 확인이 필요한 문서",
                "",
                "기존 문서의 실제 경로를 유지합니다. 이 목록은 기간 필터와 별도로 표시합니다.",
                "",
            ]
        )
        for entry in extra:
            href = quote(entry.relative_to(entry.parents[2]).as_posix(), safe="/-.")
            lines.extend(
                [
                    f'<p markdown="0">{escape(entry.name)}</p>',
                    f"[기존 문서 열기]({href}){{ .investo-archive-link }}",
                    "",
                ]
            )
    lines.extend(["</div>", ""])
    return "\n".join(lines)


def _entry_date(entry: Path) -> date | None:
    try:
        parsed = date.fromisoformat(entry.stem)
    except ValueError:
        return None
    matches = (entry.parent.parent.name, entry.parent.name) == (
        f"{parsed.year:04d}",
        f"{parsed.month:02d}",
    )
    return parsed if matches and entry.stem == parsed.isoformat() else None


def _legacy_snippet(document: FinalizedPublicDocument) -> str | None:
    value = extract_conclusion(document.briefing.rendered_markdown)
    if value is None:
        return None
    public = clean_public_summary_text(value)
    bounded = bound_at_sentence(public, 120, require_complete=True)
    # Do not drop a later limitation/caution to make a historical snippet fit.
    return bounded if bounded == public else None


def _render_archive_entry(
    entry: Path,
    *,
    segment: MarketSegment,
    finalized: FinalizedPublicDocument | None,
    terminal_snippet: str | None,
    terminal_limitation: str | None,
    terminal_mode: bool = False,
) -> str:
    href = quote(entry.relative_to(entry.parents[2]).as_posix(), safe="/-.")
    iso = entry.stem
    lines = [
        f'<div class="investo-archive-entry" data-date="{iso}" markdown="1">',
        "",
        f"[{iso}]({href}){{ .investo-archive-link }}",
        "",
    ]
    snippet = terminal_snippet
    if (
        not terminal_mode
        and snippet is None
        and finalized is not None
        and (finalized.segment == segment and finalized.target_date.isoformat() == iso)
    ):
        snippet = _legacy_snippet(finalized)
    if snippet is not None:
        lines.append(f'<p class="investo-archive-snippet" markdown="0">{escape(snippet)}</p>')
    if terminal_limitation is not None:
        lines.append(
            f'<p class="investo-archive-limitation" markdown="0">{escape(terminal_limitation)}</p>'
        )
    lines.append("</div>")
    return "\n".join(lines)


def _segment_entries(archive_dir: Path) -> list[Path]:
    """Return safe archive paths, including malformed historical names, newest first."""
    root = archive_dir.resolve()
    paths: list[Path] = []

    def is_safe_kind(path: Path, *, directory: bool) -> bool:
        try:
            if not path.resolve(strict=True).is_relative_to(root):
                return False
            mode = path.stat().st_mode
        except (FileNotFoundError, NotADirectoryError, RuntimeError):
            return False
        return S_ISDIR(mode) if directory else S_ISREG(mode)

    try:
        years = list(archive_dir.iterdir())
    except FileNotFoundError:
        return []
    # Path.glob suppresses nested scandir errors on supported Python versions.
    # Explicit fixed-depth traversal propagates unreadable directories so the
    # atomic index writer cannot publish an incomplete archive as empty.
    for year in years:
        if len(year.name) != 4 or not all("0" <= c <= "9" for c in year.name):
            continue
        if not is_safe_kind(year, directory=True):
            continue
        for month in year.iterdir():
            if not is_safe_kind(month, directory=True):
                continue
            for path in month.iterdir():
                if (
                    path.suffix == ".md"
                    and path.name != "index.md"
                    and is_safe_kind(path, directory=False)
                ):
                    paths.append(path)
    return sorted(paths, key=lambda path: (path.stem, path.as_posix()), reverse=True)
