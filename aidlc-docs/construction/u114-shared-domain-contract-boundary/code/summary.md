# u114 shared-domain-contract-boundary - Code Summary

**Date**: 2026-06-24
**Status**: Complete
**Stage**: Code Generation

## Summary

Closed the clean-architecture boundary drift where `briefing` had become the
shared vocabulary package. Pure shared contracts now live under `models` or
`_internal`, while behavior-heavy briefing modules keep ownership of routing,
matching, grouping, and validation behavior through compatibility re-exports.

## Changes

- Added canonical shared owners:
  - `src/investo/models/time_state.py`
  - `src/investo/models/market_anchor.py`
  - `src/investo/models/watchlist.py`
  - `src/investo/_internal/briefing_extract.py`
  - `src/investo/_internal/watchlist_matching.py`
- Extended `src/investo/models/segments.py` with segment constants, labels,
  coverage status/reason literals, and `SegmentCoverage`.
- Moved `CORE_FACT_METADATA_PREFIX` and `core_fact_metadata_key()` into
  `src/investo/models/core_fact.py`; `sources._core_fact_map` now keeps only
  ticker-to-core-fact mapping behavior plus compatibility re-exports.
- Replaced shared-vocabulary imports in `publisher`, `notifier`, `visuals`,
  `sources`, and `models` with imports from `models` or `_internal`.
- Kept legacy `briefing.*` imports valid:
- `briefing.market_anchor` and `briefing.extract` are compatibility
    re-export modules.
  - `briefing.time_state`, `briefing.segments`, `briefing.watchlist`, and
    `briefing.watchlist_impact` import canonical DTOs while keeping behavior.
  - `briefing.summary_quality` imports canonical first-viewport prefixes from
    `_internal.briefing_extract`.
- Added AST boundary tests for `models -> briefing` and sibling-unit
  `-> briefing` shared-vocabulary imports.
- Added compatibility tests proving old import paths resolve to the same
  canonical classes/functions.
- Code review follow-up:
  - Restored prefix-literal compatibility from `briefing.extract`.
  - Re-exported the new canonical model contracts from `investo.models`.
  - Strengthened the AST boundary test against package-level briefing imports.

## Validation

```bash
uv run --extra dev pytest tests/unit/_internal/test_module_boundary.py tests/unit/models/test_shared_domain_contracts.py tests/unit/briefing/test_time_state.py tests/unit/briefing/test_anchor_label.py tests/unit/briefing/test_market_anchor.py tests/unit/briefing/test_extract.py tests/unit/briefing/test_summary_quality.py tests/unit/briefing/test_watchlist.py tests/unit/briefing/test_watchlist_impact.py
# 164 passed

uv run --extra dev pytest tests/unit/models tests/unit/briefing/test_segments.py tests/unit/briefing/test_segments_severity.py tests/unit/briefing/test_anchor_label.py tests/unit/briefing/test_numeric_verify.py tests/unit/briefing/test_watchlist.py tests/unit/briefing/test_extract.py tests/unit/briefing/test_summary_quality.py tests/unit/publisher tests/unit/notifier tests/unit/visuals tests/unit/sources/test_stooq_price.py tests/unit/sources/test_yfinance.py
# 1188 passed

uv run --extra dev ruff check src/investo tests/unit/models tests/unit/_internal/test_module_boundary.py tests/unit/briefing tests/unit/publisher tests/unit/notifier tests/unit/visuals tests/unit/sources
# All checks passed

uv run --extra dev mypy src
# Success: no issues found in 216 source files
```

## TECH-DEBT

None.
