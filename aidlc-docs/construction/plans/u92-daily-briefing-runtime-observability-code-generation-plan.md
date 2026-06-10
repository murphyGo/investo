# Code Generation Plan: `u92 daily-briefing-runtime-observability`

**Date**: 2026-06-09
**Unit**: u92 daily-briefing-runtime-observability
**Stage**: Code Generation
**Status**: Complete
**Source**: 2026-06-04/09 daily briefing speed investigation
**Estimated Effort**: ~4-6 h
**Dependencies**:
- u10 source diagnostics complete
- u84 orchestrator-stage-abstraction complete

---

## Problem Statement

The daily briefing pipeline has grown from a single generated article into three segmented briefings plus source coverage, market anchors, visual assets, reader-format transforms, quality pages, forecast logs, watchlist pages, and git publishing. The current operator-facing timing surface is still coarse:

- `PipelineResult.stage_timings` reports broad stage keys such as `collect`, `generate`, `visual_assets`, `publish`, and `notify_briefing`.
- `GenerateStage` includes recent-context loading, Yahoo history market-anchor fetch, carryover parsing, macro carryover, three segment LLM generations, visual preparation, chart block injection, and reader-format work.
- `collect_sources` runs adapters concurrently but only reports item count/status, not elapsed seconds per adapter.
- `call_claude_code` measures elapsed seconds but `_classify` and `_synthesize` do not log attempt-level timing with segment and stage labels.

Without finer timing, a later implementation agent cannot tell whether a slow run was dominated by a source adapter, one segment's Stage 2 synthesis, visual asset preparation, publish/index generation, or workflow setup.

## Goal

Expose timing at the level needed to make speed work evidence-backed:

- per-source elapsed seconds,
- per-segment generation elapsed seconds,
- generate-context and reader-format elapsed seconds,
- per-Claude-attempt metadata,
- GitHub step summary rows that surface the slowest runtime components.

This unit must not change behavior, output markdown, retry policy, concurrency, source collection result ordering, or pipeline status routing.

## Existing Coverage / Deduplication

- u10 already logs `source returned` with source name, category, item count, and UTC window. u92 extends that diagnostic to elapsed seconds.
- u84 already decomposes the orchestrator into stage objects and keeps `run_pipeline` as a sequencing loop. u92 adds sub-stage timing keys without adding or reordering top-level stages.
- `PipelineResult.stage_timings` already accepts arbitrary non-negative stage keys, so u92 should reuse it instead of adding a second timing model.
- u92 is the prerequisite measurement unit for u94 and u95. It does not implement concurrency or workflow caching.

## Scope Boundary

In scope:
- Add elapsed seconds to `SourceOutcome` in a backward-compatible way.
- Measure each adapter fetch duration inside `collect_sources`.
- Add per-segment generation timing to `_stage_generate_segments`.
- Split generate-stage context and reader-format timing into explicit timing keys.
- Add structured INFO logs for each Claude attempt.
- Render the new timing keys and slowest sources in GitHub step summary.

Out of scope:
- Changing adapter retry policies or source ordering.
- Changing candidate selection, prompts, or LLM timeout values.
- Changing segment generation concurrency.
- Changing publish artifacts or Telegram text.

## Stage Decision

- **Functional Design — SKIP.** This is an observability refinement over existing runtime entities.
- **NFR Requirements — SKIP.** No new dependency, source, secret, external service, or cost surface. The implementation strengthens NFR-001 measurement and NFR-003 triage.

## Implementation Steps

### Step 1 — extend `SourceOutcome` elapsed timing

- [x] Add `elapsed_s: float | None = None` to `src/investo/models/coverage.py::SourceOutcome`.
- [x] Keep existing constructors backward-compatible: `ok`, `zero`, and `from_failure` accept optional `elapsed_s`.
- [x] Validate `elapsed_s` as `None` or `>= 0`.
- [x] Update model tests so omitted `elapsed_s` remains backward-compatible and negative values are rejected.

### Step 2 — measure source adapter durations

- [x] In `src/investo/sources/aggregator.py::collect_sources`, wrap each adapter coroutine so it returns elapsed seconds with the adapter result.
- [x] Preserve failure isolation and registry order while retaining elapsed seconds for exceptions.
- [x] Attach elapsed seconds to every `SourceOutcome`, including failed and zero-item outcomes.
- [x] Extend source logs with `elapsed_s=...` in the existing `source returned` and `source failed` log lines.

### Step 3 — measure generate sub-stages

- [x] In `GenerateStage.execute`, record `generate:context` for recent context, market anchors, KR anchor merge, carryover, and macro carryover; record `generate:bundle_context` inside `_stage_generate_segments`.
- [x] In `_stage_generate_segments`, record per-segment timings as `generate:domestic-equity`, `generate:us-equity`, and `generate:crypto`.
- [x] Record `generate:reader_format` for `_apply_reader_format_to_segments`.
- [x] Keep existing broad `generate` timing equal to the whole generate stage so older readers still see the coarse number.

### Step 4 — log each Claude attempt

- [x] Add `segment: MarketSegment | None` and `llm_stage` labels to the private orchestration logging path.
- [x] After each `call_claude_code` return, log one INFO record with `segment`, `llm_stage`, `attempt`, `timeout_s`, `elapsed_s`, `prompt_bytes`, `stdout_len`, `stderr_len`, and `returncode`.
- [x] Redact no prompt content; log only lengths and labels.
- [x] Keep retry behavior and `BriefingGenerationError` payloads unchanged.

### Step 5 — render summary

- [x] Update `src/investo/__main__.py::_write_github_step_summary` so the existing stages table includes synthetic timing keys.
- [x] Add a compact "Slowest Sources" table with at most 10 rows, sorted by elapsed seconds descending, only when source elapsed data exists.
- [x] Apply the existing `_redact_diagnostic_text` path to source names and diagnostic stage text; source detail rows keep the existing source-table redaction path for reasons.

## Acceptance Criteria

1. `SourceOutcome` accepts and serializes `elapsed_s`, and older payloads without the field still validate.
2. A fake slow adapter produces a `SourceOutcome.elapsed_s` value greater than a fake fast adapter while preserving adapter order in `outcomes`.
3. A successful segmented run records `generate:domestic-equity`, `generate:us-equity`, `generate:crypto`, `generate:context`, and `generate:reader_format` timing keys.
4. A failed segment still records its segment timing before the failure is surfaced.
5. LLM attempt logs contain lengths and timing metadata but never prompt text, token values, or chat IDs.
6. GitHub step summary includes the new timing keys and slowest-source rows without changing the pipeline exit-code mapping.

## Tests / Validation

- `tests/unit/models/test_results.py` and source outcome model tests for `elapsed_s` validation.
- `tests/unit/sources/test_aggregator.py` or `tests/unit/sources/test_collect_sources.py` for elapsed timing and ordering.
- `tests/unit/orchestrator/test_stage_generate.py` for per-segment and context timing.
- `tests/unit/orchestrator/test_run_pipeline.py` for summary-compatible `stage_timings`.
- `tests/unit/orchestrator/test_main.py` for GitHub step summary rendering.
- Local gate: `uv run pytest tests/unit/models tests/unit/sources tests/unit/briefing tests/unit/orchestrator -q`, `uv run ruff check src tests`, `uv run mypy --strict src`.

## Non-Goals

- Runtime speed improvement by itself.
- Parallel execution changes.
- Source adapter retry tuning.
- Prompt content changes.
- New public site pages.
