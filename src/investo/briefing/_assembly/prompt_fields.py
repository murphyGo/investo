"""LLM-input prompt-field shaping (truncation + URL rendering).

These helpers shape values destined for the *LLM prompt* — they change
for a prompt/token-budget reason, NOT for an output-rendering reason
(which is why they live here and not in :mod:`markdown_render`; see the
u83 plan correction 2026-05-28).

Moved verbatim from ``briefing/pipeline.py`` in the u83 decomposition;
behavior-preserving (move-only).
"""

from __future__ import annotations

from typing import Final

_STAGE2_URL_MAX_CHARS: Final[int] = 160


def _truncate_prompt_field(value: str, limit: int) -> str:
    """Bound a prompt field while preserving a clear ellipsis marker."""
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)] + "…"


def _render_prompt_url(url: object | None) -> str:
    if url is None:
        return ""
    rendered = _truncate_prompt_field(str(url), _STAGE2_URL_MAX_CHARS)
    return f" ({rendered})"


__all__ = [
    "_STAGE2_URL_MAX_CHARS",
    "_render_prompt_url",
    "_truncate_prompt_field",
]
