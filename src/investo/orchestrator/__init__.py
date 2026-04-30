"""Orchestrator (u5) — pipeline integration glue.

US-005 (스케줄 실행). Single entry-point that composes the four work
units (u1 sources, u2 briefing, u3 publisher, u4 notifier) under one
async ``run_pipeline`` plus a ``python -m investo`` console entry.

Public surface (finalized in Step 11):

* :func:`run_pipeline` — async pipeline composer; applies the Q9=B
  graceful-degradation policy from
  ``aidlc-docs/inception/application-design/application-design.md``;
  always returns :class:`investo.models.PipelineResult`. Programmer
  errors (``KeyError``, ``AttributeError``, etc.) are NOT caught
  here — they propagate to ``main()``.
* :func:`main` — module entry-point invoked by
  ``python -m investo``. Parses 5 environment variables, validates
  CLAUDE.md #5 chat-ID disjointness BEFORE constructing dispatchers,
  builds dependencies, runs the pipeline, maps
  :class:`investo.models.PipelineStatus` → exit code (SUCCESS or
  PARTIAL → 0; FAILED → 1).
* :func:`resolve_target_date` — KST 평일/토요일 cron-time → US
  trading-day mapping (no holiday calendar dep per Q3=A; US public
  holidays surface as empty-collect → operator alert).
* :class:`ConfigError` — raised when env validation fails (missing
  vars or chat-ID equality). Caught by ``main()``; best-effort
  operator alert attempted if ``TELEGRAM_BOT_TOKEN`` and
  ``TELEGRAM_OPERATOR_CHAT_ID`` happen to be present.
* :class:`EmptyCollectError` — internal sentinel raised by
  ``_stage_collect`` when every source returned 0 items. Routed by
  ``run_pipeline`` to operator alert + ``status=FAILED`` per
  AC-003-2.

The internal stage runners ``_stage_collect / _stage_generate /
_stage_publish / _stage_notify_briefing`` are NOT re-exported — they
are u5-internal implementation details, individually testable via
explicit imports from ``investo.orchestrator.pipeline``.

**Module boundary** (CLAUDE.md #3): u5 is the ONLY unit allowed to
import all four work units (``investo.sources``, ``investo.briefing``,
``investo.publisher``, ``investo.notifier``) plus
``investo.models`` + stdlib + ``httpx``. The other 4 units must not
import each other.

**Failure routing** (Q9=B Error Policy, see audit log + NFR
acceptance criteria AC-003-1 ~ AC-003-11):

- per-source collect failure → swallowed by u1's aggregator → SUCCESS
- empty collect (all sources failed) → operator alert + FAILED
- :class:`investo.briefing.errors.BriefingGenerationError` →
  operator alert + FAILED (no orchestrator-level retry; trust u2's
  internal RetryBudget per Q4=A)
- :class:`investo.publisher.errors.PublisherDisclaimerError` /
  :class:`investo.publisher.errors.PublisherIOError` /
  :class:`investo.publisher.errors.PublisherGitError` →
  operator alert + FAILED
- :class:`investo.models.SendResult` ``ok=False`` from public-channel
  notify → PARTIAL (NO operator alert per AC-003-6 — PARTIAL itself
  is the visibility signal)
- top-level unexpected exception → caught in ``main()``,
  best-effort alert + exit 1 (AC-003-7)

Reference:
    aidlc-docs/inception/application-design/component-methods.md (C5)
    aidlc-docs/inception/application-design/application-design.md
        (Time Budget table + Q9=B Error Policy summary)
    aidlc-docs/construction/u5-orchestrator/nfr-requirements/
        (39 testable AC; 0 new external deps)
    aidlc-docs/construction/plans/u5-orchestrator-code-generation-plan.md
"""

from investo.orchestrator.date_resolution import resolve_target_date
from investo.orchestrator.errors import ConfigError, EmptyCollectError
from investo.orchestrator.pipeline import run_pipeline

# ``main`` lives in ``investo.__main__`` per Python convention so that
# ``python -m investo`` finds it. We do NOT re-export it from this
# package — the entry point is the module-runner, not a callable
# imported from ``investo.orchestrator``. Internal stage runners
# (``_stage_collect``, ``_stage_generate``, ``_stage_publish``,
# ``_stage_notify_briefing``) are likewise not re-exported; they are
# implementation details of ``run_pipeline`` and are individually
# testable via explicit imports from ``investo.orchestrator.pipeline``.

__all__ = [
    "ConfigError",
    "EmptyCollectError",
    "resolve_target_date",
    "run_pipeline",
]
