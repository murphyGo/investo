# u98 watchpoint-card-list-redesign — Code Summary

Date: 2026-06-11
Status: Complete

## Scope

Replace the mobile-hostile §⑥ six-column watchpoint table with compact cards while keeping the existing watchpoint extraction, validation, confidence, compliance, and public API contracts.

## Implementation

- Kept `render_watchpoint_matrix()` signature and markdown-in/markdown-out semantics unchanged.
- Changed `render_matrix_table()` compatibility helper to emit canonical card blocks:
  `관찰 신호`, `출처`, `현재`, `확인 조건`, `신뢰도`, and `관심 영향`.
- Added source extraction and card-level sanitation for raw URLs, broken markdown fragments, trace tokens, pipes, and empty/default field fallbacks.
- Preserved `MAX_VISIBLE_ROWS`, row order, omitted-row note, u87 diagnostic filtering, and `DATA_LIMITED_NOTE` collapse.
- Filtered unusable/data-limited rows out of mixed valid output; all-unusable or coverage-limited sections collapse to the existing single note.
- Updated the Stage 2 prompt from a six-column matrix instruction to a card-populatable watchpoint instruction while retaining source+trigger+implication and advice-ban requirements.

## Validation

- `uv run --extra dev pytest tests/unit/publisher/test_watchpoint_matrix.py tests/unit/briefing/test_prompts.py -k "watchpoint or prompt"`
- `uv run --extra dev ruff check src/investo/publisher/watchpoint_matrix.py src/investo/briefing/prompts.py tests/unit/publisher/test_watchpoint_matrix.py tests/unit/briefing/test_prompts.py`
- `uv run --extra dev mypy src`
