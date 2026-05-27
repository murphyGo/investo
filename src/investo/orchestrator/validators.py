"""Orchestrator-owned publish-boundary ``Validator`` adapters + registry.

u85 (Wave 14 capstone). These thin adapters wrap the UNCHANGED
publish-boundary gates that run *as a flat, ordered, per-segment sequence*
in :func:`investo.orchestrator.pipeline._stage_publish_segments` — the
first-viewport summary gate, the canonical-footer disclaimer gate, and the
first-viewport short-disclaimer gate — and map them onto the shared
:class:`~investo._internal.validation.ValidationResult` envelope.

Why only these three (plan's descope permission; guide §9.5):
the publisher's OTHER gates — ``scan_compliance`` (twice),
``run_all_cross_segment_lints``, ``enforce_anchor_assertions``,
``evaluate_cause_map`` — do NOT run as a separable orchestrator-level
sequence. They are interleaved *between* the str→str markdown
transformations deep inside ``publisher.segment_reader_format`` (e.g.
``scan_compliance`` runs once before and once after
``render_watchpoint_matrix``, with the ordering load-bearing). Lifting
them into a flat orchestrator registry would require reordering that
mutation pipeline — a behaviour change, which Wave 14 forbids. They stay
where they are. This module wraps only the genuinely-alike, flat,
``block``-only trio at the actual orchestrator publish boundary.

ADDITIVE + behaviour-preserving:

* :class:`FirstViewportSummaryValidator` lets
  :func:`investo.briefing.summary_quality.validate_first_viewport_summary`
  raise its existing ``SummaryQualityError`` from inside ``validate()`` —
  the exact exception, at the exact point, with the exact rollback
  semantics the surrounding ``except`` block already provides.
* :class:`DisclaimerFooterValidator` / :class:`ShortDisclaimerValidator`
  wrap the bool predicates; they return ``block`` on failure and the call
  site keeps raising the same ``PublisherDisclaimerError(target_date=...)``
  it raises today.

This registry is owned by u5 (orchestrator); the briefing in-pipeline
registry is owned by u2. The shared protocol type lives in ``_internal/``
so neither unit imports the other (CLAUDE.md #3).
"""

from __future__ import annotations

from dataclasses import dataclass

from investo._internal.validation import (
    ValidationRegistry,
    ValidationResult,
    Validator,
)
from investo.briefing.summary_quality import validate_first_viewport_summary
from investo.models import MarketSegment
from investo.publisher.verifier import (
    verify_disclaimer,
    verify_short_disclaimer_first_viewport,
)


@dataclass(frozen=True)
class FirstViewportSummaryValidator:
    """Wraps ``validate_first_viewport_summary`` as a raise-at-boundary gate.

    ``validate()`` calls the unchanged function, which raises
    ``SummaryQualityError`` on a bad first-viewport summary. The exception
    propagates straight out (the registry does not catch it), preserving
    the existing failure shape + rollback path.
    """

    name: str
    markdown: str

    def validate(self) -> ValidationResult:
        validate_first_viewport_summary(self.markdown)
        return ValidationResult(severity="pass")


@dataclass(frozen=True)
class DisclaimerFooterValidator:
    """Wraps ``verify_disclaimer`` (canonical footer) as a ``block`` gate."""

    name: str
    markdown: str
    segment: MarketSegment

    def validate(self) -> ValidationResult:
        if not verify_disclaimer(self.markdown, self.segment):
            return ValidationResult(
                severity="block",
                message=f"disclaimer verification failed segment={self.segment}",
            )
        return ValidationResult(severity="pass")


@dataclass(frozen=True)
class ShortDisclaimerValidator:
    """Wraps ``verify_short_disclaimer_first_viewport`` as a ``block`` gate."""

    name: str
    markdown: str
    segment: MarketSegment

    def validate(self) -> ValidationResult:
        if not verify_short_disclaimer_first_viewport(self.markdown, self.segment):
            return ValidationResult(
                severity="block",
                message=f"first-viewport disclaimer verification failed segment={self.segment}",
            )
        return ValidationResult(severity="pass")


def build_publish_boundary_registry(
    *,
    markdown: str,
    segment: MarketSegment,
) -> ValidationRegistry:
    """Build the per-segment publish-boundary gate registry.

    Order is identical to today's inline cascade in
    ``_stage_publish_segments``: first-viewport summary → canonical
    disclaimer footer → first-viewport short disclaimer.
    """
    validators: tuple[Validator, ...] = (
        FirstViewportSummaryValidator(name="first_viewport_summary", markdown=markdown),
        DisclaimerFooterValidator(name="disclaimer_footer", markdown=markdown, segment=segment),
        ShortDisclaimerValidator(name="short_disclaimer", markdown=markdown, segment=segment),
    )
    return ValidationRegistry(name=f"publish_boundary.{segment}", validators=validators)


__all__ = [
    "DisclaimerFooterValidator",
    "FirstViewportSummaryValidator",
    "ShortDisclaimerValidator",
    "build_publish_boundary_registry",
]
