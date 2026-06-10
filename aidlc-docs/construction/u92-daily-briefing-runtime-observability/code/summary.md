# u92 Daily Briefing Runtime Observability — Code Summary

## Status

Complete on 2026-06-10.

## Scope Delivered

- Added backward-compatible `SourceOutcome.elapsed_s` with constructor support and non-negative validation.
- Timed every source adapter invocation in `collect_sources`, including zero-item and `SourceFetchError` outcomes, while preserving registry-order outcomes and existing non-source exception propagation.
- Extended source success/failure logs with structured `elapsed_s`.
- Added segmented generate sub-timings:
  - `generate:context`
  - `generate:bundle_context`
  - `generate:domestic-equity`
  - `generate:us-equity`
  - `generate:crypto`
  - `generate:reader_format`
- Kept the coarse `generate` timing as whole-stage elapsed time for backward-compatible operator surfaces.
- Added private INFO logs for each Claude classification/synthesis attempt with segment, stage, attempt, timeout, elapsed seconds, prompt byte length, stdout/stderr lengths, and return code. Prompt text is not logged.
- Extended GitHub step summary rendering so synthetic timing keys appear in the stage table and the top 10 slowest sources are visible when source elapsed data exists.

## Behavior Boundaries

- No prompt content changed.
- No LLM retry, timeout, budget, or error-payload semantics changed.
- No segment concurrency or source adapter retry behavior changed.
- No public briefing markdown, Telegram text, or archive layout intentionally changed.

## Validation

- `uv run --extra dev pytest tests/unit/models/test_coverage.py tests/unit/sources/test_aggregator.py tests/unit/sources/test_collect_sources.py tests/unit/briefing/test_budget_happy_path.py tests/unit/orchestrator/test_main.py tests/unit/orchestrator/test_run_pipeline.py -q`
  - 170 passed
- `uv run --extra dev ruff check src/investo/models/coverage.py src/investo/sources/aggregator.py src/investo/briefing/_core/orchestration.py src/investo/briefing/pipeline.py src/investo/orchestrator/pipeline.py src/investo/__main__.py tests/unit/models/test_coverage.py tests/unit/sources/test_aggregator.py tests/unit/sources/test_collect_sources.py tests/unit/briefing/test_budget_happy_path.py tests/unit/orchestrator/test_main.py tests/unit/orchestrator/test_run_pipeline.py`
  - All checks passed
- `uv run --extra dev mypy src`
  - Success: no issues found in 193 source files

## Notes For Next Units

- u94 can now use `generate:<segment>` timings to evaluate bounded segment concurrency payoff.
- u95 can use slowest-source rows and `generate:context` / `generate:bundle_context` / `visual_assets` timings to identify critical-path enrichment work.
