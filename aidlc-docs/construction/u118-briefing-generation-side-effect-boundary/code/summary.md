# u118 Code Generation Summary: briefing-generation-side-effect-boundary

**Status**: Complete
**Date**: 2026-06-25
**Commit**: this unit commit

## Scope

Implemented a behavior-preserving briefing/orchestrator contract cleanup:

- Added immutable `GenerationInput` and `GenerationResult` contracts.
- Added `generate_briefing_from_input(...) -> GenerationResult` as the canonical generation API.
- Kept `generate_briefing(...) -> Briefing` as a compatibility wrapper, including legacy `watchlist_config=None` and `macro_lineage_out` support.
- Moved production watchlist loading to orchestrator/default callers so canonical generation requires explicit `WatchlistConfig`.
- Returned production macro lineage through `GenerationResult.macro_lineage` instead of a mutable production out-param.
- Preserved custom segment generator seams and existing briefing failure/budget semantics.

## Design Notes

- `GenerationInput` tuple-normalizes sequence inputs without reading files, environment variables, or global path state.
- `generate_briefing_from_input` owns the current two-stage generation body and never calls `load_watchlist()`.
- The legacy wrapper remains the only generation entry point that may load the watchlist fallback or mutate `macro_lineage_out`.
- `_stage_generate_segments` loads one `WatchlistConfig` for the default production generator path and passes that explicit object to each segment.
- LLM retry-loop extraction was intentionally skipped. The current `_classify` and `_synthesize` functions keep stage-specific prompt construction, validation, feedback, and error labeling clearer than a shared helper would.

## Tests Added

- Canonical `GenerationInput` API does not call `load_watchlist()`.
- Canonical result carries macro lineage.
- Legacy wrapper still extends `macro_lineage_out`.
- Default segmented orchestrator passes an explicit watchlist config to each default segment generation call.

## Validation

```bash
uv run --extra dev pytest tests/unit/briefing/test_budget_guard.py tests/unit/briefing/test_budget_happy_path.py tests/unit/briefing/test_watchlist_pipeline_u28.py tests/unit/briefing/test_failure_contract.py tests/unit/orchestrator/test_stage_generate.py tests/unit/orchestrator/test_run_pipeline.py tests/integration/test_pipeline.py
uv run --extra dev ruff check src/investo/briefing src/investo/orchestrator tests/unit/briefing tests/unit/orchestrator tests/integration/test_pipeline.py
uv run --extra dev ruff format --check src/investo/briefing src/investo/orchestrator tests/unit/briefing tests/unit/orchestrator tests/integration/test_pipeline.py
uv run --extra dev mypy src
uv run --extra dev pytest
uv run --extra dev mkdocs build --strict
```

## TECH-DEBT

None.
