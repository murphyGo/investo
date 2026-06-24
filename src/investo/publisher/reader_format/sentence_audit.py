"""u56 retail tone-cap audits (sentence-ending diversity + filler density).

Move-only extraction from the pre-split ``reader_format`` module (u81).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from investo.models.segments import MarketSegment
from investo.publisher.reader_format._constants import _TABLE_ROW_RE, _logger


@dataclass(frozen=True, slots=True)
class SentenceEndingReport:
    """Distribution of dominant sentence-ending patterns in the body."""

    counts: dict[str, int]
    total: int
    dominant: str | None
    dominant_ratio: float


@dataclass(frozen=True, slots=True)
class FillerDensityReport:
    """Filler-phrase density per 1000 chars of cleaned body text."""

    counts: dict[str, int]
    total_chars: int
    density_per_1000: float


# Korean closing patterns categorised. Matched right-of-sentence, after
# stripping a final trailing period / space. The category list is small
# on purpose — over-matching produces noisy ratios; we want a clean
# "dominant ending" signal.
_SENTENCE_ENDING_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("했다", re.compile(r"했다\.?\s*$")),
    ("된다", re.compile(r"된다\.?\s*$")),
    ("이다", re.compile(r"이다\.?\s*$")),
    ("전망이다", re.compile(r"전망이다\.?\s*$")),
    ("보인다", re.compile(r"보인다\.?\s*$")),
    ("가능성", re.compile(r"가능성[이가]?\s*\S*\.?\s*$")),
)

_FILLER_TERMS: Final[tuple[str, ...]] = (
    "여부",
    "전망",
    "우려",
    "가능성",
    "작용",
)

SENTENCE_ENDING_DOMINANCE_THRESHOLD: Final[float] = 0.60
FILLER_DENSITY_PER_1000_THRESHOLD: Final[float] = 8.0

_YAML_FRONTMATTER_RE: Final[re.Pattern[str]] = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_SENTENCE_SPLIT_RE: Final[re.Pattern[str]] = re.compile(r"[.!?]\s+|\n+")


def _strip_non_body_regions(text: str) -> str:
    """Strip yaml frontmatter / code fences / table rows for tone metrics.

    The tone caps operate on prose only: structural / data surfaces are
    not part of the reader-perceived rhythm. Disclaimer footer is also
    stripped so the canonical text does not weight the ratio.
    """
    out = _YAML_FRONTMATTER_RE.sub("", text)
    # Strip disclaimer footer.
    anchor = "## ⑦ 면책조항"
    anchor_idx = out.find(anchor)
    if anchor_idx >= 0:
        out = out[:anchor_idx]
    # Strip code fences.
    out = re.sub(r"```.*?```", "", out, flags=re.DOTALL)
    out = re.sub(r"`[^`\n]+`", "", out)
    # Strip table rows.
    out = "\n".join(line for line in out.splitlines() if not _TABLE_ROW_RE.match(line))
    return out


def check_sentence_ending_diversity(
    text: str, *, segment: MarketSegment | None = None
) -> SentenceEndingReport:
    """Return the dominant Korean sentence-ending ratio in the body.

    WARN-only — emits ``tone.sentence_ending_dominance`` when the
    dominant ending exceeds :data:`SENTENCE_ENDING_DOMINANCE_THRESHOLD`.
    """
    body = _strip_non_body_regions(text)
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(body) if s.strip()]
    counts: dict[str, int] = {}
    classified_total = 0
    for sentence in sentences:
        for label, pattern in _SENTENCE_ENDING_PATTERNS:
            if pattern.search(sentence):
                counts[label] = counts.get(label, 0) + 1
                classified_total += 1
                break

    if classified_total == 0:
        return SentenceEndingReport(counts=counts, total=0, dominant=None, dominant_ratio=0.0)

    dominant = max(counts.items(), key=lambda kv: kv[1])
    dominant_label = dominant[0]
    dominant_ratio = dominant[1] / classified_total

    if dominant_ratio > SENTENCE_ENDING_DOMINANCE_THRESHOLD:
        _logger.warning(
            "tone.sentence_ending_dominance",
            extra={
                "segment": segment,
                "dominant": dominant_label,
                "ratio": round(dominant_ratio, 3),
                "total": classified_total,
            },
        )
    return SentenceEndingReport(
        counts=counts,
        total=classified_total,
        dominant=dominant_label,
        dominant_ratio=dominant_ratio,
    )


def check_filler_phrase_density(
    text: str, *, segment: MarketSegment | None = None
) -> FillerDensityReport:
    """Return the filler-family per-1000-chars density.

    WARN-only — emits ``tone.filler_density`` when the density exceeds
    :data:`FILLER_DENSITY_PER_1000_THRESHOLD`.
    """
    body = _strip_non_body_regions(text)
    total_chars = len(body)
    counts: dict[str, int] = {}
    occurrences = 0
    for term in _FILLER_TERMS:
        count = body.count(term)
        if count:
            counts[term] = count
            occurrences += count
    density = (occurrences / total_chars * 1000.0) if total_chars else 0.0
    if density > FILLER_DENSITY_PER_1000_THRESHOLD:
        _logger.warning(
            "tone.filler_density",
            extra={
                "segment": segment,
                "density_per_1000": round(density, 2),
                "total_chars": total_chars,
                "occurrences": occurrences,
            },
        )
    return FillerDensityReport(counts=counts, total_chars=total_chars, density_per_1000=density)
