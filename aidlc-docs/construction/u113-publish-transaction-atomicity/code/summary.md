# u113 publish-transaction-atomicity - Code Summary

**Date**: 2026-06-24
**Status**: Complete
**Stage**: Code Generation

## Summary

Closed the publish-boundary atomicity gap for watchlist pages. The segmented
publish stage now snapshots every watchlist markdown destination before either
watchlist writer mutates files, so a later weekly publish failure restores
pre-run bytes or removes newly created watchlist pages.

## Changes

- `src/investo/publisher/watchlist_pages.py`
  - Added path-planning helpers for per-term pages, the watchlist index, and
    `daily.md`.
  - Reused the existing slug/grouping semantics so pre-write snapshots match
    writer destinations.
  - Routed per-term, index, and daily impact page writes through
    `investo._internal._io.write_atomic`.
- `src/investo/orchestrator/pipeline.py`
  - Snapshots watchlist publish paths before `update_watchlist_pages()` and
    `write_daily_impact_page()` run.
  - Preserves the writer-returned path set for git staging and index path
    aggregation.
- Tests
  - Added path-planning and atomic-writer coverage for watchlist pages.
  - Added rollback regressions for pre-existing and newly created watchlist
    pages when weekly publish fails after watchlist writes.
  - Added a regression proving watchlist atomic-write `OSError`s map to
    `PublisherIOError` and trigger publish-stage rollback.

## Validation

```bash
uv run --extra dev pytest tests/unit/publisher/test_watchlist_pages.py tests/unit/publisher/test_watchlist_daily_page.py tests/unit/orchestrator/test_run_pipeline.py
# 110 passed

uv run --extra dev pytest tests/unit/_internal/test_io.py tests/unit/publisher/test_writer.py
# 21 passed

uv run --extra dev ruff check src/investo/publisher/watchlist_pages.py src/investo/orchestrator/pipeline.py tests/unit/publisher tests/unit/orchestrator
# All checks passed

uv run --extra dev mypy src
# Success: no issues found in 211 source files
```

## TECH-DEBT

None.
