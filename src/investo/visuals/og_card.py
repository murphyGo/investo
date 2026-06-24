"""OG image card renderer for the public site (u29 site-discovery-v2).

Each segmented publish writes ``site_docs/assets/og-card.svg`` and its
PNG twin ``site_docs/assets/og-card.png`` so the
mkdocs site can advertise an up-to-date hero card via the
``<meta property="og:image">`` tag in the rendered HTML.

The OG card is a 1200x630 SVG (Open Graph's recommended ratio) listing
the publish date and the three-segment 오늘의 결론 quote lines. u38 adds
the PNG twin because major OG consumers (Telegram / Slack / Twitter /
LinkedIn) do not reliably unfurl SVG ``og:image`` payloads.

Determinism: same target_date + segment_briefings dict → byte-identical
SVG. The renderer takes pre-extracted conclusion strings rather than
parsing the briefing markdown itself so unit tests can drive every
visual without constructing a full ``Briefing``.

Project rules:

* No raw stdlib XML (CLAUDE.md #6) — emission only, no parsing.
* No paid APIs (CLAUDE.md #4) — pure local SVG composition.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

from investo._internal._io import write_atomic, write_atomic_bytes
from investo._internal.briefing_extract import extract_conclusion
from investo.models import Briefing
from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    SEGMENT_LABELS,
    US_EQUITY,
    MarketSegment,
)
from investo.visuals.provenance import (
    VisualProvenanceManifest,
    build_generated_svg_provenance,
    manifest_path_for,
    write_manifest,
)

OG_CARD_RELATIVE_PATH: Final[Path] = Path("site_docs/assets/og-card.svg")
OG_CARD_PNG_RELATIVE_PATH: Final[Path] = Path("site_docs/assets/og-card.png")
OG_CARD_WIDTH: Final[int] = 1200
OG_CARD_HEIGHT: Final[int] = 630
_SEGMENTS: Final[tuple[MarketSegment, ...]] = (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)
_FONT: Final[str] = "&quot;Noto Sans KR&quot;, Arial, sans-serif"
# Surface-specific fallback when the chokepoint extractor returns
# ``None`` — DEBT-060 consolidation 2026-05-08.
_OG_FALLBACK_TEXT: Final[str] = "결론 인용을 추출하지 못했습니다."


@dataclass(frozen=True, slots=True)
class OGCardInput:
    """Resolved data fed to :func:`render_og_card_svg`."""

    target_date: date
    segment_lines: tuple[tuple[MarketSegment, str], ...]


def build_og_card_input(
    target_date: date,
    segment_briefings: dict[MarketSegment, Briefing],
) -> OGCardInput:
    """Pull conclusion lines off each segmented briefing for the OG card."""
    rows: list[tuple[MarketSegment, str]] = []
    for segment in _SEGMENTS:
        briefing = segment_briefings.get(segment)
        if briefing is None:
            rows.append((segment, _OG_FALLBACK_TEXT))
            continue
        rows.append((segment, _extract_conclusion(briefing.rendered_markdown)))
    return OGCardInput(target_date=target_date, segment_lines=tuple(rows))


def render_og_card_svg(card: OGCardInput) -> str:
    """Render ``card`` to a deterministic 1200x630 SVG string."""
    body_lines: list[str] = []
    y = 230
    for segment, conclusion in card.segment_lines:
        label = SEGMENT_LABELS[segment]
        body_lines.append(
            f'<text class="og-label" x="80" y="{y}" font-family="{_FONT}" '
            f'font-size="32" font-weight="700">{html.escape(label)}</text>'
        )
        wrapped = _wrap(conclusion, max_chars=44, max_lines=2)
        text_y = y + 42
        for line in wrapped:
            body_lines.append(
                f'<text class="og-text" x="80" y="{text_y}" font-family="{_FONT}" '
                f'font-size="28">{html.escape(line)}</text>'
            )
            text_y += 36
        y += 130

    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{OG_CARD_WIDTH}" '
            f'height="{OG_CARD_HEIGHT}" viewBox="0 0 {OG_CARD_WIDTH} {OG_CARD_HEIGHT}" '
            f'role="img" aria-label="Investo {card.target_date.isoformat()} 시황 OG 카드">',
            _OG_STYLE,
            f'<rect class="og-bg" width="{OG_CARD_WIDTH}" height="{OG_CARD_HEIGHT}"/>',
            f'<rect class="og-frame" x="40" y="40" width="{OG_CARD_WIDTH - 80}" '
            f'height="{OG_CARD_HEIGHT - 80}" rx="12" stroke-width="3"/>',
            f'<text class="og-title" x="80" y="138" font-family="{_FONT}" '
            f'font-size="56" font-weight="700">Investo · 오늘의 시황</text>',
            f'<text class="og-subtitle" x="80" y="186" font-family="{_FONT}" '
            f'font-size="30">{card.target_date.isoformat()}</text>',
            *body_lines,
            f'<text class="og-disclaimer" x="80" y="{OG_CARD_HEIGHT - 60}" '
            f'font-family="{_FONT}" font-size="22">투자 자문이 아닙니다 · '
            f"investo (MIT)</text>",
            "</svg>",
        ]
    )


def write_og_card(
    target_date: date,
    segment_briefings: dict[MarketSegment, Briefing],
    *,
    out_path: Path | None = None,
) -> tuple[Path, ...]:
    """Compose and atomically write the OG card SVG, PNG, and manifests."""
    target = out_path if out_path is not None else OG_CARD_RELATIVE_PATH
    png_target = target.with_suffix(".png")
    card = build_og_card_input(target_date, segment_briefings)
    svg = render_og_card_svg(card)
    svg_bytes = svg.encode("utf-8")
    # cairosvg renders to a real path, so emit the PNG to a tmp sibling
    # first, then publish both assets atomically via the shared helper —
    # no bare ``os.replace`` write pattern remains in this module.
    png_tmp = png_target.with_suffix(png_target.suffix + ".render.tmp")
    render_og_card_png(svg_bytes, output_path=png_tmp)
    png_bytes = png_tmp.read_bytes()
    png_tmp.unlink(missing_ok=True)
    write_atomic(target, svg)
    write_atomic_bytes(png_target, png_bytes)
    written = (target, png_target)
    _write_og_card_manifests(svg_path=target, png_path=png_target)
    return (*written, manifest_path_for(target), manifest_path_for(png_target))


def render_og_card_png(svg_bytes: bytes, *, output_path: Path) -> Path:
    """Render an OG-card SVG byte string to a 1200x630 PNG file."""
    from cairosvg import svg2png  # type: ignore[import-untyped]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    svg2png(
        bytestring=svg_bytes,
        write_to=str(output_path),
        output_width=OG_CARD_WIDTH,
        output_height=OG_CARD_HEIGHT,
    )
    return output_path


_OG_STYLE: Final[str] = (
    "<style>"
    ".og-bg{fill:#f7f5ef;}"
    ".og-frame{fill:#ffffff;stroke:#253238;}"
    ".og-title{fill:#1d2b2f;}"
    ".og-subtitle{fill:#617176;}"
    ".og-label{fill:#476169;}"
    ".og-text{fill:#1d2b2f;}"
    ".og-disclaimer{fill:#7b5e2a;}"
    "@media (prefers-color-scheme: dark){"
    ".og-bg{fill:#0f1417;}"
    ".og-frame{fill:#1a2026;stroke:#9fb1ba;}"
    ".og-title{fill:#f4f6f8;}"
    ".og-subtitle{fill:#bfcdd4;}"
    ".og-label{fill:#a8c0c8;}"
    ".og-text{fill:#e8eef1;}"
    ".og-disclaimer{fill:#e2c489;}"
    "}"
    "</style>"
)


def _extract_conclusion(rendered_markdown: str) -> str:
    """Resolve the conclusion line with OG-card fallback wording.

    Thin wrapper over :func:`investo.briefing.extract.extract_conclusion`
    so the OG card owns only its surface-specific fallback string;
    DEBT-060 consolidation 2026-05-08.
    """
    value = extract_conclusion(rendered_markdown)
    if value is None:
        return _OG_FALLBACK_TEXT
    return value


def _wrap(text: str, *, max_chars: int, max_lines: int) -> tuple[str, ...]:
    if not text:
        return ("",)
    words = text.split()
    if not words:
        return (text,)
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word[: max_chars - 1] + "…" if len(word) > max_chars else word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    return tuple(lines)


def _write_og_card_manifests(*, svg_path: Path, png_path: Path) -> None:
    generated_at = datetime.now(tz=UTC)
    svg_manifest = build_generated_svg_provenance(
        asset_relative_path=svg_path.name,
        card_kind="og-card",
        generated_at=generated_at,
        width=OG_CARD_WIDTH,
        height=OG_CARD_HEIGHT,
        source_attribution="investo 자체 데이터로 결정적 OG 카드 생성",
    )
    write_manifest(svg_manifest, svg_path)
    png_manifest = VisualProvenanceManifest(
        asset_path=png_path.name,
        source_type="generated_svg",
        source_attribution=svg_manifest.source_attribution,
        generated_at=generated_at,
        generator=svg_manifest.generator,
        version=svg_manifest.version,
        content_type="image/png",
        dimensions=(OG_CARD_WIDTH, OG_CARD_HEIGHT),
        additional_metadata={"source_svg": svg_path.name},
        card_kind="og-card",
    )
    write_manifest(png_manifest, png_path)


__all__ = [
    "OG_CARD_HEIGHT",
    "OG_CARD_PNG_RELATIVE_PATH",
    "OG_CARD_RELATIVE_PATH",
    "OG_CARD_WIDTH",
    "OGCardInput",
    "build_og_card_input",
    "render_og_card_png",
    "render_og_card_svg",
    "write_og_card",
]
