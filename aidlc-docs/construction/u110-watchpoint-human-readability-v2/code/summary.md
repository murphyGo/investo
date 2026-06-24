# u110 watchpoint-human-readability-v2 - Code Summary

**Date**: 2026-06-24
**Status**: Complete
**Stage**: Code Generation

## Summary

Closed the u110 §⑥ watchpoint card readability follow-up. The u98 card shape
is unchanged, but card fields are now normalized before public rendering:
duplicate field prefixes are stripped, source labels can be promoted from
current/trigger/implication text, up/down triggers must be present and
distinct, and rows with invalid public value collapse to the existing bounded
data-limited note.

## Changes

- `src/investo/publisher/watchpoint_matrix.py`
  - Added field-prefix stripping for `현재:`, `출처:`, `확인 소스:`, `상방:`,
    `하방:`, `관심 영향:`, and `섹션 내 관심 영향:`.
  - Added source promotion from source/current/up/down/implication fields with
    rejection for missing/data-limited source values.
  - Prefer explicit `상방:`/`하방:` clauses over semantic text such as
    `상방 압력`, preserving the latter in the current field.
  - Reject public cards with missing source, missing triggers, identical
    normalized triggers, or too many low-value placeholder fields.
  - Render trigger text without `상방 상방` / `하방 하방` duplication.
- `src/investo/briefing/prompts.py`
  - Tightened the §⑥ Stage-2 prompt contract with the u110
    human-readability rule: no duplicate card labels, and up/down triggers must
    be distinct.
- Tests
  - Added u110 regressions for source promotion, duplicate label stripping,
    identical-trigger collapse, mixed valid/invalid sections, and soft-invalid
    row scoring.
  - Updated older u98 expectations so the historical duplicate-label artifacts
    are no longer accepted.

## Validation

```bash
uv run --extra dev pytest tests/unit/publisher/test_watchpoint_matrix.py tests/unit/briefing/test_prompts.py tests/unit/publisher/test_segment_reader_surface_quality.py
# 73 passed

uv run --extra dev ruff check src/investo/publisher/watchpoint_matrix.py src/investo/briefing/prompts.py tests/unit/publisher/test_watchpoint_matrix.py tests/unit/briefing/test_prompts.py
# All checks passed

uv run --extra dev mypy src
# Success: no issues found in 211 source files
```

`tests/unit/publisher/test_segment_reader_format.py` from the plan does not
exist in the current repo; the closest public segment-reader surface-quality
test file, `tests/unit/publisher/test_segment_reader_surface_quality.py`, was
used in the targeted gate.

## TECH-DEBT

None.
