"""u33 Step 3 — per-ticker accumulation page.

Each watchlist term gets a per-page markdown accumulating the matched
items across publish runs. The file lives at
``site_docs/watchlist/{slug}.md`` and is regenerated on every
successful publish — idempotent: re-running for the same target_date
replaces only that date's section, keeping prior history intact.

Term slugification:

* Tickers (``NVDA``, ``TSLA``) → upper-case ASCII.
* Korean tickers (``[005930]``) → preserved as the bracketed digits.
* Generic Korean asset names (``엔비디아``) → preserved verbatim
  (mkdocs handles unicode filenames on every supported OS).

Pure I/O — given the same inputs, the helper produces byte-identical
output. The orchestrator threads ``today`` and the matched items
explicitly so tests are deterministic.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path
from typing import Final

from investo.briefing.watchlist import WatchlistMatch
from investo.models import NormalizedItem

WATCHLIST_PAGES_ROOT: Final[Path] = Path("site_docs/watchlist")
# Per-day section marker — bracket-style anchored on the target date.
_BEGIN_MARKER_TEMPLATE: Final[str] = "<!-- u33 entry {date} begin -->"
_END_MARKER_TEMPLATE: Final[str] = "<!-- u33 entry {date} end -->"
_SLUG_RE: Final[re.Pattern[str]] = re.compile(r"[^A-Za-z0-9가-힣\[\]\-_]+")


def _slug_for_term(term: str) -> str:
    """Render a filesystem-safe slug for a watchlist term."""
    return _SLUG_RE.sub("-", term.strip()).strip("-") or "_unnamed"


def update_watchlist_pages(
    target_date: date,
    matches: Sequence[WatchlistMatch],
    *,
    pages_root: Path = WATCHLIST_PAGES_ROOT,
) -> tuple[Path, ...]:
    """Regenerate the per-term accumulation pages for ``matches``.

    Per-term: replace the ``target_date`` section in place (idempotent
    on re-run). Empty match lists for a term remove that day's section
    so a recovered upstream doesn't leave orphan entries.

    Returns the deterministic alphabetical tuple of paths the helper
    rewrote so the caller can pass them to ``commit_and_push``.
    """
    by_term = _group_by_term(matches)
    written: list[Path] = []
    for term, term_matches in sorted(by_term.items()):
        slug = _slug_for_term(term)
        path = pages_root / f"{slug}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else _initial_page(term)
        next_body = _replace_day_section(existing, target_date, term_matches, term=term)
        path.write_text(next_body, encoding="utf-8")
        written.append(path)
    index_path = _maybe_write_index(pages_root)
    if index_path is not None:
        written.append(index_path)
    return tuple(written)


def _group_by_term(matches: Iterable[WatchlistMatch]) -> dict[str, list[WatchlistMatch]]:
    out: dict[str, list[WatchlistMatch]] = {}
    for match in matches:
        out.setdefault(match.term, []).append(match)
    return out


def _initial_page(term: str) -> str:
    return f"# {term} 매칭 누적\n\n_자동 생성된 페이지 — 매 게시 직후 갱신됩니다._\n\n"


def _replace_day_section(
    existing: str,
    target_date: date,
    matches: Sequence[WatchlistMatch],
    *,
    term: str,
) -> str:
    """Replace (or insert) the ``target_date`` section in ``existing``."""
    iso = target_date.isoformat()
    begin = _BEGIN_MARKER_TEMPLATE.format(date=iso)
    end = _END_MARKER_TEMPLATE.format(date=iso)
    rendered_block = _render_day_block(target_date, matches, term=term, begin=begin, end=end)
    if begin in existing and end in existing:
        # Replace the existing section.
        prefix, _, rest = existing.partition(begin)
        _, _, suffix = rest.partition(end)
        return prefix + rendered_block + suffix
    # Insert at the top of the body (right after the auto-generated header).
    header_split = "_자동 생성된 페이지 — 매 게시 직후 갱신됩니다._\n\n"
    if header_split in existing:
        prefix, _, suffix = existing.partition(header_split)
        return prefix + header_split + rendered_block + suffix
    # No header marker — prepend a fresh header + block.
    return _initial_page(term) + rendered_block


def _render_day_block(
    target_date: date,
    matches: Sequence[WatchlistMatch],
    *,
    term: str,
    begin: str,
    end: str,
) -> str:
    if not matches:
        return f"{begin}\n{end}\n"
    iso = target_date.isoformat()
    lines = [begin, "", f"## {iso}", ""]
    for match in matches:
        lines.append(_match_bullet(match))
    lines.append("")
    lines.append(end)
    lines.append("")
    return "\n".join(lines)


def _match_bullet(match: WatchlistMatch) -> str:
    item: NormalizedItem = match.item
    title = item.title.strip()
    if len(title) > 120:
        title = title[:117].rstrip() + "…"
    weight_part = f" (가중치 {match.weight:g})" if match.weight else ""
    source_part = f"[{item.source_name}]"
    return f"- {source_part} **{match.kind}**: {title}{weight_part}"


def _maybe_write_index(pages_root: Path) -> Path | None:
    """Refresh the per-term index page so mkdocs nav can list every page.

    u33 Step 5 — embed a deterministic SVG chart at the top showing the
    cumulative match count per term (counted by per-page section
    headings).
    """
    from investo.visuals.watchlist_chart import render_cumulative_match_chart

    if not pages_root.exists():
        return None
    pages = sorted(p for p in pages_root.glob("*.md") if p.name != "index.md")
    if not pages:
        return None
    counts = {page.stem: _count_per_page(page) for page in pages}
    chart_svg = render_cumulative_match_chart({k: v for k, v in counts.items() if v > 0})
    index_path = pages_root / "index.md"
    lines = ["# 관심 자산 누적", ""]
    lines.append(chart_svg)
    lines.append("")
    lines.append("| 종목 / 자산 | 매칭 수 | 누적 페이지 |")
    lines.append("|-------------|---------|-------------|")
    for page in pages:
        slug = page.stem
        lines.append(f"| {slug} | {counts.get(slug, 0)} | [{slug}.md]({page.name}) |")
    lines.append("")
    index_path.write_text("\n".join(lines), encoding="utf-8")
    return index_path


def _count_per_page(page: Path) -> int:
    """Count the number of dated section headings (``## YYYY-MM-DD``)."""
    try:
        text = page.read_text(encoding="utf-8")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if line.startswith("## 20"))


__all__ = [
    "WATCHLIST_PAGES_ROOT",
    "update_watchlist_pages",
]
