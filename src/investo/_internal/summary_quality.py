"""First-viewport summary validation shared by briefing and publisher.

This module is an inward pure contract: it imports only ``models`` /
``_internal`` plus text regex constants, performs no I/O, and owns the
summary safety gate used before archive writes.
"""

from __future__ import annotations

import re
from typing import Final

from investo._internal.briefing_extract import (
    CAUTION_PREFIX,
    CONCLUSION_PREFIX,
    DRIVER_PREFIX,
    FALLBACK_BY_PREFIX,
    SUMMARY_PREFIXES,
    WATERMARK_PREFIX,
)
from investo._internal.surface_quality import has_blocking_surface_issue
from investo._internal.text import MEANINGFUL_TEXT as _MEANINGFUL_TEXT_RE

_SUMMARY_PREFIXES: Final[tuple[str, ...]] = SUMMARY_PREFIXES
_LIST_MARKER_ONLY_RE: Final[re.Pattern[str]] = re.compile(r"^(?:[-*+]|\d+[.)]|[①-⑳])$")
_NUMBER_DOT_ONLY_RE: Final[re.Pattern[str]] = re.compile(r"^\d+\.$")
_EN_CONJUNCTION_TAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:vs|and|or|but|that|where|which|because|with|of|to|for|on|in|by)\.\s*$",
    re.IGNORECASE,
)
_KO_PARTICLE_TAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:과|와|및|또는|에서|의|을|를|이|가|은|는)\.\s*$"
)
_HEADING_RESIDUE_RE: Final[re.Pattern[str]] = re.compile(r"(^|\s)#{1,6}\s+\S")
_BROKEN_NUMERIC_BOLD_RE: Final[re.Pattern[str]] = re.compile(
    r"\*\*[+-]\*\*\s*\d|\d+(?:\.\d+)?%?\s*\*\*p\*\*",
    re.IGNORECASE,
)
_GENERATOR_RESIDUE_TAIL_RE: Final[re.Pattern[str]] = re.compile(r"\b(?:ROS)\s*$")
_DANGLING_LONG_TAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:기관|정책|입법|시장|수급|이슈|흐름|요인|변수|데이터)\s*$"
)
_MARKDOWN_LINK_RE: Final[re.Pattern[str]] = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARKDOWN_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[*_`]+")
_URL_RE: Final[re.Pattern[str]] = re.compile(r"https?://\S+")
_FALLBACK_BY_PREFIX: Final[dict[str, str]] = FALLBACK_BY_PREFIX


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


def repair_first_viewport_summary(markdown: str) -> str:
    """Repair malformed first-viewport summary values in-place."""
    lines = markdown.splitlines()
    changed = False
    for index, line in enumerate(lines):
        prefix = next(
            (candidate for candidate in _SUMMARY_PREFIXES if line.startswith(candidate)),
            None,
        )
        if prefix is None:
            continue
        value = line.removeprefix(prefix).strip()
        try:
            _validate_summary_value(prefix, value)
        except SummaryQualityError:
            repaired = _repair_summary_value(prefix, value)
            lines[index] = f"{prefix} {repaired}"
            changed = True
    if not changed:
        return markdown
    suffix = "\n" if markdown.endswith("\n") else ""
    return "\n".join(lines) + suffix


def _summary_value(lines: list[str], prefix: str) -> str | None:
    for line in lines:
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return None


def _validate_summary_value(prefix: str, value: str) -> None:
    if not value:
        raise SummaryQualityError(f"empty first-viewport summary line: {prefix}")
    if _LIST_MARKER_ONLY_RE.fullmatch(value) or _NUMBER_DOT_ONLY_RE.fullmatch(value):
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
    if _HEADING_RESIDUE_RE.search(value):
        raise SummaryQualityError(f"heading residue in first-viewport summary line: {prefix}")
    if _BROKEN_NUMERIC_BOLD_RE.search(value):
        raise SummaryQualityError(
            f"broken numeric emphasis in first-viewport summary line: {prefix}"
        )
    if _GENERATOR_RESIDUE_TAIL_RE.search(value):
        raise SummaryQualityError(f"generator residue in first-viewport summary line: {prefix}")
    if (
        len(value) >= 60
        and not value.rstrip().endswith(("다.", "니다.", "요.", ".", "!", "?", "…"))
        and _DANGLING_LONG_TAIL_RE.search(value)
    ):
        raise SummaryQualityError(f"dangling truncation in first-viewport summary line: {prefix}")
    if has_blocking_surface_issue(value):
        raise SummaryQualityError(f"surface-quality issue in first-viewport summary line: {prefix}")
    if _EN_CONJUNCTION_TAIL_RE.search(value) or _KO_PARTICLE_TAIL_RE.search(value):
        raise SummaryQualityError(
            f"conjunction-tail truncation in first-viewport summary line: {prefix}"
        )


def _repair_summary_value(prefix: str, value: str) -> str:
    cleaned = _MARKDOWN_LINK_RE.sub(r"\1", value)
    cleaned = _URL_RE.sub("", cleaned)
    cleaned = re.sub(r"^(?:>\s*)?#{1,6}\s+", "", cleaned).strip()
    cleaned = _GENERATOR_RESIDUE_TAIL_RE.sub("", cleaned).strip()
    cleaned = _MARKDOWN_TOKEN_RE.sub("", cleaned)
    cleaned = cleaned.replace("[", "").replace("]", "")
    cleaned = cleaned.replace("(", "").replace(")", "")
    cleaned = " ".join(cleaned.split()).strip(" -.,;:")
    cleaned = _EN_CONJUNCTION_TAIL_RE.sub("", cleaned).strip(" -.,;:")
    cleaned = _KO_PARTICLE_TAIL_RE.sub("", cleaned).strip(" -.,;:")
    if not cleaned or cleaned.isdigit() or _LIST_MARKER_ONLY_RE.fullmatch(cleaned):
        cleaned = _FALLBACK_BY_PREFIX[prefix]
    if not _MEANINGFUL_TEXT_RE.search(cleaned):
        cleaned = _FALLBACK_BY_PREFIX[prefix]
    try:
        _validate_summary_value(prefix, cleaned)
    except SummaryQualityError:
        return _FALLBACK_BY_PREFIX[prefix]
    return cleaned


__all__ = [
    "CAUTION_PREFIX",
    "CONCLUSION_PREFIX",
    "DRIVER_PREFIX",
    "WATERMARK_PREFIX",
    "SummaryQualityError",
    "repair_first_viewport_summary",
    "validate_first_viewport_summary",
]
