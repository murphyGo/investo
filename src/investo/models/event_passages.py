"""Bounded exact source spans; no language-model or network authority (u184)."""

from __future__ import annotations

import re


def passage_spans(text: str, *, limit: int = 6000) -> tuple[tuple[int, int], ...]:
    """Keep complete paragraphs/sentences, never a cut-off qualifying clause.

    Oversized paragraphs are split at sentence boundaries. A sentence over 1200
    characters is omitted rather than represented as a complete assertion.
    Offsets always address the original normalized source buffer.
    """
    if not 1 <= limit <= 6000:
        raise ValueError("passage budget outside approved bounds")
    units: list[tuple[int, int]] = []
    for paragraph in re.finditer(r"[^\n]+", text):
        start, end = paragraph.span()
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start == end:
            continue
        if end - start <= 1200:
            units.append((start, end))
            continue
        cursor = start
        for boundary in re.finditer(r"(?<=[.!?。])\s+(?=[A-Z가-힣\"“])", text[start:end]):
            stop = start + boundary.start()
            if 0 < stop - cursor <= 1200:
                units.append((cursor, stop))
            cursor = start + boundary.end()
        if 0 < end - cursor <= 1200:
            units.append((cursor, end))
    # Source order remains stable; a later qualifying sentence stays available
    # when the leading material is too long. No synthesized ellipsis is added.
    result: list[tuple[int, int]] = []
    used = 0
    for start, end in units:
        if len(result) == 6:
            break
        if used + end - start <= limit:
            result.append((start, end))
            used += end - start
    return tuple(result)
