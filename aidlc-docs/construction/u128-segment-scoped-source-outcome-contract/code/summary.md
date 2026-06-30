# u128 Code Summary: Segment-Scoped Source Outcome Contract

## Outcome

Completed the source-outcome scoping contract hardening. `build_segment_coverage` no longer silently accepts a global mixed-segment `SourceOutcome` list.

## Changes

- Added `SegmentScopedOutcomes = NewType("SegmentScopedOutcomes", tuple[SourceOutcome, ...])`.
- Added `scope_source_outcomes(outcomes, segment)` and kept `segment_source_outcomes(segment, outcomes)` as the compatibility boundary builder.
- Added a defensive `build_segment_coverage` validation step that raises `ValueError` when any supplied outcome source is outside the target segment allow-list.
- Preserved shared-source and CFTC outcome semantics through the existing source-spec-derived outcome segment registry.
- Added tests for cross-segment rejection and shared/CFTC visibility.

## Validation

- `uv run --extra dev pytest tests/unit/briefing/test_segments.py tests/unit/briefing/test_segments_severity.py tests/unit/orchestrator/test_stage_generate.py tests/unit/orchestrator/test_run_pipeline.py`
- `uv run --extra dev ruff check src/investo/briefing/segments.py src/investo/orchestrator tests/unit/briefing/test_segments.py tests/unit/briefing/test_segments_severity.py tests/unit/orchestrator/test_stage_generate.py tests/unit/orchestrator/test_run_pipeline.py`
- `uv run --extra dev ruff format --check src/investo/briefing/segments.py src/investo/orchestrator tests/unit/briefing/test_segments.py tests/unit/briefing/test_segments_severity.py tests/unit/orchestrator/test_stage_generate.py tests/unit/orchestrator/test_run_pipeline.py`
- `uv run --extra dev mypy src`

## Debt

- Closed `DEBT-038`.
