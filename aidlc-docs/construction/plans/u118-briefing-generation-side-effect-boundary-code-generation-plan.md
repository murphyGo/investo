# Code Generation Plan: `u118 briefing-generation-side-effect-boundary`

**Date**: 2026-06-24
**Unit**: u118 briefing-generation-side-effect-boundary
**Stage**: Code Generation
**Status**: Complete (2026-06-25)
**Source**: 2026-06-24 clean-code review of `briefing.generate_briefing` side-effect and result-boundary contracts.
**Estimated Effort**: ~4-6 h
**Dependencies**:
- u83 briefing-pipeline-decomposition is complete; do not repeat broad module decomposition.
- u94 bounded segment generation concurrency is complete; preserve segment timeout/retry behavior.
- u101 verified fact context and u108-u112 surface-quality follow-ups are complete.

---

## Problem Statement

After u83, `briefing/pipeline.py` is much thinner, but `generate_briefing` still exposes a long loosely grouped keyword list and hides side effects:

- `watchlist_config=None` causes briefing generation to call `load_watchlist()`, so a generation function performs caller/environment I/O.
- `macro_lineage_out` is a mutable out-param.
- `_classify` and `_synthesize` still duplicate retry/budget/subprocess loop mechanics.

This is not a feature issue, but it makes the briefing/orchestrator boundary harder to reason about and test.

## Goal

Introduce an explicit generation request/result boundary while preserving public compatibility:

- `GenerationInput`: immutable object containing all generation inputs.
- `GenerationResult`: immutable object containing the `Briefing` plus auxiliary artifacts such as macro lineage.
- `generate_briefing_from_input(input) -> GenerationResult` as canonical API.
- Existing `generate_briefing(...) -> Briefing` remains compatible and delegates.
- Production orchestrator paths pass an already loaded `WatchlistConfig`.
- Production macro lineage flows through `GenerationResult`, not a mutable out-param.
- LLM retry-loop duplication is reduced only if the helper keeps Stage 1 and Stage 2 specifics explicit.

## Existing Coverage / Deduplication

- u83 already decomposed briefing internals; do not reopen that package split.
- `GenerationPolicy` and `RetryBudget` already model generation policy and retry budget.
- Orchestrator already owns segment orchestration, recent context, carryover, bundle context, fact context, and macro-lineage aggregation.

## Scope Boundary

In scope:
- Add `GenerationInput` and `GenerationResult`.
- Add a canonical structured generation function returning `GenerationResult`.
- Keep existing `generate_briefing(...) -> Briefing` compatibility.
- Move production watchlist I/O to orchestrator/default callers.
- Replace production macro-lineage out-param flow with result payload.
- Optionally extract a small private LLM dispatch helper if it is clearly simpler.

Out of scope:
- No prompt text change.
- No rendered markdown change.
- No section planning/classification/synthesis behavior change.
- No `Briefing` model change.
- No public removal of `generate_briefing(...)`.
- No Anthropic SDK or paid API path.
- No broad second decomposition of u83 package layout.

## Stage Decision

Functional Design: skip. This is a bounded behavior-preserving internal contract cleanup. If implementation would remove public compatibility or change cross-component behavior, stop and route to Functional Design.

NFR Requirements: skip. No new dependency, source, secret, network call, workflow, storage format, or paid API.

## Fixed Contracts

### GenerationInput

Add an immutable contract object, preferably in `briefing/generation_contract.py` and re-exported from `briefing/pipeline.py`.

Rules:

- `target_date`, `items`, and explicit `watchlist_config` are required.
- Construction must not read files, environment variables, or global path state.
- Optional fields mirror existing generation inputs without changing their semantics.
- Tuple-normalization is allowed if order is preserved.

### GenerationResult

Add an immutable result object:

```python
@dataclass(frozen=True, slots=True)
class GenerationResult:
    briefing: Briefing
    macro_lineage: tuple[MacroLineageTrace, ...] = ()
```

Rules:

- Canonical generation returns `GenerationResult`.
- Existing public `generate_briefing(...)` returns `result.briefing`.
- `macro_lineage` is empty when no lineage applies.

### Compatibility Wrapper

The existing `generate_briefing(...)` signature remains valid:

- If `watchlist_config is None`, legacy wrapper may still call `load_watchlist()`.
- Production/default orchestrator paths must not rely on that fallback.
- If legacy `macro_lineage_out` is supplied, the wrapper extends it from `GenerationResult.macro_lineage`.

### LLM Stage Runner Constraint

Only extract shared LLM loop mechanics if the resulting private helper stays small and explicit. Stage-specific prompt construction, JSON/section validation, retry feedback, and failure semantics must stay in `_classify` and `_synthesize`.

## Implementation Steps

- [x] Add `briefing/generation_contract.py` with `GenerationInput` and `GenerationResult`.
- [x] Re-export both from `briefing/pipeline.py`.
- [x] Add `generate_briefing_from_input(request: GenerationInput) -> GenerationResult`.
- [x] Move the current generation body behind the canonical structured API.
- [x] Keep `generate_briefing(...) -> Briefing` as a compatibility wrapper.
- [x] Change `_record_macro_lineage` or its call site so lineage is returned as a tuple, not written through production out-param.
- [x] Update default orchestrator generation to pass explicit `WatchlistConfig`.
- [x] Preserve non-default generator seams unless an explicit typed compatibility adapter is needed.
- [x] Extract LLM retry-loop mechanics only if the helper is simpler and tests prove identical behavior. Decision: skipped because the existing Stage 1/Stage 2 functions keep validation and retry feedback clearer.
- [x] Add tests for canonical no-watchlist-I/O behavior, wrapper compatibility, macro-lineage result payload, and orchestrator explicit watchlist handoff.
- [x] Write `aidlc-docs/construction/u118-briefing-generation-side-effect-boundary/code/summary.md`.

## Acceptance Criteria

1. `GenerationInput` and `GenerationResult` are importable briefing contracts.
2. `generate_briefing_from_input(...)` is the canonical API and returns `GenerationResult`.
3. The canonical API does not call `load_watchlist()`.
4. Existing `generate_briefing(...) -> Briefing` calls remain compatible.
5. Production orchestrator default generation passes explicit `WatchlistConfig`.
6. Production macro lineage is returned through `GenerationResult`.
7. Legacy `macro_lineage_out` remains supported only in the compatibility wrapper.
8. Generated markdown stays unchanged for representative tests.
9. `BriefingGenerationError` labels, attempts, stdout/stderr fields, and budget behavior remain unchanged.
10. Any LLM loop extraction keeps Stage 1/Stage 2 validation explicit; otherwise it is skipped.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/briefing/test_budget_guard.py tests/unit/briefing/test_budget_happy_path.py tests/unit/briefing/test_watchlist_pipeline_u28.py tests/unit/briefing/test_failure_contract.py tests/unit/orchestrator/test_stage_generate.py tests/unit/orchestrator/test_run_pipeline.py tests/integration/test_pipeline.py
uv run --extra dev ruff check src/investo/briefing src/investo/orchestrator tests/unit/briefing tests/unit/orchestrator tests/integration/test_pipeline.py
uv run --extra dev ruff format --check src/investo/briefing src/investo/orchestrator tests/unit/briefing tests/unit/orchestrator tests/integration/test_pipeline.py
uv run --extra dev mypy src
```

Full gate is recommended because this touches the briefing/orchestrator boundary:

```bash
uv run --extra dev pytest
uv run --extra dev mkdocs build --strict
```

## Non-Goals

- No prompt rewrite.
- No markdown/rendering change.
- No source adapter change.
- No publisher/notifier behavior change.
- No new external dependency.
- No public removal of `generate_briefing(...)`.
