# u99 daily-thesis-layer — Code Summary

Date: 2026-06-11
Status: Complete

## Scope

Add a deterministic cross-segment "오늘의 큰 그림" line without adding another LLM call, new data source, or post-render narrative rewrite.

## Implementation

- Added `DailyThesisSignal` and `DailyThesisDecision` to `BundleContext` with backward-compatible defaults.
- Extended `compute_bundle_context()` to compute daily-thesis signals from existing u57 shared macro keys and choose `strong`, `data_limited`, or `omit`.
- Kept strong thesis decisions gated by u74-approved cause-map types.
- Added `publisher.daily_thesis` for rendering and idempotent insertion/removal of the thesis marker before §①.
- Wired daily-thesis insertion into `segment_reader_format` after cause-map insertion and before compliance gates.
- Added a compact Stage 2 prompt guard so the LLM does not author `> **오늘의 큰 그림:**`.

## Validation

- `uv run --extra dev pytest tests/unit/publisher/test_daily_thesis.py tests/unit/orchestrator/test_bundle_context.py tests/unit/publisher/test_cross_market_cause_map.py tests/unit/briefing/test_prompts.py -k "daily_thesis or bundle_context or cause_map or stage2_system_prompt"`
- `uv run --extra dev ruff check src/investo/models/bundle_context.py src/investo/orchestrator/bundle_context.py src/investo/publisher/daily_thesis.py src/investo/publisher/segment_reader_format.py src/investo/briefing/prompts.py tests/unit/publisher/test_daily_thesis.py tests/unit/orchestrator/test_bundle_context.py tests/unit/briefing/test_prompts.py`
- `uv run --extra dev mypy src/investo/models/bundle_context.py src/investo/orchestrator/bundle_context.py src/investo/publisher/daily_thesis.py src/investo/publisher/segment_reader_format.py`
