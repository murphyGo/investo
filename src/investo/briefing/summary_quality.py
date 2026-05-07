"""Publish-time validation for first-viewport segmented briefing summaries."""

from __future__ import annotations

import re
from typing import Final

_SUMMARY_PREFIXES: Final[tuple[str, ...]] = (
    "> **오늘의 결론**:",
    "> **핵심 동인**:",
    "> **주의할 점**:",
)
_LIST_MARKER_ONLY_RE: Final[re.Pattern[str]] = re.compile(r"^(?:[-*+]|\d+[.)])$")
_MEANINGFUL_TEXT_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9가-힣]")


class SummaryQualityError(ValueError):
    """Raised when a briefing first-viewport summary is unsafe to publish."""


def validate_first_viewport_summary(markdown: str) -> None:
    """Validate the three reader-facing summary lines before publish."""
    lines = markdown.splitlines()
    for prefix in _SUMMARY_PREFIXES:
        value = _summary_value(lines, prefix)
        if value is None:
            raise SummaryQualityError(f"missing first-viewport summary line: {prefix}")
        _validate_summary_value(prefix, value)


def _summary_value(lines: list[str], prefix: str) -> str | None:
    for line in lines:
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return None


def _validate_summary_value(prefix: str, value: str) -> None:
    if not value:
        raise SummaryQualityError(f"empty first-viewport summary line: {prefix}")
    if _LIST_MARKER_ONLY_RE.fullmatch(value):
        raise SummaryQualityError(f"list-marker-only first-viewport summary line: {prefix}")
    if not _MEANINGFUL_TEXT_RE.search(value):
        raise SummaryQualityError(f"meaningless first-viewport summary line: {prefix}")
    if value.count("**") % 2 != 0:
        raise SummaryQualityError(
            f"unbalanced bold marker in first-viewport summary line: {prefix}"
        )
    if value.count("[") != value.count("]") or value.count("(") != value.count(")"):
        raise SummaryQualityError(
            f"unbalanced markdown link in first-viewport summary line: {prefix}"
        )


__all__ = ["SummaryQualityError", "validate_first_viewport_summary"]
