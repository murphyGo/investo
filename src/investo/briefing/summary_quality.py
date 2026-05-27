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

from investo.briefing._text.patterns import (
    MEANINGFUL_TEXT as _MEANINGFUL_TEXT_RE,
)

# Public canonical prefix literals — DEBT-060 chokepoint. Five surfaces
# (publisher.site_index, publisher.weekly_digest, visuals.og_card,
# visuals.assets, briefing.context) used to declare these locally; they
# now import these constants so a future shape change (e.g.
# ``**결론**:`` → ``**결론 (yyyy-mm-dd)**:``) lands in one place. The
# briefing pipeline's ``_enhance_reader_experience`` is the canonical
# emitter — every consumer is a parser of that emitter's output.
CONCLUSION_PREFIX: Final[str] = "> **오늘의 결론**:"
DRIVER_PREFIX: Final[str] = "> **핵심 동인**:"
CAUTION_PREFIX: Final[str] = "> **주의할 점**:"
WATERMARK_PREFIX: Final[str] = "**기준 시각**:"

_SUMMARY_PREFIXES: Final[tuple[str, ...]] = (
    CONCLUSION_PREFIX,
    DRIVER_PREFIX,
    CAUTION_PREFIX,
)
# Reject ``"1."``, ``"-"``, ``"*"``, ``"1)"`` … and the circled-digit
# Korean numbers occasionally emitted by the LLM. Fullmatch only —
# partial matches let valid sentences through.
_LIST_MARKER_ONLY_RE: Final[re.Pattern[str]] = re.compile(r"^(?:[-*+]|\d+[.)]|[①-⑳])$")
# ``^\d+\.$`` — explicit alternate spelling per the u25 plan. Already
# matched by the list-marker-only regex above; kept as a separate
# constant so the persona-cited pattern is greppable.
_NUMBER_DOT_ONLY_RE: Final[re.Pattern[str]] = re.compile(r"^\d+\.$")
# u79 — ``_MEANINGFUL_TEXT_RE`` single-sourced in
# :mod:`investo.briefing._text.patterns`; imported above.
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
_FALLBACK_BY_PREFIX: Final[dict[str, str]] = {
    CONCLUSION_PREFIX: "확인된 요약이 부족합니다.",
    DRIVER_PREFIX: "핵심 동인은 추가 확인이 필요합니다.",
    CAUTION_PREFIX: "관전 포인트는 데이터 회복 후 보강합니다.",
}


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


def repair_first_viewport_summary(markdown: str) -> str:
    """Repair malformed first-viewport summary values in-place.

    This is a narrow safety pass for live LLM output: it only rewrites
    the three blockquote summary values when the publish gate would
    reject them for markdown residue or truncation artifacts.
    """
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
