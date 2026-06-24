"""Deterministic publish-calendar heatmap renderer (u29 site-discovery-v2).

The output is a single GitHub-contribution-graph-style SVG inlined into
``site_docs/archive/index.md``. One column per ISO week, one row per
weekday (월 → 일). Each cell encodes:

* whether a briefing was archived on that date (``archive/{segment}/
  YYYY/MM/YYYY-MM-DD.md`` exists for at least one segment), and
* the segment-coverage status of that publish — derived from the
  per-segment count: 3 segments → 정상 (green), 1-2 → 부분 (yellow), 0 →
  미발행 (gray). Insufficient days are rendered as 부족 (red) when
  marker files indicate so (see :func:`render_publish_heatmap`).

Determinism contract: same input dict → byte-identical SVG. The
renderer takes a precomputed ``coverage`` mapping rather than touching
the filesystem itself so that publisher tests can drive every visual
state without seeding archive dirs. The companion
:func:`scan_publish_coverage` is the production seam — it walks the
archive root and produces the coverage mapping the renderer consumes.

Dark-mode policy mirrors :mod:`investo.visuals.render` (u26 DEBT-049):
fill colors swap under ``@media (prefers-color-scheme: dark)`` so the
same SVG works on both mkdocs Material light / dark schemes. The
toggle limitation (visitors who manually flip the mkdocs theme via the
toolbar without changing OS preference will see the OS-preferred
palette) is the same as the briefing cards — accepted under the same
DEBT-049 rationale.

No raw stdlib XML used — the SVG is assembled as a string literal with
escaped attributes, the same approach as ``visuals.render``. (Project
rule #6: ``defusedxml`` for *parsing*; this module only emits.)
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Final, Literal

from investo.models.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY, MarketSegment

PublishStatus = Literal["normal", "partial", "insufficient", "absent"]
_STATUS_ORDER: Final[tuple[PublishStatus, ...]] = (
    "normal",
    "partial",
    "insufficient",
    "absent",
)
_SEGMENTS: Final[tuple[MarketSegment, ...]] = (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)

# Project start anchor — declared in the plan as 2026-04-26. The
# heatmap walks weeks from this anchor's Monday up to the most recent
# date known to the publisher.
PROJECT_START: Final[date] = date(2026, 4, 26)

_CELL_SIZE: Final[int] = 14
_CELL_GAP: Final[int] = 3
_ROW_LABEL_WIDTH: Final[int] = 28
_TOP_PADDING: Final[int] = 22
_BOTTOM_PADDING: Final[int] = 24
_LEFT_PADDING: Final[int] = 8
_RIGHT_PADDING: Final[int] = 8

_WEEKDAY_LABELS: Final[tuple[str, ...]] = ("월", "화", "수", "목", "금", "토", "일")

_LEGEND_LABELS: Final[dict[PublishStatus, str]] = {
    "normal": "정상",
    "partial": "부분",
    "insufficient": "부족",
    "absent": "미발행",
}


@dataclass(frozen=True, slots=True)
class CalendarCell:
    """Per-day publish state used by :func:`render_publish_heatmap`."""

    target_date: date
    status: PublishStatus


def render_publish_heatmap(
    cells: list[CalendarCell],
    *,
    today: date,
) -> str:
    """Render the deterministic SVG for ``cells``.

    Cells are placed Monday-first in week-of-year columns. Days outside
    the cell list (e.g. days that haven't happened yet, or days before
    the earliest cell) are rendered as transparent placeholders so the
    grid keeps its shape.

    ``today`` clamps the right edge of the grid: cells beyond ``today``
    are not rendered (otherwise ISO-week math would expose half-blank
    columns at the end of the grid every week).
    """
    if not cells:
        # Empty grid — single row with a friendly placeholder so the
        # archive page never renders an empty SVG.
        return _empty_svg()

    by_date = {cell.target_date: cell for cell in cells}
    earliest = min(cell.target_date for cell in cells)
    # Anchor at Monday on or before the earliest cell so column 0 is a
    # well-defined week-Monday.
    anchor = earliest - timedelta(days=earliest.weekday())
    last = max(today, max(cell.target_date for cell in cells))

    weeks: list[list[CalendarCell | None]] = []
    cursor = anchor
    while cursor <= last:
        week: list[CalendarCell | None] = []
        for day_offset in range(7):
            day = cursor + timedelta(days=day_offset)
            if day < earliest or day > today:
                week.append(None)
                continue
            existing = by_date.get(day)
            if existing is None:
                week.append(CalendarCell(target_date=day, status="absent"))
            else:
                week.append(existing)
        weeks.append(week)
        cursor += timedelta(days=7)

    return _render_svg(weeks, anchor=anchor)


def scan_publish_coverage(
    archive_root: Path,
    *,
    today: date,
    project_start: date = PROJECT_START,
) -> list[CalendarCell]:
    """Walk the archive root + return one cell per project day.

    A day is ``normal`` when all three segment markdowns exist, ``partial``
    when at least one but not all three exist, ``absent`` otherwise.
    ``insufficient`` is reserved for explicit manifest-driven downgrades —
    not produced by this scan today; the renderer accepts it from
    caller-supplied coverage maps for forward-compat.
    """
    cells: list[CalendarCell] = []
    if today < project_start:
        return cells

    cursor = project_start
    while cursor <= today:
        present = sum(
            1
            for segment in _SEGMENTS
            if (
                archive_root
                / segment
                / f"{cursor.year:04d}"
                / f"{cursor.month:02d}"
                / f"{cursor.isoformat()}.md"
            ).exists()
        )
        if present == len(_SEGMENTS):
            status: PublishStatus = "normal"
        elif present > 0:
            status = "partial"
        else:
            status = "absent"
        if status != "absent":
            cells.append(CalendarCell(target_date=cursor, status=status))
        cursor += timedelta(days=1)
    return cells


# ---------------------------------------------------------------------------
# SVG building
# ---------------------------------------------------------------------------


_HEATMAP_STYLE: Final[str] = (
    "<style>"
    ".u29-cell-normal{fill:#2ea44f;}"
    ".u29-cell-partial{fill:#f1c40f;}"
    ".u29-cell-insufficient{fill:#cf222e;}"
    ".u29-cell-absent{fill:#d0d7de;}"
    ".u29-text{fill:#1d2b2f;font-family:&quot;Noto Sans KR&quot;,Arial,sans-serif;}"
    ".u29-legend{fill:#1d2b2f;font-family:&quot;Noto Sans KR&quot;,Arial,sans-serif;}"
    "@media (prefers-color-scheme: dark){"
    ".u29-cell-normal{fill:#3fb950;}"
    ".u29-cell-partial{fill:#d29922;}"
    ".u29-cell-insufficient{fill:#f85149;}"
    ".u29-cell-absent{fill:#30363d;}"
    ".u29-text{fill:#e6edf3;}"
    ".u29-legend{fill:#e6edf3;}"
    "}"
    "</style>"
)


def _render_svg(weeks: list[list[CalendarCell | None]], *, anchor: date) -> str:
    cell_step = _CELL_SIZE + _CELL_GAP
    width = _LEFT_PADDING + _ROW_LABEL_WIDTH + len(weeks) * cell_step + _RIGHT_PADDING
    height = _TOP_PADDING + 7 * cell_step + _BOTTOM_PADDING

    rects: list[str] = []
    # Weekday labels (left margin).
    for row_index, label in enumerate(_WEEKDAY_LABELS):
        y = _TOP_PADDING + row_index * cell_step + _CELL_SIZE - 2
        rects.append(
            f'<text class="u29-text" x="{_LEFT_PADDING}" y="{y}" '
            f'font-size="11">{html.escape(label)}</text>'
        )

    for column_index, week in enumerate(weeks):
        x = _LEFT_PADDING + _ROW_LABEL_WIDTH + column_index * cell_step
        for row_index, cell in enumerate(week):
            if cell is None:
                continue
            y = _TOP_PADDING + row_index * cell_step
            klass = f"u29-cell-{cell.status}"
            label = f"{cell.target_date.isoformat()} · {_LEGEND_LABELS[cell.status]}"
            rects.append(
                f'<rect class="{klass}" x="{x}" y="{y}" '
                f'width="{_CELL_SIZE}" height="{_CELL_SIZE}" rx="2" ry="2">'
                f"<title>{html.escape(label)}</title>"
                f"</rect>"
            )

    # Legend along the bottom row.
    legend_y = height - 6
    legend_x = _LEFT_PADDING + _ROW_LABEL_WIDTH
    legend_parts: list[str] = []
    for status in _STATUS_ORDER:
        legend_parts.append(
            f'<rect class="u29-cell-{status}" x="{legend_x}" y="{legend_y - 11}" '
            f'width="11" height="11" rx="2" ry="2"/>'
        )
        legend_parts.append(
            f'<text class="u29-legend" x="{legend_x + 16}" y="{legend_y - 1}" '
            f'font-size="11">{html.escape(_LEGEND_LABELS[status])}</text>'
        )
        legend_x += 70

    anchor_label = (
        f"{anchor.isoformat()} ~ {(anchor + timedelta(days=len(weeks) * 7 - 1)).isoformat()}"
    )

    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
            f'aria-label="투자 시황 발행 캘린더 ({html.escape(anchor_label)})">',
            _HEATMAP_STYLE,
            *rects,
            *legend_parts,
            "</svg>",
        ]
    )


def _empty_svg() -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="40" '
        'viewBox="0 0 200 40" role="img" aria-label="투자 시황 발행 캘린더 (비어있음)">'
        f"{_HEATMAP_STYLE}"
        '<text class="u29-text" x="8" y="24" font-size="12">'
        "발행 이력이 아직 없습니다.</text>"
        "</svg>"
    )


__all__ = [
    "PROJECT_START",
    "CalendarCell",
    "PublishStatus",
    "render_publish_heatmap",
    "scan_publish_coverage",
]
