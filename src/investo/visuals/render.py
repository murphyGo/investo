"""Deterministic SVG renderer for briefing visual cards."""

from __future__ import annotations

import html
import re
from typing import Final

from investo.briefing.segments import SEGMENT_LABELS
from investo.visuals.cards import (
    DataConfidenceCardInput,
    MarketSnapshotCardInput,
    PriceSnapshotCardInput,
    WatchlistRelevanceCardInput,
)

SVG_WIDTH: Final[int] = 1200
SVG_HEIGHT: Final[int] = 630
_DISCLAIMER = "정보 제공용 시황 카드"
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARKDOWN_TOKEN_RE = re.compile(r"[*_`>#]")
_LEADING_LIST_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")


def render_card_svg(
    card: (
        DataConfidenceCardInput
        | MarketSnapshotCardInput
        | PriceSnapshotCardInput
        | WatchlistRelevanceCardInput
    ),
) -> str:
    """Render a card input to a standalone SVG string."""
    if isinstance(card, DataConfidenceCardInput):
        return _render_data_confidence(card)
    if isinstance(card, MarketSnapshotCardInput):
        return _render_market_snapshot(card)
    if isinstance(card, PriceSnapshotCardInput):
        return _render_price_snapshot(card)
    return _render_watchlist(card)


def wrap_visual_text(text: str, *, max_chars: int, max_lines: int) -> tuple[str, ...]:
    """Clean and wrap visual text with deterministic truncation."""
    cleaned = _clean_visual_text(text)
    words = cleaned.split()
    if not words:
        return ("n/a",)
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = _truncate_word(word, max_chars)
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if words and _clean_visual_text(" ".join(words)) != " ".join(lines):
        lines[-1] = _truncate_line(lines[-1], max_chars)
    return tuple(lines)


def _render_data_confidence(card: DataConfidenceCardInput) -> str:
    missing = ", ".join(card.missing_categories) if card.missing_categories else "없음"
    rows = [
        ("상태", card.coverage_status),
        ("수집", f"{card.item_count}건"),
        ("소스", f"{card.source_count}개"),
        ("누락", missing),
    ]
    return _svg_document(
        title=f"{SEGMENT_LABELS[card.segment]} 데이터 신뢰도",
        subtitle=card.target_date.isoformat(),
        body=_metric_rows(rows),
    )


def _render_market_snapshot(card: MarketSnapshotCardInput) -> str:
    lines = [
        _text_block("오늘의 결론", card.conclusion, y=180),
        _text_block("핵심 동인", card.main_driver, y=300),
        _text_block("주의할 점", card.caution, y=420),
    ]
    return _svg_document(
        title=f"{SEGMENT_LABELS[card.segment]} 시장 스냅샷",
        subtitle=f"{card.target_date.isoformat()} · 데이터 {card.coverage_status}",
        body="\n".join(lines),
    )


def _render_price_snapshot(card: PriceSnapshotCardInput) -> str:
    y = 180
    rows: list[str] = []
    for row in card.rows[:6]:
        details = f"{row.price} · {row.percent_change}"
        if row.volume:
            details = f"{details} · V {row.volume}"
        rows.append(_row_line(row.symbol, details, y=y))
        y += 62
    return _svg_document(
        title=f"{SEGMENT_LABELS[card.segment]} 가격 스냅샷",
        subtitle=card.target_date.isoformat(),
        body="\n".join(rows),
    )


def _render_watchlist(card: WatchlistRelevanceCardInput) -> str:
    if not card.configured:
        body = _text_block(
            "관심 목록",
            "미설정 - config/watchlist.json 추가 시 관련 항목 표시",
            y=210,
        )
    elif not card.rows:
        body = _text_block("관심 목록", "직접 연결된 수집 항목 없음", y=210)
    else:
        y = 180
        lines: list[str] = []
        for row in card.rows:
            lines.append(_row_line(row.term, row.title, y=y))
            y += 76
        body = "\n".join(lines)
    return _svg_document(
        title=f"{SEGMENT_LABELS[card.segment]} 관심 자산 관련성",
        subtitle=f"{card.target_date.isoformat()} · 매칭 {card.total_matches}건",
        body=body,
    )


def _svg_document(*, title: str, subtitle: str, body: str) -> str:
    safe_title = _escape(title)
    safe_subtitle = _escape(subtitle)
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" '
            f'viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" role="img" aria-label="{safe_title}">',
            '<rect width="1200" height="630" fill="#f7f5ef"/>',
            '<rect x="40" y="40" width="1120" height="550" rx="8" fill="#ffffff" '
            'stroke="#253238" stroke-width="3"/>',
            f'<text x="80" y="118" font-family="Arial, sans-serif" font-size="48" '
            f'font-weight="700" fill="#1d2b2f">{safe_title}</text>',
            f'<text x="80" y="158" font-family="Arial, sans-serif" font-size="24" '
            f'fill="#617176">{safe_subtitle}</text>',
            body,
            f'<text x="80" y="555" font-family="Arial, sans-serif" font-size="22" '
            f'fill="#7b5e2a">{_DISCLAIMER}</text>',
            "</svg>",
        ]
    )


def _metric_rows(rows: list[tuple[str, str]]) -> str:
    y = 220
    rendered: list[str] = []
    for label, value in rows:
        rendered.append(_row_line(label, value, y=y))
        y += 72
    return "\n".join(rendered)


def _text_block(label: str, text: str, *, y: int) -> str:
    lines = wrap_visual_text(text, max_chars=58, max_lines=2)
    rendered = [
        f'<text x="80" y="{y}" font-family="Arial, sans-serif" font-size="24" '
        f'font-weight="700" fill="#476169">{_escape(label)}</text>'
    ]
    text_y = y + 40
    for line in lines:
        rendered.append(
            f'<text x="80" y="{text_y}" font-family="Arial, sans-serif" '
            f'font-size="32" fill="#1d2b2f">{_escape(line)}</text>'
        )
        text_y += 38
    return "\n".join(rendered)


def _row_line(label: str, value: str, *, y: int) -> str:
    label_text = _escape(_clean_visual_text(label))
    value_lines = wrap_visual_text(value, max_chars=64, max_lines=1)
    return "\n".join(
        [
            f'<text x="90" y="{y}" font-family="Arial, sans-serif" font-size="30" '
            f'font-weight="700" fill="#14555f">{label_text}</text>',
            f'<text x="310" y="{y}" font-family="Arial, sans-serif" font-size="30" '
            f'fill="#1d2b2f">{_escape(value_lines[0])}</text>',
        ]
    )


def _clean_visual_text(text: str) -> str:
    cleaned = _MARKDOWN_LINK_RE.sub(r"\1", text)
    cleaned = _LEADING_LIST_RE.sub("", cleaned)
    cleaned = _MARKDOWN_TOKEN_RE.sub("", cleaned)
    return " ".join(cleaned.split())


def _truncate_word(word: str, max_chars: int) -> str:
    if len(word) <= max_chars:
        return word
    return f"{word[: max_chars - 1]}…"


def _truncate_line(line: str, max_chars: int) -> str:
    if len(line) <= max_chars:
        return line
    return f"{line[: max_chars - 1]}…"


def _escape(text: str) -> str:
    return html.escape(text, quote=True)


__all__ = ["SVG_HEIGHT", "SVG_WIDTH", "render_card_svg", "wrap_visual_text"]
