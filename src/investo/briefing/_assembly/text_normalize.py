"""Section parsing + summary-line normalization + sentence splitting.

References:
    Functional Design L3 / R1 — six fixed Stage 2 headers
    NFR Requirements AC-6.3 — parse_six_sections round-trip PBT

Moved verbatim from ``briefing/pipeline.py`` in the u83 decomposition;
behavior-preserving (move-only). ``parse_six_sections`` keeps its
import path via re-export from ``briefing/pipeline.py``.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

from investo.briefing._text.patterns import (
    MEANINGFUL_TEXT as _MEANINGFUL_TEXT_RE,
)
from investo.briefing.prompts import STAGE2_SECTION_HEADERS

_MARKDOWN_LINK_RE: Final[re.Pattern[str]] = re.compile(r"!?\[([^\]]*)\]\([^)]+\)")
_MARKDOWN_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[*_`~]+")
_LEADING_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^(?:>\s*)?#{1,6}\s+")
_LEADING_MARKDOWN_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:>\s*)?(?:(?:[-*+])|\d+[.)]|[①-⑳])\s*"
)
# u79 — ``_MEANINGFUL_TEXT_RE`` now single-sourced in
# :mod:`investo.briefing._text.patterns` (identical literal previously
# duplicated here and in ``summary_quality``); imported above.
# Reject patterns the summary sentence picker uses to skip a candidate
# (matches mirror summary_quality gate-side rejects so the producer
# never emits what the gate would block).
_MARKER_ONLY_RE: Final[re.Pattern[str]] = re.compile(r"^(?:[-*+]|\d+[.)]|[①-⑳])$")
# Sentence terminator markers, longest-first so ``니다.`` matches before
# the shorter ``다.`` substring inside it.
_SENTENCE_TERMINATORS: Final[tuple[str, ...]] = (
    "니다.",
    "다.",
    "요.",
    "?",
    "!",
)


def parse_six_sections(markdown: str) -> tuple[str, str, str, str, str, str]:
    """Split ``markdown`` on the six fixed Stage 2 headers (FD L3 / R1).

    Returns the six bodies in section order. Raises ``ValueError`` if:

    * any of the six headers is missing,
    * any of the six headers appears more than once
      (inline duplicates would silently fuse adjacent bodies),
    * the headers appear out of order,
    * any body (text between consecutive headers, after strip) is empty.

    The input is NFC-normalized before search. Korean numerals (① … ⑥)
    are sensitive to Unicode normalization form (NFC vs NFD); LLMs
    occasionally emit NFD even when the prompt and constants are NFC.
    A single normalization mismatch would otherwise burn all 3 retry
    attempts before failing.

    Used by both ``_synthesize`` (validation gate before returning) and
    ``generate_briefing`` (final extraction into ``Briefing`` fields).
    Pure: no side effects, no I/O.
    """
    markdown = unicodedata.normalize("NFC", markdown)

    positions: list[int] = []
    for header in STAGE2_SECTION_HEADERS:
        count = markdown.count(header)
        if count == 0:
            raise ValueError(f"missing section header: {header!r}")
        if count > 1:
            raise ValueError(
                f"section header {header!r} appears {count} times; "
                f"each header must be unique to avoid silent body fusion"
            )
        positions.append(markdown.find(header))

    for i in range(len(positions) - 1):
        if positions[i] >= positions[i + 1]:
            raise ValueError(
                f"section headers out of order: {STAGE2_SECTION_HEADERS[i]!r} at {positions[i]} "
                f"is not before {STAGE2_SECTION_HEADERS[i + 1]!r} at {positions[i + 1]}"
            )

    bodies: list[str] = []
    for i, header in enumerate(STAGE2_SECTION_HEADERS):
        start = positions[i] + len(header)
        end = positions[i + 1] if i + 1 < len(positions) else len(markdown)
        body = markdown[start:end].strip()
        if not body:
            raise ValueError(f"section body for {header!r} is blank")
        bodies.append(body)

    return (bodies[0], bodies[1], bodies[2], bodies[3], bodies[4], bodies[5])


def _clean_summary_line(line: str) -> str:
    """Strip markdown punctuation off a single line and return its prose.

    Returns ``""`` if the line is empty after stripping, or if all that
    remains is a list marker / punctuation with no meaningful text.
    """
    cleaned = line.strip()
    if not cleaned:
        return ""
    cleaned = _LEADING_HEADING_RE.sub("", cleaned).strip()
    cleaned = _LEADING_MARKDOWN_RE.sub("", cleaned).strip()
    cleaned = _MARKDOWN_LINK_RE.sub(r"\1", cleaned)
    cleaned = _MARKDOWN_TOKEN_RE.sub("", cleaned)
    cleaned = " ".join(cleaned.split())
    if not _MEANINGFUL_TEXT_RE.search(cleaned):
        return ""
    if _MARKER_ONLY_RE.fullmatch(cleaned):
        return ""
    return cleaned


def _split_into_sentences(normalized: str) -> list[str]:
    """Split a single normalized prose line into sentence-shaped chunks.

    Splits on the closed set of Korean sentence terminators
    (``다.``, ``니다.``, ``요.``, ``?``, ``!``) so each candidate ends
    on a complete clause. The terminator stays attached to its
    preceding chunk so the caller can decide whether to keep it. If no
    terminator is found the whole string is returned as a single chunk.
    """
    chunks: list[str] = []
    remaining = normalized
    while remaining:
        best_idx = -1
        best_marker = ""
        for marker in _SENTENCE_TERMINATORS:
            idx = remaining.find(marker)
            if idx < 0:
                continue
            if best_idx < 0 or idx < best_idx:
                best_idx = idx
                best_marker = marker
        if best_idx < 0:
            chunks.append(remaining.strip())
            break
        chunk = remaining[: best_idx + len(best_marker)].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[best_idx + len(best_marker) :].lstrip()
    return [c for c in chunks if c]


__all__ = [
    "_clean_summary_line",
    "_split_into_sentences",
    "parse_six_sections",
]
