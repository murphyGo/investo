# u65 generated-briefing-quality-replay-harness Code Summary

**Date**: 2026-05-23
**Status**: Complete

## Delivered

- Added `investo.publisher.briefing_replay` offline replay checks for generated archive markdown.
- Added `scripts/replay_generated_briefing_quality.py` CLI wrapper.
- Replay checks cover first-viewport summary validation, `본문 사용 0` with trace/source evidence, missing segment artifacts, missing nav labels, BTC/BTM watchlist mismatches, weak watchpoints, and missing quality-history rows.
- Added deterministic fixture tests for failing and missing-bundle cases.

## Verification

- `uv run pytest tests/unit/publisher/test_briefing_replay.py -q`
- Included in combined targeted gate: 192 passed.

