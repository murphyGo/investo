"""Orchestrator Stage abstraction — uniform stage shape + error routing.

u84 introduces this layer so :func:`investo.orchestrator.pipeline.run_pipeline`
can read as a *sequencing + error-routing loop* over uniformly-shaped
stages instead of an inline 11-arm try/except cascade. The behavioural
contract (which exception type routes to which operator alert and which
:class:`~investo.models.PipelineStatus`) is preserved exactly — see
``test_run_pipeline.py``.

Design choices (review 2026-05-28, guide §2/§3/§4/§9):

* :class:`PipelineContext` is ``@dataclass(frozen=True)`` and
  **inputs-only**. It is the parameter object the loop threads into each
  stage; a stage MUST NOT mutate it. Stage outputs flow EXCLUSIVELY via
  :attr:`StageResult.data`, accumulated by the loop (Command/Query
  separation). This keeps the stages from silently re-coupling through a
  shared mutable bag of state.
* :class:`StageResult` is the uniform return envelope (status / data /
  error). A stage reports a *recoverable* failure by returning
  ``status="failed"`` with ``error`` set; the loop then consults
  :data:`EXCEPTION_ROUTING` to decide the operator alert + pipeline
  status. Programmer errors (anything not in the routing table) are NOT
  wrapped — they propagate to ``main()`` per AC-003-7.
* :data:`EXCEPTION_ROUTING` is a **declarative dict** keyed by exception
  type (Replace-Conditional-with-Polymorphism, guide §4) — not an
  ``isinstance`` chain. The "switch on exception type" lives in exactly
  one place and new failure types extend the table, not the loop.
* The concrete stage sequence is assembled at a **composition root**
  (:func:`investo.orchestrator.pipeline.build_default_stages`) and passed
  into the loop, so stages are injectable for isolated tests (DIP,
  guide §3/§8) rather than instantiated inline in ``run_pipeline``.

This module deliberately holds NO unit imports beyond ``models`` — the
concrete stage classes (which DO touch sources/briefing/publisher/
notifier) live in ``pipeline.py``, the only u5 module allowed those
cross-unit edges (CLAUDE.md #3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Generic, Literal, Protocol, TypeVar

from pydantic import HttpUrl

from investo.models import PipelineStatus
from investo.models.results import FailureStage

T = TypeVar("T")

StageRunStatus = Literal["ok", "partial", "failed"]


@dataclass(frozen=True)
class PipelineContext:
    """Inputs-only parameter object threaded into every stage.

    Frozen by design (guide §2/§9.2): a stage reads the fields it needs
    and returns its outputs via :class:`StageResult`; it never writes
    back into the context. The loop accumulates per-stage outputs in its
    own local state, so there is no hidden shared mutable bag.

    Fields are the *run inputs* known before any stage executes plus the
    DI seams forwarded from :func:`run_pipeline`. Stage-produced values
    (collected items, generated briefings, archive paths, …) are NOT
    here — they live in :attr:`StageResult.data`.
    """

    target_date: date
    site_url_base: HttpUrl
    # DI seams — production passes ``None`` so each stage uses its real
    # binding; tests inject fakes. Typed loosely (``object``) here to keep
    # this module free of cross-unit imports; the concrete stages in
    # ``pipeline.py`` narrow them back to their real callable/Protocol
    # shapes at the point of use.
    fetch: object | None = None
    runner: object | None = None
    git_runner: object | None = None
    generate: object | None = None
    generate_segment: object | None = None


@dataclass(frozen=True)
class StageResult(Generic[T]):
    """Uniform stage return envelope.

    ``status`` is the per-stage run status; ``data`` carries the stage's
    outputs (consumed by later stages via the loop's accumulator);
    ``error`` is set when the stage caught a routable failure (the loop
    maps it through ``EXCEPTION_ROUTING``). ``stage_notes`` lets a stage
    contribute extra human-readable ``stages``-dict entries (e.g. per-
    segment generate failures) without mutating the context. ``timings``
    lets a stage own its ``stage_timings`` contributions (a single stage
    may report more than one timing key — e.g. the generate stage records
    both ``generate`` and, on a reader-format abort, ``publish``).
    """

    status: StageRunStatus
    data: T | None = None
    error: Exception | None = None
    stage_notes: dict[str, str] = field(default_factory=dict)
    timings: dict[str, float] = field(default_factory=dict)


class Stage(Protocol):
    """Uniform stage interface.

    ``name`` is the :data:`FailureStage`-compatible label used for the
    ``stages`` dict key and the operator-alert ``stage`` field. ``execute``
    reads from the (frozen) context + the loop's accumulated outputs and
    returns a :class:`StageResult`.
    """

    name: str

    async def execute(
        self,
        ctx: PipelineContext,
        accumulated: dict[str, object],
    ) -> StageResult[dict[str, object]]: ...


@dataclass(frozen=True)
class StageAction:
    """Declarative routing entry for one catalogued failure exception.

    ``stage`` is the :data:`FailureStage` label passed to the operator
    alert; ``alert`` is whether an operator alert fires; ``status`` is the
    resulting pipeline status. This is the single change-point for the
    exception→action mapping (guide §4).
    """

    stage: FailureStage
    alert: bool
    status: PipelineStatus


__all__ = [
    "PipelineContext",
    "Stage",
    "StageAction",
    "StageResult",
    "StageRunStatus",
]
