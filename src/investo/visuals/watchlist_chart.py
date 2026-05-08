"""u33 Step 5 — deterministic SVG chart for cumulative watchlist matches.

Given a mapping of term → cumulative match count over the run history,
render a horizontal bar chart that surfaces which tickers / assets the
user's watchlist has been catching most often. The output is a single
self-contained ``<svg>`` element with no external resources — the
publisher embeds it inline in the watchlist index page so mkdocs picks
it up without an asset round-trip.

Design:

* Sort by count desc, then term alphabetically — deterministic layout.
* Cap at the top :data:`_MAX_BARS` rows; the rest collapse into a
  trailing "기타 N건" line.
* Color: a single shade per bar, matching the existing watchlist card
  palette (no per-tier color noise — the mix is already on the
  coverage badge).
* Pure: no I/O, no clock. Same input → same SVG byte-for-byte.
"""

from __future__ import annotations

from typing import Final

_MAX_BARS: Final[int] = 8
_BAR_HEIGHT: Final[int] = 24
_BAR_GAP: Final[int] = 6
_LABEL_WIDTH: Final[int] = 110
_VALUE_WIDTH: Final[int] = 50
_CHART_WIDTH: Final[int] = 360
_TOTAL_WIDTH: Final[int] = _LABEL_WIDTH + _CHART_WIDTH + _VALUE_WIDTH
_PADDING_TOP: Final[int] = 24
_BAR_COLOR: Final[str] = "#3a8dde"
_TEXT_COLOR: Final[str] = "#1f2937"
_TITLE_COLOR: Final[str] = "#111827"


def render_cumulative_match_chart(
    matches_by_term: dict[str, int],
    *,
    title: str = "관심 자산 누적 매칭",
) -> str:
    """Render an SVG bar chart of cumulative matches per term."""
    if not matches_by_term:
        return _empty_chart(title)
    ranked = sorted(matches_by_term.items(), key=lambda kv: (-kv[1], kv[0]))
    visible = ranked[:_MAX_BARS]
    overflow = ranked[_MAX_BARS:]
    overflow_total = sum(count for _, count in overflow)
    rows = visible + ([("기타", overflow_total)] if overflow_total > 0 else [])
    max_count = max(count for _, count in rows) if rows else 1
    height = _PADDING_TOP + len(rows) * (_BAR_HEIGHT + _BAR_GAP) + 12
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_TOTAL_WIDTH} {height}" '
        f'role="img" aria-label="{title}">',
        f'<text x="12" y="16" font-family="Noto Sans KR, Arial, sans-serif" '
        f'font-size="14" fill="{_TITLE_COLOR}">{title}</text>',
    ]
    for idx, (term, count) in enumerate(rows):
        y = _PADDING_TOP + idx * (_BAR_HEIGHT + _BAR_GAP)
        bar_w = max(1, int(_CHART_WIDTH * count / max_count)) if max_count > 0 else 0
        parts.extend(
            [
                f'<text x="12" y="{y + 16}" font-family="Noto Sans KR, Arial, sans-serif" '
                f'font-size="12" fill="{_TEXT_COLOR}">{_escape(term)}</text>',
                f'<rect x="{_LABEL_WIDTH}" y="{y}" width="{bar_w}" '
                f'height="{_BAR_HEIGHT}" fill="{_BAR_COLOR}" rx="3"/>',
                f'<text x="{_LABEL_WIDTH + bar_w + 6}" y="{y + 16}" '
                f'font-family="Noto Sans KR, Arial, sans-serif" '
                f'font-size="12" fill="{_TEXT_COLOR}">{count}</text>',
            ]
        )
    parts.append("</svg>")
    return "".join(parts)


def _empty_chart(title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_TOTAL_WIDTH} 60" '
        f'role="img" aria-label="{title}">'
        f'<text x="12" y="36" font-family="Noto Sans KR, Arial, sans-serif" '
        f'font-size="13" fill="{_TEXT_COLOR}">집계할 매칭이 아직 없습니다.</text>'
        "</svg>"
    )


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


__all__ = [
    "render_cumulative_match_chart",
]
