# u96 quality-current-run-snapshot-sync — Code Summary

Date: 2026-06-11
Status: Complete

## Scope

Synchronize public quality surfaces with current-run segment evidence without adding a new quality taxonomy, source adapter, or dashboard redesign.

## Implementation

- Extended data-limited detection to include `[데이터부족]`, `데이터 부족 안내`, and `실시간 안내`.
- Added current-run fields to `QualitySnapshot` and persisted `quality_history.jsonl` rows:
  - `current_run_zero_item_sources`
  - `current_run_core_missing_segments`
  - `current_run_segments_limited_or_worse`
  - `current_run_data_limited_briefings`
  - `current_run_briefings_observed`
- Populated those fields in `orchestrator.pipeline::_build_quality_snapshot()` from final segment markdown, current source outcomes, and current per-segment severities.
- Strengthened `publisher.quality_consistency` so `quality.md` fails the publish-boundary gate when it understates current-run fallback, zero-item, core-missing, limited/failed, or observed-briefing evidence.
- Extended `reconcile_kpis_with_history()` so the rendered dashboard floors are raised from the same current-run history row before consistency validation.

## Validation

- `uv run --extra dev pytest tests/unit/briefing/test_quality_eval_kpis.py tests/unit/briefing/test_quality_history.py tests/unit/publisher/test_quality_consistency.py tests/unit/orchestrator/test_run_pipeline.py::test_run_pipeline_success_appends_quality_history`
- `uv run --extra dev ruff check src/investo/briefing/quality_eval.py src/investo/briefing/quality_history.py src/investo/publisher/quality_consistency.py src/investo/orchestrator/pipeline.py tests/unit/briefing/test_quality_eval_kpis.py tests/unit/briefing/test_quality_history.py tests/unit/publisher/test_quality_consistency.py tests/unit/orchestrator/test_run_pipeline.py`
- `uv run --extra dev mypy src/investo/briefing/quality_eval.py src/investo/briefing/quality_history.py src/investo/publisher/quality_consistency.py src/investo/orchestrator/pipeline.py`
