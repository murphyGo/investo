"""First-viewport summary extraction (sentence pick + 3-line header).

References:
    u30 Step 3 — conclusion action-tagging

Moved verbatim from ``briefing/pipeline.py`` in the u83 decomposition;
behavior-preserving (move-only).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from investo._internal.surface_quality import has_blocking_surface_issue
from investo.briefing._assembly.text_normalize import (
    _clean_summary_line,
    _split_into_sentences,
)
from investo.briefing._text.patterns import (
    MEANINGFUL_TEXT as _MEANINGFUL_TEXT_RE,
)
from investo.briefing.action_tag import apply_action_tag

# Reject patterns the summary sentence picker uses to skip a candidate
# (matches mirror summary_quality gate-side rejects so the producer
# never emits what the gate would block).
_MARKER_ONLY_RE: Final[re.Pattern[str]] = re.compile(r"^(?:[-*+]|\d+[.)]|[①-⑳])$")
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


@dataclass(frozen=True, slots=True)
class SummaryHeader:
    """Validated first-viewport summary lines for segmented briefings."""

    conclusion: str
    driver: str
    caution: str


def _is_unsafe_summary_candidate(candidate: str) -> bool:
    """Reject candidate strings that would later trip the publish gate.

    Mirrors the rejects in ``summary_quality.validate_first_viewport_summary``
    so the producer never emits a string the gate would block. Keeping
    the two lists aligned is the contract; a regression here surfaces
    as a publish-time ``SummaryQualityError``.
    """
    if not candidate:
        return True
    if _MARKER_ONLY_RE.fullmatch(candidate):
        return True
    if not _MEANINGFUL_TEXT_RE.search(candidate):
        return True
    if candidate.count("**") % 2 != 0:
        return True
    if candidate.count("[") != candidate.count("]"):
        return True
    if candidate.count("(") != candidate.count(")"):
        return True
    if has_blocking_surface_issue(candidate):
        return True
    if _HEADING_RESIDUE_RE.search(candidate):
        return True
    if _BROKEN_NUMERIC_BOLD_RE.search(candidate):
        return True
    if _GENERATOR_RESIDUE_TAIL_RE.search(candidate):
        return True
    if (
        len(candidate) >= 60
        and not candidate.rstrip().endswith(("다.", "니다.", "요.", ".", "!", "?", "…"))
        and _DANGLING_LONG_TAIL_RE.search(candidate)
    ):
        return True
    if _EN_CONJUNCTION_TAIL_RE.search(candidate):
        return True
    return bool(_KO_PARTICLE_TAIL_RE.search(candidate))


def _summary_sentence(text: str, *, fallback: str) -> str:
    """Extract the first publish-safe sentence from a section body.

    Iterates sentence-shaped chunks (terminator-anchored) and returns
    the first one that passes :func:`_is_unsafe_summary_candidate`.
    Falls back to ``fallback`` when no chunk survives — this keeps the
    first-viewport summary well-formed even when the LLM's section
    body opens with a marker fragment, an unfinished bold pair, or a
    conjunction tail (the three persona-cited 2026-05-06 failures).
    """
    cleaned_lines = [
        cleaned
        for line in text.splitlines()
        if not has_blocking_surface_issue(line) and (cleaned := _clean_summary_line(line))
    ]
    normalized = " ".join(cleaned_lines)
    if not normalized:
        return fallback

    sentences = _split_into_sentences(normalized)

    # Per-sentence scan first: pick the first complete, safe sentence.
    for candidate in sentences:
        if not _is_unsafe_summary_candidate(candidate):
            return candidate[:280].strip()

    # No complete sentence survived. Try each cleaned line as a
    # standalone candidate (truncated to 140 chars) — line-shaped
    # phrases without a terminator can still be valid summaries.
    for line in cleaned_lines:
        candidate = line[:140].strip()
        if not _is_unsafe_summary_candidate(candidate):
            return candidate

    # Last resort: the truncated normalized blob. If even that is
    # unsafe, hand back the explicit data-limited fallback string.
    candidate = normalized[:140].strip()
    if not _is_unsafe_summary_candidate(candidate):
        return candidate
    return fallback


def _build_summary_header(
    sections: tuple[str, str, str, str, str, str],
    *,
    data_limited: bool = False,
) -> SummaryHeader:
    """Build the three first-viewport summary lines.

    u30 Step 3 — the conclusion line is post-processed to carry exactly
    one closed-set action tag (``[관망]`` / ``[변동성↑]`` / ``[강세]`` /
    ``[약세]`` / ``[혼조]`` / ``[데이터부족]``). When ``data_limited`` is
    true the tag is forced to ``[데이터부족]`` regardless of what (if
    anything) the LLM emitted; otherwise an off-set or missing tag is
    rewritten to the deterministic default ``[관망]``. See
    :mod:`investo.briefing.action_tag`.
    """
    raw_conclusion = _summary_sentence(sections[0], fallback="확인된 요약이 부족합니다.")
    return SummaryHeader(
        conclusion=apply_action_tag(
            raw_conclusion,
            data_limited=data_limited,
            section_text=sections[0],
        ),
        driver=_summary_sentence(sections[1], fallback="핵심 동인은 추가 확인이 필요합니다."),
        caution=_summary_sentence(sections[5], fallback="관전 포인트는 데이터 회복 후 보강합니다."),
    )


__all__ = [
    "SummaryHeader",
    "_build_summary_header",
    "_is_unsafe_summary_candidate",
    "_summary_sentence",
]
