"""Briefing-side ``Validator`` adapters + the in-pipeline gate registry.

u85 (Wave 14 capstone). These thin adapters wrap the UNCHANGED briefing
check functions and map their outcomes onto the shared
:class:`~investo._internal.validation.ValidationResult` envelope, so the
briefing pipeline can express its post-generation gating as a registry
run instead of an inline call.

ADDITIVE + behaviour-preserving (plan AC-85.2/AC-85.3): the adapter calls
the existing function and translates its result; no detection logic,
threshold, or message changes. The only briefing check that actually fires
*in the briefing pipeline* is :func:`investo.briefing.leak_guard.scan`
(the post-synthesis leak gate in ``_finalize_briefing``); the other
briefing-domain checks (citation_cardinality, date_corruption,
numeric_verify, summary_quality, accuracy) are NOT invoked inside the
briefing pipeline — they run at the orchestrator publish boundary or in
publisher site-index rendering, with divergent inputs. Wrapping a function
that the briefing pipeline does not call would add dead surface, so this
registry holds only the genuinely in-pipeline gate (plan's permission to
descope to the genuinely-alike set; guide §1 YAGNI / §9.6 Rule-of-Three).

The briefing registry is owned HERE, in u2; the publish-boundary registry
is owned by the orchestrator (u5). The shared protocol type lives in
``_internal/`` so neither side imports the other (CLAUDE.md #3).
"""

from __future__ import annotations

from dataclasses import dataclass

from investo._internal.validation import (
    ValidationRegistry,
    ValidationResult,
    Validator,
)
from investo.briefing.leak_guard import LeakGuardHit
from investo.briefing.leak_guard import scan as leak_guard_scan


@dataclass(frozen=True)
class LeakGuardValidator:
    """Wraps :func:`investo.briefing.leak_guard.scan` as a ``block`` gate.

    ``validate`` returns ``block`` (carrying the :class:`LeakGuardHit` in
    ``findings``) when the guard matches and ``pass`` otherwise. It does
    NOT raise — the existing call site (``_finalize_briefing``) keeps
    ownership of the exact ``BriefingGenerationError(stage="post_validation")``
    it raises today, so the failure shape is byte-for-byte preserved.
    """

    name: str
    markdown: str

    def validate(self) -> ValidationResult:
        hit: LeakGuardHit | None = leak_guard_scan(self.markdown)
        if hit is not None:
            return ValidationResult(
                severity="block",
                message=f"leak guard matched pattern: {hit.pattern_name}",
                findings=(hit,),
            )
        return ValidationResult(severity="pass")


def build_post_validation_registry(full_markdown: str) -> ValidationRegistry:
    """Build the briefing post-synthesis gate registry.

    Currently a single-gate registry (the leak guard). It exists so the
    in-pipeline gating reads through the shared contract and so additional
    in-pipeline briefing gates can be appended here in declared order
    without editing ``_finalize_briefing``'s control flow.
    """
    validators: tuple[Validator, ...] = (
        LeakGuardValidator(name="leak_guard", markdown=full_markdown),
    )
    return ValidationRegistry(name="briefing.post_validation", validators=validators)


__all__ = [
    "LeakGuardValidator",
    "build_post_validation_registry",
]
