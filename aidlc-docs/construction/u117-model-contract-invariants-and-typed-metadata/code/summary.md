# u117 model-contract-invariants-and-typed-metadata - Code Summary

**Date**: 2026-06-24
**Status**: Complete
**Stage**: Code Generation

## Summary

Hardened foundation model contracts by enforcing `SourceOutcome` cross-field
invariants at direct construction time and adding a typed macro metadata view
over the existing flat `NormalizedItem.raw_metadata` bag.

## Changes

- Updated `src/investo/models/coverage.py`
  - `SourceOutcome.__post_init__` now rejects invalid status/category/tier
    values, negative item counts, non-finite or negative elapsed seconds, and
    naive `latest_item_at` timestamps.
  - Enforces status-specific states:
    - `ok`: `item_count > 0`, no `failure_reason`, no `transient`
    - `zero`: `item_count == 0`, no `failure_reason`, no `transient`
    - `failed`: `item_count == 0`, non-empty `failure_reason`,
      `transient` is a bool
  - Existing `ok`, `zero`, and `from_failure` factories remain compatible for
    valid call sites.
- Updated `src/investo/models/macro.py`
  - Added `MacroMetadataIssueCode`, `MacroMetadataIssue`, and
    `MacroMetadataView`.
  - Added `macro_metadata_view(item)` as the single typed parse boundary for
    flat macro metadata.
  - Refactored `macro_event_key`, `macro_event_status`, `macro_priority`,
    `is_required_macro_actual`, `macro_required_sections`,
    `macro_event_date`, and `macro_prompt_payload` through the view.
  - Invalid explicit macro status/priority values now emit bounded issues and
    suppress inference for that field.
  - Invalid dates emit `invalid_macro_event_date` and fall back through the
    existing scheduled/published timestamp path; period strings such as
    `2026Q1` remain release-period metadata and are not flagged as bad dates.
  - Invalid `required_sections` tokens emit `invalid_required_section` while
    valid unique section IDs are preserved.
  - Explicit `required_macro_actual=true` still receives the default required
    sections when no explicit `required_sections` metadata is present.
  - Numeric primitive metadata values are converted to strings in the view and
    prompt payload, preserving the flat raw metadata boundary.
- Updated `src/investo/models/__init__.py`
  - Re-exported the new macro metadata view and issue contracts.
- Updated tests
  - Added direct `SourceOutcome(...)` invalid-state coverage.
  - Added macro metadata view coverage for valid explicit metadata, inferred
    FRED metadata, invalid enums, malformed dates, invalid sections, and
    numeric primitive conversion.
  - Updated public model API drift guard.
- Code review follow-up:
  - Preserved default required sections for explicit required macro actuals.
  - Prevented valid `release_period` strings from generating
    `invalid_macro_event_date` false positives.

## Validation

```bash
uv run --extra dev pytest tests/unit/models tests/unit/orchestrator/test_bundle_context.py tests/unit/briefing/test_macro_lineage.py tests/unit/briefing/test_macro_carryover.py tests/unit/sources/test_bls_macro_actuals.py tests/unit/sources/test_bea_macro_actuals.py tests/unit/sources/test_fred_economic_calendar.py
# 302 passed

uv run --extra dev ruff check src/investo/models tests/unit/models tests/unit/briefing tests/unit/sources
# All checks passed

uv run --extra dev ruff format --check src/investo/models tests/unit/models tests/unit/briefing tests/unit/sources
# 163 files already formatted

uv run --extra dev mypy src
# Success: no issues found in 217 source files
```

## TECH-DEBT

None.
