"""Publish-time validation for first-viewport segmented briefing summaries.

The three blockquote lines (``> **오늘의 결론**:``, ``> **핵심 동인**:``,
``> **주의할 점**:``) are the reader's first-viewport trust signal — if
they truncate mid-token, drop conjunctions on the floor, or expose
markdown punctuation, the entire site reads as broken.

This module is a hard gate on the segmented publish path
(``orchestrator._stage_publish_segments``). It runs after the LLM
output has been parsed and the brief header has been assembled, but
before any archive bytes hit disk. A :class:`SummaryQualityError`
aborts publish for the run; the orchestrator surfaces the failure via
the operator-alert path.

Rejection rules in addition to obvious empty / meaningless input:

* list-marker-only (``"1."``, ``"-"``, ``"1)"``) — happens when the
  briefing pipeline pulls the leading bullet of section ⑥ as the
  caution line and the marker is the only token that survives
  markdown stripping;
* conjunction-tail in English or Korean (``"... vs."``, ``"... and."``,
  ``"... 과."``) — happens when the briefing pipeline picks a phrase
  fragment that breaks at a conjunction;
* unbalanced ``**`` bold markers — happens when only one half of a
  bold pair survives the truncation;
* unbalanced ``[``/``]`` or ``(``/``)`` — happens when a markdown link
  splits across the truncation boundary.

The reject list is intentionally narrow: it covers the patterns that
have actually shipped truncated archives, not every theoretically
malformed string. The briefing pipeline fixes (``_summary_sentence``)
remove these patterns at source; this gate is the publish-time safety
net pinning that the fix did not regress.
"""

from __future__ import annotations

import re
from typing import Final

_SUMMARY_PREFIXES: Final[tuple[str, ...]] = (
    "> **오늘의 결론**:",
    "> **핵심 동인**:",
    "> **주의할 점**:",
)
# Reject ``"1."``, ``"-"``, ``"*"``, ``"1)"`` … and the circled-digit
# Korean numbers occasionally emitted by the LLM. Fullmatch only —
# partial matches let valid sentences through.
_LIST_MARKER_ONLY_RE: Final[re.Pattern[str]] = re.compile(r"^(?:[-*+]|\d+[.)]|[①-⑳])$")
# ``^\d+\.$`` — explicit alternate spelling per the u25 plan. Already
# matched by the list-marker-only regex above; kept as a separate
# constant so the persona-cited pattern is greppable.
_NUMBER_DOT_ONLY_RE: Final[re.Pattern[str]] = re.compile(r"^\d+\.$")
_MEANINGFUL_TEXT_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9가-힣]")
# English conjunctions / function words that should never end a
# user-facing sentence. ``\.$`` (literal trailing dot) so we only flag
# truncations like ``"... vs."``, not phrases that legitimately use
# ``vs`` mid-sentence.
_EN_CONJUNCTION_TAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:vs|and|or|but|that|where|which|because|with|of|to|for|on|in|by)\.\s*$",
    re.IGNORECASE,
)
# Korean particles / connectives that shouldn't end a sentence either.
# Listed conservatively — only the trailing-dot form is rejected so we
# do not flag sentences that legitimately end in 과/와/및 followed by
# more text.
_KO_PARTICLE_TAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:과|와|및|또는|에서|의|을|를|이|가|은|는)\.\s*$"
)


class SummaryQualityError(ValueError):
    """Raised when a briefing first-viewport summary is unsafe to publish."""


def validate_first_viewport_summary(markdown: str) -> None:
    """Validate the three reader-facing summary lines before publish.

    Called from ``investo.orchestrator.pipeline._stage_publish_segments``
    immediately before each segment archive is written. Raises
    :class:`SummaryQualityError` on any rejection — the orchestrator
    rolls back snapshots and surfaces the failure via the operator
    alerter.
    """
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
    if _EN_CONJUNCTION_TAIL_RE.search(value) or _KO_PARTICLE_TAIL_RE.search(value):
        raise SummaryQualityError(
            f"conjunction-tail truncation in first-viewport summary line: {prefix}"
        )


__all__ = ["SummaryQualityError", "validate_first_viewport_summary"]
