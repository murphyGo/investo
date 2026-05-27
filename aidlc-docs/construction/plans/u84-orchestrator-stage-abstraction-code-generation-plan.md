# Code Generation Plan: `u84 orchestrator-stage-abstraction`

**Date**: 2026-05-28
**Unit**: u84 orchestrator-stage-abstraction
**Stage**: Code Generation (refactor)
**Status**: Complete — 6/6 steps (gate green; DEBT-062 explicitly deferred)
**Source**: 2026-05-28 abstraction review — `orchestrator/pipeline.py` (god-module, highest blast radius)
**Estimated Effort**: ~8-10 h (highest-risk unit in the wave)
**Dependencies**: **u81** (reader-format leak moves cleaner after the reader_format split — soft)
**Wave**: 14 — read `wave-14-abstraction-refactor-overview.md` first; its Refactor Contract governs this unit. **The failure-routing contract is load-bearing and heavily tested — behavior preservation is mandatory.**

---

## Problem Statement

`orchestrator/pipeline.py` is 2775 lines / 41 functions and imports 34 submodules. `run_pipeline` (~L2218-2695) tangles five responsibilities:

1. **Stage sequencing & error routing** — try/except blocks route 11+ exception types (EmptyCollectError, BriefingGenerationError, PublisherDisclaimerError, PublisherIOError, PublisherGitError, …) to `_safe_alert` and a FAILED status (~L2290-2555).
2. **Context assembly** — `_load_market_anchors_for_run`, `_load_carryover_for_run`, `_load_recent_context_for_run`, `compute_bundle_context` (~L1167, 1661, 1713, 156).
3. **Segment routing & reconciliation** — `_stage_generate_segments` (~L481-611), `_stage_publish_segments` (~L775-1166), `_reconcile_anchor_closes` (~L1404-1434).
4. **Reader-format / post-publish repair** — `_apply_reader_format_to_segments` (~L1487-1660), `_enforce_quality_consistency_gate` (~L1795-1831). **This logically belongs in `publisher/`, not the orchestrator (a leak).**
5. **Alerting & retry budget** — `_safe_alert` (~L2698-2740), `_build_failure_context` (~L2169-2192).

Each stage has a different signature and exception contract, so `test_run_pipeline.py` (2164 lines) tests each ad-hoc.

---

## Goal

Introduce a consistent **`Stage` abstraction** so `run_pipeline` becomes a sequencing + error-routing loop over uniformly-shaped stages, and move the leaked reader-format step into `publisher/`. **Every existing pipeline test must pass unchanged** — the failure-status semantics, alert dedup, and partial-success handling are the contract.

Proposed shape (implementer may refine names, must keep semantics):

```python
@dataclass(frozen=True)
class StageResult(Generic[T]):
    status: Literal["ok", "partial", "failed"]
    data: T | None
    error: Exception | None

class Stage(Protocol):           # or ABC
    name: str
    async def execute(self, ctx: PipelineContext) -> StageResult: ...
```

Stages: `CollectStage`, `GenerateStage` (+ segmented variant), `PublishStage` (+ segmented variant), `NotifyStage`, `HealthTrackingStage`. Context-loader helpers move to `orchestrator/stage_context.py`.

---

## Existing Coverage / Deduplication

- The exact mapping of exception type → (alert? / status) is the behavioral contract. Before refactoring, **enumerate every existing `except` arm in `run_pipeline` and its segment helpers** and reproduce it exactly in the new error-routing loop. `test_run_pipeline.py` pins many of these — they must stay green unchanged.
- `_apply_reader_format_to_segments` moves to `publisher/` (it calls publisher reader-format anyway). After u81, the natural home is the `reader_format` package or a new `publisher/segment_reader_format.py`. The orchestrator then calls it as a publisher API — preserving the module boundary (orchestrator → publisher is allowed).
- There is an **open TECH-DEBT** about `_stage_publish_segments` absolute-vs-relative archive-path normalization (the index/heatmap/og/weekly steps branch on path shape; tests need a helper). `grep DEBT- docs/TECH-DEBT.md` for the live ID. Fold the suggested fix (single normalization point or a `archive_paths_for_publish(...)` resolver) into Step 3 and reference the DEBT ID in closeout. If folding risks behavior change, leave it and note as out-of-scope.

---

## Scope Boundary

In scope:
- `Stage` protocol + `StageResult` + `PipelineContext`; extracting each stage into its own class/module; `run_pipeline` as the loop; moving `_load_*` to `stage_context.py`; moving `_apply_reader_format_to_segments` into `publisher/`.

Out of scope:
- Changing what any stage does, when an alert fires, or the resulting pipeline status for any input.
- Changing the Telegram clients (u80) or the briefing pipeline (u83).
- Adding new stages or new alert types.

---

## Stage Decision

- **Functional Design — SKIP.** Structural restructuring of the orchestrator; no new domain entity.
- **NFR Requirements — SKIP.** No new dependency/service/secret/cost. The retry-budget, alert-delivery, and all-three-or-fail segmented-publish NFR behaviors are preserved exactly, not changed.

---

## Implementation Steps

> **Discipline:** this is the riskiest unit. Extract one stage per step, run the FULL pipeline + integration suite after each, and never proceed on a red gate. Keep each diff move-only plus the thin `Stage` wrapper.

### Step 1 — define the abstraction `[x]`
- [x] Add `Stage` protocol/ABC, `StageResult`, and `PipelineContext`.
> **Constrain `PipelineContext` (review 2026-05-28, guide §2 parameter-object / §9.2 information-hiding / §9.3 SLAP).** Do NOT make it "a bag of inputs/outputs every stage reads and writes" — that re-introduces hidden shared mutable state and silently re-couples the stages. Make `PipelineContext` `@dataclass(frozen=True)`, **inputs-only**. Stage outputs flow EXCLUSIVELY via `StageResult.data`, accumulated by the loop — a stage MUST NOT both mutate `ctx` and return data (Command/Query separation, guide §2). Where practical, pass each stage only the slice it needs rather than the whole context (ISP, guide §3); if one context is unavoidable for the migration, document which fields each stage reads.
- **Acceptance**: `PipelineContext` is frozen/inputs-only; no stage mutates it; types compile under mypy --strict; no behavior change; all tests green.

### Step 2 — extract Collect + Generate stages `[x]`
- [x] Wrap `_stage_collect` and `_stage_generate` (+ segmented) as `CollectStage` / `GenerateStage`; `run_pipeline` calls them via the loop for these stages while the rest stays inline.
- [x] Move `_load_market_anchors/carryover/recent_for_run` to `orchestrator/stage_context.py` (`compute_bundle_context` already lived in `orchestrator/bundle_context.py`).
- **Acceptance**: full pipeline suite green unchanged; collect-empty and generate-failure routing identical.

### Step 3 — extract Publish stage + path normalization `[x]`
- [x] Wrap `_stage_publish` (+ `_stage_publish_segments`) as `PublishStage`; reproduce every publish-exception arm exactly (the prior 7-type publish tuple as `_PUBLISH_FAILURES`).
- [x] DEBT-062 (`_stage_publish_segments` absolute/relative path-normalization) — **DEFERRED, NOT folded.** Per the contract (clause 8) it is a behavior-touching change that must land as its own separate commit-state with an independent gate; folding it into this uncommitted pure-refactor working tree would entangle it. Left out-of-scope; DEBT-062 stays open.
- **Acceptance**: publish-failure routing (disclaimer/IO/git) identical; segmented all-or-fail preserved; the DEBT fix lands in a distinct commit; the DEBT's test shape simplifies without changing assertions.

### Step 4 — extract Notify + Health stages; move reader-format leak `[x]`
- [x] Wrap `_stage_notify_briefing` / segmented notify as `NotifyStage`; coverage/health logging as `HealthTrackingStage`.
- [x] Move `_apply_reader_format_to_segments` into `publisher/segment_reader_format.py` as `apply_reader_format_to_segments`; orchestrator calls it as a publisher API (re-imported under the legacy private name to keep callers' import path).
- **Acceptance**: notify (non-raising) + health-append behavior identical; reader-format output unchanged; module boundary clean (orchestrator → publisher only).

### Step 5 — convert `run_pipeline` to the routing loop `[x]`
- [x] Replaced the inline try/except cascade with a loop over injected stages using the exception→(alert/status) map, implemented as the declarative `EXCEPTION_ROUTING: dict[type[BaseException], StageAction]` (no `isinstance` chain; `_route_failure` does exact-type then MRO lookup). `_safe_alert` dedup + `_build_failure_context` preserved verbatim.
- [x] Stage sequence assembled at `build_default_stages()` composition root and injected via the new `stages=` parameter (default `None` → `build_default_stages()`); `run_pipeline` does NOT instantiate concrete stages inline.
- [x] **Pre-flight test-brittleness audit of `test_run_pipeline.py`**: assertions are overwhelmingly outcome-based (`result.status`, `result.stages[...]`, `alerter.calls`, `stage_timings` keyset). The only implementation-coupled checks are the AST-grep deny tests (no `asyncio.wait_for`/`gather`/retry-loop around bare `_stage_*` Name-calls) — satisfied because the loop calls `stage.execute(...)` (an attribute call, not a `_stage_*` Name-call) and no `_stage_*` Name-call sits inside a `for`/`while`. NO assertion rewrite was required; the suite passes unchanged.
- **Acceptance**: every `test_run_pipeline.py` case green unchanged; failure status + alert dispatch identical for all inputs; the exception→action map is a declarative dict; stages are injected from a composition root.

### Step 6 — full gate `[x]`
- [x] ruff / ruff-format / mypy --strict / pytest (full) / mkdocs build --strict — all green. pytest 2828 passed (+8 = new `test_stage_protocol.py`; baseline 2820 incl. concurrent u86 WIP).
- **Acceptance**: full gate green.

---

## Acceptance Criteria

- **AC-84.1** — A uniform `Stage` abstraction exists; `run_pipeline` is a sequencing + error-routing loop, not an inline cascade. The OCP win is on the *stage* axis (new stage = new class); the exception→action map is an intentional single change-point implemented as a declarative dict (not an `isinstance` chain). Stages are injected from a composition root, not instantiated inline.
- **AC-84.2** — For every input, the resulting pipeline status, alert dispatch, and partial-success behavior are identical to pre-refactor (proven by the unchanged `test_run_pipeline.py`).
- **AC-84.3** — `_apply_reader_format_to_segments` lives in `publisher/`; orchestrator calls it via a publisher API; module boundary intact.
- **AC-84.4** — Context loaders live in `stage_context.py`; the `_stage_publish_segments` path-normalization DEBT is resolved or explicitly deferred; mypy --strict clean.

---

## Tests / Validation

- `tests/unit/orchestrator/test_run_pipeline.py` (2164 lines), `test_main.py`, `test_bundle_context.py`; `tests/integration/test_pipeline.py` — all stay green **unchanged**. Any required change to an existing assertion means a behavior change → stop.
- New: `tests/unit/orchestrator/test_stage_protocol.py` for the abstraction itself.
- Gate: full `pytest` mandatory; mkdocs build --strict.

---

## Non-Goals

- Changing alerting policy, retry budget, or pipeline status semantics.
- Adding new stages or alert types.
- Touching u80 (notifier) or u83 (briefing) internals.
