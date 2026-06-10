"""Deterministic same-run daily thesis line (u99)."""

from __future__ import annotations

import logging
import re
from typing import Final

from investo.models.bundle_context import DailyThesisDecision

_logger = logging.getLogger(__name__)

DAILY_THESIS_MARKER: Final[str] = "> **오늘의 큰 그림:**"
_FIRST_SECTION_MARKER: Final[str] = "## ①"
_DIGIT_RE: Final[re.Pattern[str]] = re.compile(r"\d")
_THESIS_LINE_RE: Final[re.Pattern[str]] = re.compile(
    rf"(?m)^{re.escape(DAILY_THESIS_MARKER)}[^\n]*(?:\n\n)?"
)
_MAX_LINE_CHARS: Final[int] = 180


def render_daily_thesis_line(decision: DailyThesisDecision) -> str:
    """Return the public thesis line or ``""`` when omitted/invalid."""

    if decision.mode == "omit" or not decision.line:
        return ""
    line = decision.line.strip()
    if not line.startswith(DAILY_THESIS_MARKER):
        return ""
    if len(line) > _MAX_LINE_CHARS:
        return ""
    if _DIGIT_RE.search(line):
        return ""
    return line


def inject_daily_thesis_line(text: str, decision: DailyThesisDecision) -> str:
    """Replace/remove existing thesis marker and insert before section ①."""

    rendered = render_daily_thesis_line(decision)
    without_existing = _THESIS_LINE_RE.sub("", text).lstrip("\n")
    if not rendered:
        return without_existing

    block = f"{rendered}\n\n"
    first_section = without_existing.find(_FIRST_SECTION_MARKER)
    if first_section == -1:
        _logger.warning("daily_thesis.no_section_anchor")
        return without_existing
    return without_existing[:first_section] + block + without_existing[first_section:]


__all__ = [
    "DAILY_THESIS_MARKER",
    "inject_daily_thesis_line",
    "render_daily_thesis_line",
]
