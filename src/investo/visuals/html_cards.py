"""Readable, deterministic views of the same immutable visual card inputs (u178)."""

from __future__ import annotations

import re
from html import escape
from urllib.parse import quote, urlsplit

from investo._internal.public_quality_language import (
    PUBLIC_SOURCE_DETAIL_TEXT,
    project_public_quality_language,
)
from investo._internal.surface_quality import find_surface_quality_issues
from investo.models.segments import COVERAGE_STATUS_LABELS, SEGMENT_LABELS
from investo.models.watchlist import DEFAULT_BUNDLE_BADGE_LABEL
from investo.visuals.cards import (
    DataConfidenceCardInput,
    MarketSnapshotCardInput,
    PriceSnapshotCardInput,
)
from investo.visuals.render import _RenderableCard


def _text(value: str) -> str:
    return escape(value, quote=True)


def _public(value: str) -> str:
    return _text(project_public_quality_language(value))


_INLINE = re.compile(r"\*\*([^*\n]+)\*\*|(?<!!)\[([^\[\]\n]+)\]\(([^()\s]+)\)")


def _public_inline(value: str) -> str:
    """Only escaped text, strong emphasis and well-formed HTTP(S) links.

    Unsafe/malformed Markdown remains literal so existing trust scanners can
    still observe it. Images, autolinks and arbitrary HTML never become active.
    """
    value = project_public_quality_language(value)
    parts: list[str] = []
    offset = 0
    for match in _INLINE.finditer(value):
        parts.append(_text(value[offset : match.start()]))
        if match.group(1) is not None:
            parts.append(f"<strong>{_text(match.group(1))}</strong>")
        else:
            label, url = match.group(2), match.group(3)
            try:
                parsed = urlsplit(url)
                safe = parsed.scheme in ("http", "https") and bool(parsed.hostname)
            except ValueError:
                safe = False
            if safe and not find_surface_quality_issues(match.group()):
                href = quote(url, safe=":/?=&%+-._~#@[]")
                parts.append(f'<a href="{_text(href)}">{_text(label)}</a>')
            else:
                parts.append(_text(match.group()))
        offset = match.end()
    parts.append(_text(value[offset:]))
    return "".join(parts)


def render_card_html(card: _RenderableCard) -> str:
    """Project existing fields without recomputing numbers, status or quote times."""
    titles = {
        "data-confidence": "데이터 신뢰도",
        "market-snapshot": "시장 스냅샷",
        "price-snapshot": "가격 스냅샷",
        "watchlist-relevance": "관심 자산 관련성",
    }
    title = f"{SEGMENT_LABELS[card.segment]} {titles[card.kind]}"
    parts = [f'<p class="investo-data-meta">대상일 {card.target_date.isoformat()}</p>']
    if isinstance(card, DataConfidenceCardInput):
        parts.append(
            "<dl><dt>근거 상태</dt>"
            f"<dd>{COVERAGE_STATUS_LABELS[card.coverage_status]}</dd>"
            f"<dt>수집 항목</dt><dd>{card.item_count}건</dd>"
            f"<dt>수집 소스</dt><dd>{card.source_count}개</dd>"
            "<dt>누락 카테고리</dt><dd>"
            f"{_public(', '.join(card.missing_categories) or '없음')}</dd>"
            f"<dt>근거 안내</dt><dd>{_public(', '.join(card.reason_labels) or '없음')}</dd></dl>"
            f"<p>{PUBLIC_SOURCE_DETAIL_TEXT}</p>"
        )
    elif isinstance(card, MarketSnapshotCardInput):
        parts.append(
            '<p class="investo-data-meta">근거 상태: '
            f"{COVERAGE_STATUS_LABELS[card.coverage_status]}</p>"
        )
        parts.extend(
            f"<dl><dt>{label}</dt><dd>{_public_inline(value)}</dd></dl>"
            for label, value in (
                ("오늘의 결론", card.conclusion),
                ("핵심 동인", card.main_driver),
                ("주의할 점", card.caution),
            )
        )
    elif isinstance(card, PriceSnapshotCardInput):
        parts.append(
            '<p class="investo-data-meta">행 라벨에 명시되지 않은 구체 기준 시각은 미확인입니다. '
            "대상일은 개별 가격의 조회·마감 시각을 뜻하지 않습니다.</p>"
        )
        if card.segment == "crypto":
            parts.append('<p class="investo-data-meta">UTC 24h 스냅샷</p>')
        headers = ("종목·기준", "가격", "등락", "거래량", "고가", "저가", "출처")
        rows = []
        for row in card.rows:
            values = (
                f"{row.symbol} · {row.label}" if row.label else row.symbol,
                row.price,
                row.percent_change,
                row.volume or "미확인",
                row.high or "미확인",
                row.low or "미확인",
                row.source_name,
            )
            rows.append("<tr>" + "".join(f"<td>{_text(value)}</td>" for value in values) + "</tr>")
        parts.append(
            f'<div class="investo-data-table" role="region" aria-label="{_text(title)} 표" '
            'tabindex="0"><table>'
            f"<caption>{_text(title)} — 입력 값과 출처</caption><thead><tr>"
            + "".join(f'<th scope="col">{header}</th>' for header in headers)
            + "</tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></div>"
        )
    else:
        if not card.configured:
            parts.append("<p>관심 목록 미설정</p>")
        else:
            if card.is_default_bundle:
                parts.append(f"<p>{_text(DEFAULT_BUNDLE_BADGE_LABEL)}</p>")
            parts.append(f"<p>관심 자산 공개 매칭 {card.total_matches}건</p>")
            if not card.rows:
                parts.append("<p>공개 연결 항목 없음</p>")
            for match_row in card.rows:
                source = _text(match_row.source_name)
                link = ""
                if match_row.url is not None:
                    url = quote(str(match_row.url), safe=":/?=&%+-._~#@[]")
                    link = f'<p markdown="1">[원문 보기]({url})</p>'
                parts.append(
                    f'<p markdown="0"><strong>{_text(match_row.term)}</strong> '
                    f"· {_text(match_row.kind)}<br>{source}</p>\n\n"
                    f'<p markdown="0">{_public_inline(match_row.title)}</p>\n\n{link}'
                )
    body = "\n".join(parts)
    if isinstance(card, DataConfidenceCardInput):
        return (
            f'<details class="investo-data-card" data-card-kind="{card.kind}" markdown="0">'
            f"<summary>{_text(title)} — 텍스트로 읽기</summary>\n{body}\n</details>"
        )
    mode = "1" if card.kind == "watchlist-relevance" else "0"
    return (
        f'<section class="investo-data-card" data-card-kind="{card.kind}" markdown="{mode}" '
        f'aria-label="{_text(title)}"><h3>{_text(title)}</h3>\n{body}\n</section>'
    )
