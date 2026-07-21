"""Pure first-viewport briefing prefix and extraction helpers."""

from __future__ import annotations

from typing import Final

# Canonical first-viewport prefix literals. The briefing pipeline emits
# these markers; publisher, visuals, and recent-context consumers parse them.
CONCLUSION_PREFIX: Final[str] = "> **오늘의 결론**:"
DRIVER_PREFIX: Final[str] = "> **핵심 동인**:"
CAUTION_PREFIX: Final[str] = "> **주의할 점**:"
WATERMARK_PREFIX: Final[str] = "**기준 시각**:"
WATCHLIST_IMPACT_PREFIX: Final[str] = "> **내 관심 자산 영향**:"

SUMMARY_PREFIXES: Final[tuple[str, ...]] = (
    CONCLUSION_PREFIX,
    DRIVER_PREFIX,
    CAUTION_PREFIX,
)
FALLBACK_BY_PREFIX: Final[dict[str, str]] = {
    CONCLUSION_PREFIX: "확인된 요약이 부족합니다.",
    DRIVER_PREFIX: "핵심 동인은 추가 확인이 필요합니다.",
    CAUTION_PREFIX: "관전 포인트는 데이터 회복 후 보강합니다.",
}


def _extract_first(rendered_markdown: str, prefix: str) -> str | None:
    """Return the trimmed value following the first ``prefix``-anchored line."""
    for line in rendered_markdown.splitlines():
        if line.startswith(prefix):
            value = line.removeprefix(prefix).strip()
            if value:
                return value
            return None
    return None


def extract_conclusion(rendered_markdown: str) -> str | None:
    """Extract the ``> **오늘의 결론**:`` value, ``None`` on miss."""
    return _extract_first(rendered_markdown, CONCLUSION_PREFIX)


def extract_key_drivers(rendered_markdown: str) -> str | None:
    """Extract the ``> **핵심 동인**:`` value, ``None`` on miss."""
    return _extract_first(rendered_markdown, DRIVER_PREFIX)


def extract_caution(rendered_markdown: str) -> str | None:
    """Extract the ``> **주의할 점**:`` value, ``None`` on miss."""
    return _extract_first(rendered_markdown, CAUTION_PREFIX)


def extract_watermark(rendered_markdown: str) -> str | None:
    """Extract the ``**기준 시각**:`` value, ``None`` on miss."""
    return _extract_first(rendered_markdown, WATERMARK_PREFIX)


def extract_watchlist_impact(rendered_markdown: str) -> str | None:
    """Extract the final reader-layout watchlist-impact value, if present."""

    return _extract_first(rendered_markdown, WATCHLIST_IMPACT_PREFIX)


__all__ = [
    "CAUTION_PREFIX",
    "CONCLUSION_PREFIX",
    "DRIVER_PREFIX",
    "FALLBACK_BY_PREFIX",
    "SUMMARY_PREFIXES",
    "WATCHLIST_IMPACT_PREFIX",
    "WATERMARK_PREFIX",
    "extract_caution",
    "extract_conclusion",
    "extract_key_drivers",
    "extract_watchlist_impact",
    "extract_watermark",
]
