"""u32 Step 2 — Stage 3 numeric cross-check.

Stage 2's LLM output is a six-section briefing. Numeric tokens
embedded in that output (prices, percentages, market caps) are the
single most fragile claim — a hallucinated figure breaks reader trust
even when the surrounding prose is otherwise faithful.

This module is the producer-side guard. After Stage 2 returns, the
briefing pipeline calls :func:`find_unverified` with the raw output
and the Stage 1 candidate items the prompt was built from. The helper
returns the deterministic ordered tuple of numeric tokens present in
Stage 2 output but not present in any candidate's title / summary /
raw_metadata. Empty tuple → quiet success. Non-empty → the brief
header is decorated with a one-line warning callout
(``> **Numeric warning**: ...``) and the orchestrator can surface a
soft operator alert downstream.

Pure helpers — no I/O, no LLM call. Determinism keeps the publish
path fixture-replayable: feeding the same `(stage2_output, candidates)`
twice yields the same warning text byte-for-byte.

Tokenisation rules:

* Match decimal numbers (``5,200.00``, ``0.42``, ``108200``) with
  optional thousands separators and optional trailing ``%`` /
  ``$`` / ``%`` / ``원`` / ``$`` units.
* Strip thousands separators when comparing against the candidate
  set so ``5,200`` matches ``5200`` in the raw_metadata.
* Numbers with at most 2 digits and no decimal/unit (years like
  ``2026``, counts like ``5건``) are intentionally ignored — they
  are too common in prose to flag usefully and the persona-cited
  failure cases (``평균 수익률 약 12%``, ``시총 합산 $1.7조``)
  always carry a unit or decimal.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Final

from investo.models import NormalizedItem

# Match a decimal number with optional thousands separators and an
# optional trailing unit token. The number must have a decimal point,
# a thousands separator, OR a trailing percent / currency / Korean
# unit — bare 1-3 digit integers slip through (they are too common in
# prose to flag usefully without context).
_NUMERIC_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z0-9])"  # left boundary — number not preceded by alnum
    r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d+)"  # the number itself
    r"(\s?(?:%|\$|¥|€|원|조|억|만)?)"  # optional unit
)
_THOUSANDS_RE: Final[re.Pattern[str]] = re.compile(r",")
_LITERAL_NUMBER_RE: Final[re.Pattern[str]] = re.compile(r"\d+(?:\.\d+)?")
# Numbers with fewer than these characters and no unit are
# intentionally ignored — see module docstring.
_MIN_FLAGGABLE_DIGITS: Final[int] = 4


def extract_flaggable_numbers(text: str) -> tuple[str, ...]:
    """Return the deterministic ordered tuple of flaggable numeric tokens.

    A token is *flaggable* if it carries a decimal point, a thousands
    separator, a trailing unit (``%``, ``$``, ``¥``, ``€``, ``원``,
    ``조``, ``억``, ``만``), or has at least :data:`_MIN_FLAGGABLE_DIGITS`
    digits. Bare 1-3-digit integers are ignored — too common in prose
    to flag usefully and not the failure mode the gate is guarding.
    """
    out: list[str] = []
    seen: set[str] = set()
    for match in _NUMERIC_RE.finditer(text):
        raw_number = match.group(1)
        unit = match.group(2).strip() if match.group(2) else ""
        token = f"{raw_number}{unit}"
        if not _is_flaggable(raw_number, unit):
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return tuple(out)


def _is_flaggable(raw: str, unit: str) -> bool:
    if "." in raw or "," in raw:
        return True
    if unit:
        return True
    digit_count = sum(ch.isdigit() for ch in raw)
    return digit_count >= _MIN_FLAGGABLE_DIGITS


def _normalise_for_compare(token: str) -> str:
    """Collapse thousands separators + lowercase for comparison."""
    return _THOUSANDS_RE.sub("", token).lower()


def _candidate_haystack(candidates: Sequence[NormalizedItem]) -> set[str]:
    """Build the set of numeric substrings present in any Stage 1 candidate.

    Each candidate's ``title``, ``summary`` (when not None), and every
    string-shaped ``raw_metadata`` value contributes its raw decimal
    substrings to the haystack. We compare extracted numbers against
    the haystack via substring containment (with thousands separators
    collapsed) so ``5,200.00`` from Stage 2 matches ``5200`` in the
    yfinance ``close`` field.
    """
    haystack: set[str] = set()
    for item in candidates:
        for source_text in _candidate_text_blobs(item):
            for match in _LITERAL_NUMBER_RE.finditer(source_text):
                haystack.add(match.group(0).lower())
    return haystack


def _candidate_text_blobs(item: NormalizedItem) -> list[str]:
    blobs = [item.title]
    if item.summary:
        blobs.append(item.summary)
    for value in item.raw_metadata.values():
        if isinstance(value, str):
            blobs.append(value)
    return blobs


def find_unverified(
    stage2_text: str,
    candidates: Sequence[NormalizedItem],
) -> tuple[str, ...]:
    """Return numeric tokens in Stage 2 output absent from any candidate.

    Each token is the raw token (with optional unit) as it appears in
    Stage 2 output. Comparison strips thousands separators and is
    case-insensitive. Order matches the first occurrence in
    ``stage2_text``. A returned empty tuple means the briefing is
    numerically verified end-to-end.
    """
    flagged = extract_flaggable_numbers(stage2_text)
    if not flagged:
        return ()
    haystack = _candidate_haystack(candidates)
    if not haystack:
        return flagged
    out: list[str] = []
    for token in flagged:
        bare = _bare_number(token)
        normalised = _normalise_for_compare(bare)
        if any(normalised in candidate for candidate in haystack):
            continue
        if any(candidate in normalised for candidate in haystack):
            continue
        out.append(token)
    return tuple(out)


def _bare_number(token: str) -> str:
    match = _LITERAL_NUMBER_RE.search(token.replace(",", ""))
    return match.group(0) if match else token


def render_warning_line(unverified: Sequence[str]) -> str:
    """Render the brief-header callout for ``unverified`` tokens."""
    if not unverified:
        return ""
    capped = list(unverified[:5])
    suffix = " 외" if len(unverified) > 5 else ""
    return f"> **수치 검증 경고**: 입력에서 확인되지 않은 수치 — {', '.join(capped)}{suffix}\n"


__all__ = [
    "extract_flaggable_numbers",
    "find_unverified",
    "render_warning_line",
]
