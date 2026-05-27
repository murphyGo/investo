"""TL;DR block synthesis pass (``## 한눈에 보기``).

Move-only extraction from the pre-split ``reader_format`` module (u81).
"""

from __future__ import annotations

import re
from typing import Final

from investo.publisher.reader_format._constants import (
    _FIRST_SECTION_MARKER,
    TLDR_HEADER,
    _logger,
)

# Markers used by ``ensure_tldr_block`` to:
#   1. detect whether the LLM already emitted a TL;DR block (idempotent),
#   2. locate the right insertion site (after the header callouts, before
#      ``## ①``).
_CONCLUSION_CALLOUT_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*오늘의 결론\*\*\s*:\s*(.+?)$", re.MULTILINE
)
_DRIVER_CALLOUT_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*핵심 동인\*\*\s*:\s*(.+?)$", re.MULTILINE
)
_CAUTION_CALLOUT_RE: Final[re.Pattern[str]] = re.compile(
    r"^>\s*\*\*주의할 점\*\*\s*:\s*(.+?)$", re.MULTILINE
)


def ensure_tldr_block(text: str, *, segment: str | None = None) -> str:
    """Insert a ``## 한눈에 보기`` H2 + 3-bullet block if absent.

    Idempotent: when the block already exists (Stage 2 prompt compliance
    is the *common* case), the text is returned unchanged. When missing,
    we fall back to a heuristic that re-uses the three header callouts
    (``오늘의 결론`` / ``핵심 동인`` / ``주의할 점``) as bullet bodies —
    they already carry magnitude + direction + caution, so the placeholder
    is informative rather than generic.

    When *neither* the block nor the callouts exist (a malformed input
    that the LLM never recovered), the text is returned unchanged and a
    WARNING is logged — the caller's downstream gates (``verify_disclaimer``,
    summary-fidelity) will surface the underlying problem; we do not
    silently insert empty bullets.
    """
    if TLDR_HEADER in text:
        return text

    conclusion = _capture_first(text, _CONCLUSION_CALLOUT_RE)
    driver = _capture_first(text, _DRIVER_CALLOUT_RE)
    caution = _capture_first(text, _CAUTION_CALLOUT_RE)

    if conclusion is None and driver is None and caution is None:
        _logger.warning(
            "reader_format.tldr_missing",
            extra={"segment": segment, "fallback": "none"},
        )
        return text

    bullets = [
        f"- {conclusion}" if conclusion else "- (요약 데이터 부족)",
        f"- {driver}" if driver else "- (핵심 동인 데이터 부족)",
        f"- {caution}" if caution else "- (주의 데이터 부족)",
    ]
    block = f"{TLDR_HEADER}\n\n" + "\n".join(bullets) + "\n\n"

    insertion = text.find(_FIRST_SECTION_MARKER)
    if insertion == -1:
        # No body sections — append to end (still better than dropping).
        _logger.warning(
            "reader_format.tldr_missing",
            extra={"segment": segment, "fallback": "appended"},
        )
        return f"{text.rstrip()}\n\n{block}"

    _logger.info(
        "reader_format.tldr_inserted",
        extra={"segment": segment, "source": "callout_fallback"},
    )
    return text[:insertion] + block + text[insertion:]


def _capture_first(text: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(text)
    if match is None:
        return None
    return match.group(1).strip()
