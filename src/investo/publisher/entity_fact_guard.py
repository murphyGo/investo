"""Publish-boundary guard for source-verified entity-role facts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from investo.models.facts import VerifiedFactBundle

_POWELL_TERMS: Final[tuple[str, ...]] = (
    "파월 의장",
    "제롬 파월 의장",
    "Powell chair",
    "Chair Powell",
    "Powell press conference",
    "파월 기자회견",
)
_WARSH_TERMS: Final[tuple[str, ...]] = (
    "Kevin Warsh 의장",
    "Warsh chair",
    "Chair Warsh",
    "Warsh press conference",
    "케빈 워시 의장",
    "워시 의장",
    "워시 기자회견",
)
_HISTORICAL_QUALIFIERS: Final[tuple[str, ...]] = (
    "전임",
    "이전",
    "과거",
    "전 의장",
    "former",
    "prior",
    "previous",
)
_SENTENCE_SPLIT_RE: Final[re.Pattern[str]] = re.compile(r"(?<=[.!?。])\s+|(?<=다\.)\s*|\n+")


@dataclass(frozen=True, slots=True)
class EntityFactViolation:
    segment: str
    fact_id: str
    expected_value: str
    offending_term: str
    line_number: int
    preview: str


class EntityFactGuardError(RuntimeError):
    """Raised when current entity-role claims contradict verified facts."""

    def __init__(self, violations: tuple[EntityFactViolation, ...]) -> None:
        self.violations = violations
        terms = ", ".join(sorted({violation.offending_term for violation in violations}))
        super().__init__(f"entity fact guard blocked terms: {terms}")


def scan_entity_fact_claims(
    markdown: str,
    bundle: VerifiedFactBundle,
    target_date: object,
    now_utc: datetime,
    *,
    segment: str = "unknown",
) -> tuple[EntityFactViolation, ...]:
    """Return violations for current Fed chair person-role claims."""

    del target_date
    fresh_fact = bundle.fresh("fed.current_chair", now_utc)
    if fresh_fact is None:
        expected = "unverified"
        blocked_terms = (*_POWELL_TERMS, *_WARSH_TERMS)
    else:
        expected = fresh_fact.value
        blocked_terms = _POWELL_TERMS if fresh_fact.value.lower() != "jerome powell" else ()

    violations: list[EntityFactViolation] = []
    for line_no, line in enumerate(markdown.splitlines(), start=1):
        for sentence in _split_sentences(line):
            if not sentence or _has_historical_qualifier(sentence):
                continue
            for term in blocked_terms:
                if _contains_term(sentence, term):
                    violations.append(
                        EntityFactViolation(
                            segment=segment,
                            fact_id="fed.current_chair",
                            expected_value=expected,
                            offending_term=term,
                            line_number=line_no,
                            preview=_preview(sentence),
                        )
                    )
    return tuple(violations)


def _split_sentences(line: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in _SENTENCE_SPLIT_RE.split(line) if part.strip())


def _has_historical_qualifier(sentence: str) -> bool:
    lower = sentence.lower()
    return any(qualifier.lower() in lower for qualifier in _HISTORICAL_QUALIFIERS)


def _contains_term(sentence: str, term: str) -> bool:
    if any(ord(ch) > 127 for ch in term):
        return term in sentence
    return term.lower() in sentence.lower()


def _preview(sentence: str) -> str:
    clean = " ".join(sentence.split())
    return clean if len(clean) <= 120 else clean[:117] + "..."


__all__ = [
    "EntityFactGuardError",
    "EntityFactViolation",
    "scan_entity_fact_claims",
]
