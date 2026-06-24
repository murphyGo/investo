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

import posixpath
import re
from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path
from typing import Final

from investo.briefing.watchlist import (
    PublicWatchlistGroup,
    WatchlistMatch,
    public_watchlist_match_summary,
)
from investo.briefing.watchlist_impact import RejectedCandidate, WatchlistImpactCenter
from investo.models import NormalizedItem

WATCHLIST_PAGES_ROOT: Final[Path] = Path("site_docs/watchlist")
# u73 — the daily-first impact center page. Today's grouped impacts are
# the first content block; per-term accumulation pages remain the
# history surface.
DAILY_IMPACT_PAGE: Final[str] = "daily.md"
_DIAGNOSTICS_SUMMARY: Final[str] = "진단: 보류/제외된 후보"

# u73 — reader-facing group semantics + alias guidance embedded at the top
# of the watchlist index page. Documents the four impact groups and how to
# turn a noisy short ticker into a reliable match via the alias config.
_GROUP_SEMANTICS_GUIDE: Final[tuple[str, ...]] = (
    "## 영향 그룹 안내",
    "",
    (
        "- **직접 (Direct)**: 티커/심볼 구조화 매칭 또는 정확한 별칭 일치. "
        "본문·텔레그램에 노출됩니다."
    ),
    (
        "- **관련 (Related)**: 섹터·키워드·매크로 맥락 매칭(직접 자산 일치는 아님). "
        "본문에 맥락으로 노출됩니다."
    ),
    (
        "- **보류 (Uncertain)**: 저신뢰 텍스트 매칭. "
        "진단 블록에만 표시되며 공개 첫인상에는 노출되지 않습니다."
    ),
    (
        "- **제외 (Rejected)**: 짧은 티커 오탐(예: `BTC`↔`BTM`/`BTCS`, `SOL`↔`SLGL`) "
        "억제 기록. 진단 블록에만 표시됩니다."
    ),
    "",
    (
        "> 짧은 티커(`BTC`, `SOL` 등)가 오탐을 일으키면 `config/watchlist.json`의 "
        "`aliases`에 정확한 표기(`Bitcoin`, `BTC-USD`, `Solana`, `SOL-USD`)를 "
        "등록하면 직접 매칭 신뢰도가 올라갑니다."
    ),
    "",
    "_관심 자산 영향은 관찰형 정보이며 매매 권유가 아닙니다._",
)
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
    # u73 — ``daily.md`` is the impact-center page, not a per-term
    # accumulation page; exclude it from the term table / chart.
    pages = sorted(
        p for p in pages_root.glob("*.md") if p.name not in ("index.md", DAILY_IMPACT_PAGE)
    )
    if not pages:
        return None
    counts = {page.stem: _count_per_page(page) for page in pages}
    chart_svg = render_cumulative_match_chart({k: v for k, v in counts.items() if v > 0})
    index_path = pages_root / "index.md"
    lines = ["# 관심 자산 누적", ""]
    if (pages_root / DAILY_IMPACT_PAGE).exists():
        lines.append(f"➡️ [오늘의 관심 자산 영향]({DAILY_IMPACT_PAGE})")
        lines.append("")
    lines.extend(_GROUP_SEMANTICS_GUIDE)
    lines.append("")
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


def render_daily_impact_page(
    target_date: date,
    center: WatchlistImpactCenter,
    *,
    segment_links: Sequence[tuple[str, str]] = (),
    link_prefix: str = "",
) -> str:
    """Render the u73 daily-first watchlist impact center page body.

    Today's grouped impacts are the first content block (not config
    prose). Public-eligible groups (Direct / Related) render in full with
    source titles. Diagnostics-only groups (Uncertain / Rejected) render
    *only* inside a collapsed ``<details>`` block with titles redacted to
    source-name + short reason — never the full title.

    ``segment_links`` is a sequence of ``(label, url)`` backlinks to the
    relevant briefing segment/date. ``link_prefix`` is prepended to relative
    URLs when the daily page lives below the docs root. Deterministic: same
    inputs → identical bytes.
    """
    iso = target_date.isoformat()
    lines = [f"# 오늘의 관심 자산 영향 — {iso}", ""]

    if not center.configured:
        lines.append(
            "_관심 목록 미설정 — `config/watchlist.json`을 추가하면 "
            "보유 종목 영향이 여기에 그룹별로 표시됩니다._"
        )
        lines.append("")
        return "\n".join(lines) + "\n"
    if center.status == "coverage_hold":
        lines.append("_데이터 수집 부족으로 매칭 판단 보류 — 추가 수집 후 재평가됩니다._")
        lines.append("")
        return "\n".join(lines) + "\n"

    lines.append(
        f"직접 {len(center.direct)} · 관련 {len(center.related)} · "
        f"보류 {len(center.uncertain)} · 제외 {len(center.rejected)}"
    )
    lines.append("")

    lines.extend(_public_group_section("직접 영향 (Direct)", center.direct, group="direct"))
    lines.extend(
        _public_group_section("관련·매크로 맥락 (Related)", center.related, group="related")
    )

    if segment_links:
        lines.append("## 관련 시황")
        lines.append("")
        for label, url in segment_links:
            lines.append(f"- [{label}]({_prefix_relative_url(url, link_prefix)})")
        lines.append("")

    if center.has_diagnostics:
        lines.extend(_diagnostics_block(center.uncertain, center.rejected))

    return "\n".join(lines).rstrip("\n") + "\n"


def _public_group_section(
    heading: str,
    matches: Sequence[WatchlistMatch],
    *,
    group: PublicWatchlistGroup,
) -> list[str]:
    out = [f"## {heading}", ""]
    if not matches:
        out.append("_해당 항목 없음._")
        out.append("")
        return out
    for match in matches:
        out.append(f"- {public_watchlist_match_summary(match, group=group)}")
    out.append("")
    return out


def _prefix_relative_url(url: str, prefix: str) -> str:
    if not prefix or "://" in url or url.startswith(("#", "/", "mailto:")):
        return url
    return posixpath.normpath(f"{prefix.rstrip('/')}/{url.lstrip('/')}")


def _diagnostics_block(
    uncertain: Sequence[WatchlistMatch],
    rejected: Sequence[RejectedCandidate],
) -> list[str]:
    """Collapsed, redacted diagnostics for uncertain + rejected candidates.

    Source titles are redacted: uncertain rows show only term + source +
    reason code; rejected rows show the user's term, the offending token,
    a reason code, the source name, and a short title hash. No full
    titles, summaries, or URLs leak into this public block.
    """
    out = ["<details>", f"<summary>{_DIAGNOSTICS_SUMMARY}</summary>", ""]
    if uncertain:
        out.append("보류 (Uncertain) — 저신뢰 텍스트 매칭, 추가 근거 필요:")
        out.append("")
        for match in uncertain:
            out.append(f"- {match.term} · {match.item.source_name} [{match.reason}]")
        out.append("")
    if rejected:
        out.append("제외 (Rejected) — 짧은 티커 오탐 억제 확인:")
        out.append("")
        for candidate in rejected:
            out.append(f"- {candidate.redacted_line()}")
        out.append("")
    out.append("</details>")
    out.append("")
    return out


def write_daily_impact_page(
    target_date: date,
    center: WatchlistImpactCenter,
    *,
    pages_root: Path = WATCHLIST_PAGES_ROOT,
    segment_links: Sequence[tuple[str, str]] = (),
) -> Path:
    """Write the daily impact center page and return its path.

    Idempotent: the page is fully regenerated each run (it reflects only
    today's impacts), so re-running for the same ``target_date`` yields
    byte-identical output.
    """
    pages_root.mkdir(parents=True, exist_ok=True)
    path = pages_root / DAILY_IMPACT_PAGE
    body = render_daily_impact_page(
        target_date,
        center,
        segment_links=segment_links,
        link_prefix=posixpath.relpath(pages_root.parent.as_posix(), pages_root.as_posix()),
    )
    path.write_text(body, encoding="utf-8")
    return path


__all__ = [
    "DAILY_IMPACT_PAGE",
    "WATCHLIST_PAGES_ROOT",
    "render_daily_impact_page",
    "update_watchlist_pages",
    "write_daily_impact_page",
]
