# u94 Bounded Segment Generation Concurrency — Code Summary

## Status

Complete on 2026-06-10.

## Scope Delivered

- Added `INVESTO_SEGMENT_GENERATION_CONCURRENCY` parsing in `orchestrator/pipeline.py`.
  - Valid: `1`, `2`, `3`
  - Default: `1`
  - Invalid: warning + fallback to `1`
- Extracted segment generation into `_generate_one_segment`.
- Added `_SegmentGenerationResult` carrying `segment`, `briefing`, `failure`, `macro_lineage`, and `elapsed_s`.
- Added bounded fanout inside `_stage_generate_segments` using `asyncio.Semaphore`.
- Reassembled `briefings`, `failures`, `macro_lineage_by_segment`, and `generate:<segment>` timings in `SEGMENT_ORDER`.

## Behavior Boundaries

- Top-level pipeline stages remain sequential.
- Source collection, visual assets, publish, notify, health, and git paths are not parallelized.
- Claude CLI invocation, timeout, retry count, prompt content, and runner semantics are unchanged.
- `BriefingGenerationError` remains segment-isolated.
- Programmer errors still propagate.

## Validation

- `uv run --extra dev pytest tests/unit/orchestrator/test_run_pipeline.py -q`
  - 74 passed
- `uv run --extra dev pytest tests/unit/orchestrator -q`
  - 323 passed
- `uv run --extra dev pytest tests/integration/test_pipeline.py -q`
  - 7 passed
- `uv run --extra dev ruff check src/investo/orchestrator tests/unit/orchestrator`
  - All checks passed
- `uv run --extra dev mypy src`
  - Success: no issues found in 193 source files

## Notes For Operation

Keep the default at `1` until u92 timing data shows stable segment durations. Test `2` first for normal runs; reserve `3` for short-lived trials because all three segments can dispatch Claude calls at once.
