"""Deterministic same-run daily thesis line (u99)."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Final

from investo.models.bundle_context import DAILY_THESIS_FALLBACK_LINE, DailyThesisDecision
from investo.publisher.errors import DailyThesisConsistencyError

_logger = logging.getLogger(__name__)

DAILY_THESIS_MARKER: Final[str] = "> **오늘의 큰 그림:**"
_FIRST_SECTION_MARKER: Final[str] = "## ①"
_DIGIT_RE: Final[re.Pattern[str]] = re.compile(r"\d")
_THESIS_LINE_RE: Final[re.Pattern[str]] = re.compile(
    rf"(?m)^{re.escape(DAILY_THESIS_MARKER)}[^\n]*(?:\n\n)?"
)
_MAX_LINE_CHARS: Final[int] = 180


def _select_daily_thesis_line(
    decision: DailyThesisDecision,
    *,
    segment: str | None,
) -> str | None:
    if segment is not None and decision.per_segment_lines:
        return decision.per_segment_lines.get(segment)
    return decision.line


def render_daily_thesis_line(
    decision: DailyThesisDecision,
    *,
    segment: str | None = None,
) -> str:
    """Return the public thesis line or ``""`` when omitted/invalid."""

    line = _select_daily_thesis_line(decision, segment=segment)
    if decision.mode == "omit" or not line:
        return ""
    line = line.strip()
    if not line.startswith(DAILY_THESIS_MARKER):
        return ""
    if len(line) > _MAX_LINE_CHARS:
        return ""
    if _DIGIT_RE.search(line):
        return ""
    return line


def inject_daily_thesis_line(
    text: str,
    decision: DailyThesisDecision,
    *,
    segment: str | None = None,
) -> str:
    """Replace/remove existing thesis marker and insert before section ①."""

    rendered = render_daily_thesis_line(decision, segment=segment)
    return inject_rendered_daily_thesis_line(text, rendered)


def inject_rendered_daily_thesis_line(text: str, rendered: str) -> str:
    """Inject one already-validated producer-plan thesis payload."""

    if rendered and (
        not rendered.startswith(DAILY_THESIS_MARKER)
        or len(rendered) > _MAX_LINE_CHARS
        or _DIGIT_RE.search(rendered)
    ):
        raise ValueError("rendered daily thesis line is not canonical")
    without_existing = _THESIS_LINE_RE.sub("", text).lstrip("\n")
    if not rendered:
        return without_existing

    block = f"{rendered}\n\n"
    first_section = without_existing.find(_FIRST_SECTION_MARKER)
    if first_section == -1:
        _logger.warning("daily_thesis.no_section_anchor")
        return without_existing
    return without_existing[:first_section] + block + without_existing[first_section:]


def assert_distinct_daily_thesis_lines(lines_by_segment: Mapping[str, str]) -> None:
    """Block the u124 regression where all published segments share one thesis."""

    rendered = {
        segment: line.strip()
        for segment, line in lines_by_segment.items()
        if line.strip() and line.strip() != DAILY_THESIS_FALLBACK_LINE
    }
    if len(rendered) < 3:
        return
    unique_lines = set(rendered.values())
    if len(unique_lines) == 1:
        raise DailyThesisConsistencyError(
            segments=tuple(rendered),
            line=next(iter(unique_lines)),
        )


__all__ = [
    "DAILY_THESIS_FALLBACK_LINE",
    "DAILY_THESIS_MARKER",
    "assert_distinct_daily_thesis_lines",
    "inject_daily_thesis_line",
    "inject_rendered_daily_thesis_line",
    "render_daily_thesis_line",
]
