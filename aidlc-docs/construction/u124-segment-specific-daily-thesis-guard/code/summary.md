# u124 Code Summary: segment-specific-daily-thesis-guard

## Overview

u124 prevents the daily thesis line from being stamped identically across domestic, US, and crypto segment pages. The bundle-level daily thesis decision now carries segment-specific rendered lines while preserving the original u99 marker and compatibility line.

## Files Changed

- `src/investo/models/bundle_context.py` adds `SegmentDailyThesisInput` and `DailyThesisDecision.per_segment_lines`.
- `src/investo/orchestrator/bundle_context.py` builds deterministic segment-native consequence lines from shared macro keys, segment evidence labels, and the fixed native-term lexicon.
- `src/investo/publisher/daily_thesis.py` renders the line for the current segment and blocks the three-segment identical-line regression.
- `src/investo/publisher/segment_reader_format.py` validates bundle-level thesis distinctness before reader-format rewrites and injects the current segment's line.
- `src/investo/publisher/errors.py`, `publisher.__init__`, and `orchestrator.pipeline` add `DailyThesisConsistencyError` routing as a publish-stage failure.
- `src/investo/briefing/prompts.py` keeps Stage 2 from authoring the publisher-owned thesis line.
- Tests cover segment-specific precedence, fallback repetition, publish routing, and three-segment consequence distinctness.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Keep `DailyThesisDecision.line` | Preserves u99 compatibility for callers/tests that do not pass a segment. |
| Use `per_segment_lines` at publish time | The publisher already knows the current segment and owns the marker insertion point. |
| Allow repeated bounded fallback | The fixed fallback is the safe insufficient-evidence state; blocking it would fail low-signal bundles for the wrong reason. |
| Route repeated non-fallback lines as a publish failure | The defect is a public artifact consistency problem, not a recoverable single-segment surface-quality retry. |

## Validation

- `uv run --extra dev pytest tests/unit/orchestrator/test_bundle_context.py tests/unit/publisher/test_daily_thesis.py tests/unit/briefing/test_prompts.py tests/unit/orchestrator/test_stage_protocol.py`

## TECH-DEBT

None.
