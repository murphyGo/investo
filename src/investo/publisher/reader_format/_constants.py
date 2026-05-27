"""Shared markers, regexes, and the package logger for ``reader_format``.

Single source for every constant referenced by more than one pass module in
the :mod:`investo.publisher.reader_format` package (u81 split). Pass-private
markers/regexes that only one pass uses stay in that pass's module; this file
holds only the genuinely cross-pass shared surface.

The shared logger is named ``investo.publisher.reader_format`` (the package
``__name__``) so that every pass logs under the *same* logger regardless of
which submodule it now lives in — preserving the pre-split logger name that
the existing tests bind to via ``caplog.at_level(logger=...)``.
"""

from __future__ import annotations

import logging
import re
from typing import Final

# Shared logger: every pass module imports this so the logger name stays
# ``investo.publisher.reader_format`` exactly as before the package split.
_logger = logging.getLogger("investo.publisher.reader_format")


# ---------------------------------------------------------------------------
# Cross-pass markers
# ---------------------------------------------------------------------------

# TL;DR header — used by the TL;DR pass (to detect/insert) and the
# first-viewport disclaimer pass (placement anchor).
TLDR_HEADER: Final[str] = "## 한눈에 보기"

# First body-section marker — used by the TL;DR pass, the disclaimer pass,
# and the reflow pass as a placement anchor.
_FIRST_SECTION_MARKER: Final[str] = "## ①"

# Disclaimer footer anchor — used by the sentence-audit pass (to strip the
# footer for tone metrics) and the orchestration chain (to keep the footer
# byte-identical for publish verification).
_DISCLAIMER_FOOTER_ANCHOR: Final[str] = "## ⑦ 면책조항"


# ---------------------------------------------------------------------------
# Cross-pass regexes
# ---------------------------------------------------------------------------

# Section header / bullet — used by the watchpoint-audit pass and the
# meaning-line pass to slice section bodies.
_SECTION_HEADER_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+(?P<header>.+?)$", re.MULTILINE)
_BULLET_RE: Final[re.Pattern[str]] = re.compile(r"^\s*[-*]\s+(.+?)$", re.MULTILINE)

# Markdown table-row matcher — used by the emphasis pass (skip cells) and the
# sentence-audit pass (strip table rows from tone metrics).
_TABLE_ROW_RE: Final[re.Pattern[str]] = re.compile(r"^\s*\|.*\|\s*$")


# ---------------------------------------------------------------------------
# u76 meaning-line markers (shared so they remain a single source)
# ---------------------------------------------------------------------------

MEANING_MARKER: Final[str] = "> **그래서 의미는?** "
MEANING_FALLBACK: Final[str] = (
    "> **그래서 의미는?** 현재 수집 근거가 부족해 방향보다 확인 필요 항목으로만 봅니다."
)
# Max Korean-visible chars AFTER the marker (the implication text itself).
MEANING_MAX_CHARS: Final[int] = 80
