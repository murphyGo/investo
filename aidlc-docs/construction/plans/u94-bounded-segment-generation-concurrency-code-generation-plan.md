# Code Generation Plan: `u94 bounded-segment-generation-concurrency`

**Date**: 2026-06-09
**Unit**: u94 bounded-segment-generation-concurrency
**Stage**: Code Generation
**Status**: Complete
**Source**: 2026-06-04/09 daily briefing speed investigation
**Estimated Effort**: ~6-9 h
**Dependencies**:
- u7 segmented briefing complete
- u84 orchestrator-stage-abstraction complete
- u92 daily-briefing-runtime-observability complete

---

## Problem Statement

The segmented daily briefing generates domestic-equity, us-equity, and crypto briefings independently, but `_stage_generate_segments` awaits them in fixed order. Each non-empty segment can run Stage 1 classification and Stage 2 synthesis, so a normal all-segment run makes at least six Claude CLI calls. Current segment policies allow a high per-call timeout and two attempts per segment. Serial execution means one slow segment delays the start of every later segment.

The existing runtime already isolates `BriefingGenerationError` per segment: one failed segment can still allow the successful sibling segments to publish, while all segment failures fail the pipeline. That isolation makes bounded intra-stage concurrency a natural speed unit.

## Goal

Run independent segment generation tasks concurrently under an explicit environment-controlled limit while preserving every publish and failure semantic:

- top-level stages remain sequential,
- source collection still completes before generation,
- shared context is built once before segment tasks,
- per-segment failures remain isolated,
- all failed segments still fail the pipeline,
- output ordering remains `SEGMENT_ORDER`.

## Existing Coverage / Deduplication

- u7 created segmented briefing and partial-publish semantics. u94 must keep those semantics intact.
- u84 made top-level stage sequencing explicit. u94 does not add `asyncio.gather` across top-level stages; it only fans out independent segment work inside `GenerateStage`.
- u92 provides measurement keys so before/after speed impact can be observed.
- u93 reduces prompt size first; u94 still works without u93 but must not depend on prompt internals.

## Scope Boundary

In scope:
- Parse `INVESTO_SEGMENT_GENERATION_CONCURRENCY` as an integer 1 through 3.
- Run segment generation tasks through a bounded semaphore.
- Preserve deterministic returned dict ordering by assembling results in `SEGMENT_ORDER`.
- Preserve macro lineage collection per segment.
- Add tests that prove task overlap and failure isolation.

Out of scope:
- Parallelizing collect, publish, notify, or health stages.
- Changing Claude CLI runner implementation.
- Changing segment generation policies, timeout values, or retry count.
- Changing article content, prompt templates, or source routing.

## Stage Decision

- **Functional Design — SKIP.** This is an orchestration scheduling refinement over existing segment generation.
- **NFR Requirements — REQUIRED, focused.** Concurrency touches NFR-001 runtime, NFR-003 graceful degradation, and NFR-007 subprocess/secret safety. The NFR addendum must document env parsing, default rollout value, failure isolation, and no prompt/secret logging.

## Implementation Steps

### Step 1 — add concurrency config

- [x] Add a private helper in `src/investo/orchestrator/pipeline.py`:
  - env var: `INVESTO_SEGMENT_GENERATION_CONCURRENCY`,
  - accepted values: `1`, `2`, `3`,
  - default: `1`,
  - invalid value: log WARNING and return `1`.
- [x] Add tests for absent, valid, zero, negative, high, and non-integer values.

### Step 2 — split one-segment generation into a helper

- [x] Extract the body of the current `for segment in SEGMENT_ORDER` loop into an async helper that accepts all segment-scoped inputs.
- [x] The helper returns a small result object with:
  - `segment`,
  - `briefing`,
  - `failure`,
  - `macro_lineage`,
  - `elapsed_s`.
- [x] The helper catches only `BriefingGenerationError`; programmer errors still propagate.

### Step 3 — add bounded task fanout

- [x] Build one task per segment using the helper and an `asyncio.Semaphore`.
- [x] Await all segment tasks with `asyncio.gather(..., return_exceptions=True)`.
- [x] Re-raise programmer errors exactly as the serial loop did.
- [x] Convert `BriefingGenerationError` values into the existing `failures` dict.
- [x] Reassemble `briefings` and `macro_lineage_by_segment` in `SEGMENT_ORDER`, not task-completion order.

### Step 4 — preserve status and alert semantics

- [x] Keep the current all-failed behavior: `raise next(iter(failures.values()))`.
- [x] Keep partial behavior: successful segment briefings continue to publish.
- [x] Keep per-segment warning logs with segment, stage, and attempt count.
- [x] Add u92 timing keys for every segment, including failed segments.

### Step 5 — tests

- [x] Add a fake segment generator that blocks on events so tests can prove concurrency 2 starts two segments before the first finishes.
- [x] Add a concurrency 1 test that proves behavior remains serial by start order.
- [x] Add one-failure and all-fail tests.
- [x] Add a programmer-error propagation test.
- [x] Keep existing `test_run_pipeline.py` stage-gather deny tests green.

## Acceptance Criteria

1. With env absent, segment generation remains serial and behavior-compatible.
2. With env value `2`, two segment generation tasks can be in flight at once.
3. With env value `3`, all three segment generation tasks can be in flight at once.
4. Invalid env values fall back to serial execution and log a warning.
5. Returned `briefings`, `failures`, and `macro_lineage_by_segment` are deterministic and ordered by `SEGMENT_ORDER`.
6. Per-segment `BriefingGenerationError` isolation and all-fail behavior are unchanged.
7. Programmer errors are not swallowed.
8. No prompt text, token, or chat ID is logged by the concurrency implementation.

## Tests / Validation

- `tests/unit/orchestrator/test_run_pipeline.py` for helper behavior, concurrency, and end-to-end partial/fail behavior.
- `tests/integration/test_pipeline.py` for segmented publish happy path.
- Local gate: `uv run pytest tests/unit/orchestrator tests/integration/test_pipeline.py -q`, `uv run ruff check src/investo/orchestrator tests/unit/orchestrator`, `uv run mypy --strict src`.

## Non-Goals

- Making concurrency the default above 1 in the same unit. The env default remains 1 for a controlled rollout.
- Changing generation timeout policies.
- Running publish before every segment completes.
- Sharing one Claude process across segments.
- Implementing source-adapter concurrency changes.
