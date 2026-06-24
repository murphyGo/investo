"""u56 first-viewport short disclaimer pass (segment-aware).

Move-only extraction from the pre-split ``reader_format`` module (u81).
"""

from __future__ import annotations

from typing import Final

from investo.models.segments import MarketSegment
from investo.publisher.reader_format._constants import (
    _FIRST_SECTION_MARKER,
    TLDR_HEADER,
)

# Short disclaimer text per segment. The canonical footer
# (``DISCLAIMER`` / ``DISCLAIMER_CRYPTO`` in ``briefing.disclaimer``)
# remains untouched as the publish gate; this short blockquote is an
# *additive* surface that lands above-the-fold for reader UX. u56
# evaluation Finding #5 (crypto needs its own §10 reference) is what
# motivates the segment-aware variant.
SHORT_DISCLAIMER_EQUITY: Final[str] = "> 정보 제공용 자동 시황이며 매매 권유가 아닙니다."
SHORT_DISCLAIMER_CRYPTO: Final[str] = (
    "> 정보 제공용 자동 시황이며 가상자산 매매 권유가 아닙니다. "
    "가상자산은 가격 변동성이 매우 큽니다."
)


def _short_disclaimer_for(segment: MarketSegment) -> str:
    if segment == "crypto":
        return SHORT_DISCLAIMER_CRYPTO
    return SHORT_DISCLAIMER_EQUITY


def emit_first_viewport_disclaimer(text: str, segment: MarketSegment) -> str:
    """Insert a one-line short disclaimer blockquote in the first viewport.

    Placement order (first match wins):
      1. Immediately before ``## 한눈에 보기`` (TLDR header) when present.
      2. Immediately before ``## ①`` (first section) when (1) is absent.
      3. Prepended to the document when neither anchor exists.

    Idempotent only when the segment-appropriate short disclaimer is already
    present in the first ~30 rendered lines. If a later transform moved or
    duplicated it below the first viewport, remove the stale line and reinsert
    it near the top.
    """
    short = _short_disclaimer_for(segment)
    head = "\n".join(text.splitlines()[:30])
    if short in head:
        return text

    text = _remove_short_disclaimer_line(text, short)
    block = f"{short}\n\n"

    insertion = text.find(TLDR_HEADER)
    if insertion == -1:
        insertion = text.find(_FIRST_SECTION_MARKER)
    if insertion == -1 or text.count("\n", 0, insertion) >= 28:
        return f"{block}{text}"
    return text[:insertion] + block + text[insertion:]


def _remove_short_disclaimer_line(text: str, short: str) -> str:
    lines = text.splitlines(keepends=True)
    changed = False
    kept: list[str] = []
    for line in lines:
        if line.strip() == short:
            changed = True
            continue
        kept.append(line)
    if not changed:
        return text
    return "".join(kept)
