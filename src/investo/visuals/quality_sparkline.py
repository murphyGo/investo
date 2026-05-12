"""Deterministic SVG sparkline for the public quality history page."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Final, Literal

from investo.briefing.quality_eval import QualityHistoryRow
from investo.visuals.provenance import VisualProvenanceManifest, _investo_version
from investo.visuals.render import _CARD_STYLE

SVG_WIDTH: Final[int] = 600
SVG_HEIGHT: Final[int] = 180
_PANEL_HEIGHT: Final[int] = 60
_PADDING_X: Final[int] = 56
_LINE_WIDTH: Final[int] = SVG_WIDTH - (_PADDING_X * 2)
_METRICS: Final[tuple[tuple[str, str, str], ...]] = (
    ("source_liveness", "소스 라이브니스", "#167a6f"),
    ("figures_presence", "수치 인용", "#2457a6"),
    ("figures_verified", "수치 검증", "#7e22ce"),  # u55 — sibling to figures_presence
    ("fallback_ratio", "폴백 비율", "#b65f18"),
)


def render_quality_sparkline(rows: list[QualityHistoryRow]) -> bytes:
    """Render the 30-day quality history as a standalone SVG document."""
    data_rows = [row for row in rows if row.has_data]
    if len(data_rows) < 2:
        return _empty_svg().encode("utf-8")

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" '
        'role="img" aria-label="최근 30일 데이터 품질 추세">',
        _CARD_STYLE,
        f'<rect class="card-bg" x="0" y="0" width="{SVG_WIDTH}" height="{SVG_HEIGHT}"/>',
        f'<rect class="card-frame" x="8" y="8" width="{SVG_WIDTH - 16}" '
        f'height="{SVG_HEIGHT - 16}" rx="6"/>',
    ]
    for idx, (field, label, color) in enumerate(_METRICS):
        top = idx * _PANEL_HEIGHT
        parts.append(
            f'<text class="card-label" x="20" y="{top + 35}" '
            'font-family="&quot;Noto Sans KR&quot;, Arial, sans-serif" '
            f'font-size="12">{html.escape(label)}</text>'
        )
        parts.append(
            f'<line x1="{_PADDING_X}" y1="{top + 44}" '
            f'x2="{SVG_WIDTH - 20}" y2="{top + 44}" stroke="#9aa6ad" '
            'stroke-width="1" opacity="0.35"/>'
        )
        for points in _metric_segments(rows, field, panel_top=top):
            parts.append(
                f'<polyline data-metric="{field}" points="{points}" fill="none" '
                f'stroke="{color}" stroke-width="2.5" stroke-linecap="round" '
                'stroke-linejoin="round"/>'
            )
    parts.append("</svg>")
    return "".join(parts).encode("utf-8")


def build_quality_sparkline_manifest(
    *,
    asset_relative_path: str,
    generated_at: datetime,
) -> VisualProvenanceManifest:
    """Build provenance metadata for a generated quality sparkline asset."""
    return VisualProvenanceManifest(
        asset_path=asset_relative_path,
        source_type="generated_svg",
        source_attribution="investo 품질 시계열로 결정적 SVG 생성",
        generated_at=generated_at,
        generator="investo.visuals.quality_sparkline",
        version=_investo_version(),
        content_type="image/svg+xml",
        dimensions=(SVG_WIDTH, SVG_HEIGHT),
        additional_metadata={"history_window": "30d"},
        card_kind="quality-sparkline",
    )


def _metric_segments(
    rows: list[QualityHistoryRow],
    field: Literal["source_liveness", "figures_presence", "fallback_ratio"] | str,
    *,
    panel_top: int,
) -> list[str]:
    segments: list[list[str]] = []
    current: list[str] = []
    count = max(len(rows), 1)
    for idx, row in enumerate(rows):
        value = getattr(row, field)
        if value is None:
            if current:
                segments.append(current)
                current = []
            continue
        x = _PADDING_X + round((_LINE_WIDTH * idx) / max(count - 1, 1), 2)
        y = panel_top + 48 - round(float(value) * 38, 2)
        current.append(f"{x:g},{y:g}")
    if current:
        segments.append(current)
    return [" ".join(segment) for segment in segments if len(segment) >= 2]


def _empty_svg() -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" '
        'role="img" aria-label="최근 30일 데이터 품질 추세">'
        f"{_CARD_STYLE}"
        f'<rect class="card-bg" x="0" y="0" width="{SVG_WIDTH}" height="{SVG_HEIGHT}"/>'
        f'<rect class="card-frame" x="8" y="8" width="{SVG_WIDTH - 16}" '
        f'height="{SVG_HEIGHT - 16}" rx="6"/>'
        '<text class="card-title" x="40" y="82" '
        'font-family="&quot;Noto Sans KR&quot;, Arial, sans-serif" '
        'font-size="22">데이터 부족</text>'
        '<text class="card-text" x="40" y="112" '
        'font-family="&quot;Noto Sans KR&quot;, Arial, sans-serif" '
        'font-size="13">품질 이력이 더 쌓이면 30일 추세선을 표시합니다.</text>'
        "</svg>"
    )


__all__ = [
    "SVG_HEIGHT",
    "SVG_WIDTH",
    "build_quality_sparkline_manifest",
    "render_quality_sparkline",
]
