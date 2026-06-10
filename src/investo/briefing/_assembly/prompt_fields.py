"""LLM-input prompt-field shaping (truncation + URL rendering).

These helpers shape values destined for the *LLM prompt* — they change
for a prompt/token-budget reason, NOT for an output-rendering reason
(which is why they live here and not in :mod:`markdown_render`; see the
u83 plan correction 2026-05-28).

Moved from ``briefing/pipeline.py`` in the u83 decomposition; u93 adds
Stage 1-specific caps while preserving the existing Stage 2 URL helper.
"""

from __future__ import annotations

from typing import Final
from urllib.parse import urlsplit, urlunsplit

_STAGE2_URL_MAX_CHARS: Final[int] = 160
_STAGE1_TITLE_MAX_CHARS: Final[int] = 180
_STAGE1_SUMMARY_MAX_CHARS: Final[int] = 320
_STAGE1_URL_PATH_QUERY_MAX_CHARS: Final[int] = 96


def _truncate_prompt_field(value: str, limit: int) -> str:
    """Bound a prompt field while preserving a clear ellipsis marker."""
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)] + "…"


def _truncate_stage1_prompt_field(value: str, limit: int) -> str:
    """Bound Stage 1 fields with an ASCII marker for byte-count stability."""
    if len(value) <= limit:
        return value
    return value[: max(limit - 3, 0)] + "..."


def _render_stage1_prompt_title(title: str) -> str:
    return _truncate_stage1_prompt_field(title, _STAGE1_TITLE_MAX_CHARS)


def _render_stage1_prompt_summary(summary: str | None) -> str:
    if summary is None:
        return ""
    return _truncate_stage1_prompt_field(summary, _STAGE1_SUMMARY_MAX_CHARS)


def _render_stage1_prompt_url(url: object | None) -> str:
    if url is None:
        return ""
    value = str(url)
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return _truncate_stage1_prompt_field(value, _STAGE1_URL_PATH_QUERY_MAX_CHARS)
    path_query = parsed.path
    if parsed.query:
        path_query = f"{path_query}?{parsed.query}"
    compact_path_query = _truncate_stage1_prompt_field(
        path_query,
        _STAGE1_URL_PATH_QUERY_MAX_CHARS,
    )
    return urlunsplit((parsed.scheme, parsed.netloc, compact_path_query, "", ""))


def _render_prompt_url(url: object | None) -> str:
    if url is None:
        return ""
    rendered = _truncate_prompt_field(str(url), _STAGE2_URL_MAX_CHARS)
    return f" ({rendered})"


__all__ = [
    "_STAGE1_SUMMARY_MAX_CHARS",
    "_STAGE1_TITLE_MAX_CHARS",
    "_STAGE1_URL_PATH_QUERY_MAX_CHARS",
    "_STAGE2_URL_MAX_CHARS",
    "_render_prompt_url",
    "_render_stage1_prompt_summary",
    "_render_stage1_prompt_title",
    "_render_stage1_prompt_url",
    "_truncate_prompt_field",
    "_truncate_stage1_prompt_field",
]
