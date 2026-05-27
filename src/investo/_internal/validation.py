"""Shared validation gating contract — ``ValidationResult`` + ``Validator``.

u85 (Wave 14 capstone) gives Investo's publish-boundary gates ONE
invocation contract + an ordered registry so a pipeline can read as
"run these gates, in this order, raising on the first ``block``" instead
of an ad-hoc inline cascade. The contract is **additive**: each gate stays
its own unchanged function; a thin adapter wraps it and maps its outcome
onto :class:`ValidationResult`.

Home choice (review 2026-05-28, plan Step 1): this lives in ``_internal/``,
NOT ``models/``. It is a *behavioural contract* (a role two units play),
not a persisted/domain entity — the unit's own Stage Decision says
``ValidationResult`` is "an internal contract, not a persisted/domain
entity". Putting it in ``_internal/`` lets both ``briefing`` and
``publisher`` implement it WITHOUT a cross-unit import (CLAUDE.md #3): the
shared layer is the only legitimate meeting point.

Design choices (review 2026-05-28, guide §1/§3/§9):

* **``ValidationResult`` is a thin GATING ENVELOPE, not a payload-unifier
  (guide §9.4/§9.5).** The gates have genuinely divergent inputs
  (markdown vs ``NormalizedItem``s vs ``log_path`` + ``price_lookup``),
  outputs, and side-effect profiles. Unifying their *payloads* would be
  the wrong abstraction. This envelope unifies ONLY the *gating role*:
  a severity, a human-readable message, and an opaque ``findings`` tuple.
  A consumer that needs structured per-gate detail keeps calling the
  underlying check directly — it must NEVER reconstruct typed per-gate
  data out of the generic ``findings`` tuple. ``findings`` exists for
  logging / aggregation only.
* **Severity is 3-valued: ``pass`` / ``warn`` / ``block`` (guide §1
  YAGNI).** ``downgrade`` was dropped: no existing Investo gate produces
  a distinct "downgrade" outcome (every current gate either passes,
  emits a non-blocking warning, or raises at the publish boundary). A
  4th level with zero real cases is speculative surface. If a real
  downgrade case ever appears, add the level here + define its consumer.
* **No ``is_blocking`` on the protocol (guide §3 ISP / §1 DRY).** Whether
  a gate blocks is already carried by the ``block`` severity of the
  result it returns; a separate static flag would duplicate that and
  force every warn-only adapter to declare a policy it does not own. The
  registry derives blocking from the returned severity. (No
  fail-fast-before-running need exists today, so no static flag is kept.)
* The :class:`Validator` protocol is intentionally **input-agnostic**:
  ``validate`` takes no arguments. Each concrete adapter closes over its
  own (divergent) inputs at construction time and exposes the uniform
  zero-arg gating call. This is what lets the registry sequence
  heterogeneous gates without a god-``ctx`` parameter object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

Severity = Literal["pass", "warn", "block"]
"""Gating severity. ``pass`` = no action; ``warn`` = log/aggregate only,
publish continues; ``block`` = the registry raises at this gate."""


@dataclass(frozen=True)
class ValidationResult:
    """Thin gating envelope returned by every :class:`Validator`.

    NOT a payload-unifier (see module docstring). ``findings`` is an
    opaque tuple kept for logging/aggregation; consumers MUST NOT
    reconstruct typed per-gate data from it.
    """

    severity: Severity
    message: str = ""
    findings: tuple[object, ...] = field(default_factory=tuple)

    @property
    def is_block(self) -> bool:
        """True iff this result blocks publish (severity ``block``)."""
        return self.severity == "block"


@runtime_checkable
class Validator(Protocol):
    """Uniform gating role. Concrete adapters close over their own inputs.

    ``name`` is a stable label for logging / ordering diagnostics
    (declared read-only so ``frozen=True`` dataclass adapters satisfy it).
    ``validate`` runs the underlying check and returns the gating
    envelope. A ``block``-level adapter that wraps an existing
    raise-at-boundary gate MAY raise its existing exception instead of
    returning ``severity="block"`` — the contract permits either, and the
    registry honours both (see :mod:`investo._internal.validation` callers).
    """

    @property
    def name(self) -> str: ...

    def validate(self) -> ValidationResult: ...


@dataclass(frozen=True)
class ValidationRegistry:
    """An ordered, immutable sequence of :class:`Validator`s.

    The registry is the single place that says "these are the gates, in
    this order". :meth:`run` executes them in declaration order and
    returns every result; the FIRST ``block`` short-circuits (the loop
    stops), matching the existing pipelines' fail-on-first-block
    behaviour. Crucially, the registry does NOT itself decide *how* to
    block — a wrapped raise-at-boundary gate raises its own existing
    exception from inside ``validate()``, which propagates straight
    through :meth:`run` exactly as it does at today's call site. The
    registry's ``block`` short-circuit is for non-raising gates whose
    callers want the uniform "stop here" signal.

    Both flavours are supported so the contract can wrap raising gates
    (preserving the exact exception/point) AND bool/report gates without
    forcing either into a god-``ctx``.
    """

    name: str
    validators: tuple[Validator, ...] = ()

    def run(self) -> tuple[ValidationResult, ...]:
        """Run validators in order; stop after the first ``block``.

        Returns the accumulated results (including the terminal block, if
        any). A raising adapter's exception propagates out of this call
        unchanged — it is NOT caught here.
        """
        results: list[ValidationResult] = []
        for validator in self.validators:
            result = validator.validate()
            results.append(result)
            if result.is_block:
                break
        return tuple(results)


__all__ = [
    "Severity",
    "ValidationRegistry",
    "ValidationResult",
    "Validator",
]
