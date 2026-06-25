# u121 publish-archive-path-normalization Code Summary

**Date**: 2026-06-25
**Stage**: Code Generation
**Status**: Complete

## Summary

u121 fixed the publish-stage absolute/relative archive path split. The publish stage now normalizes archive paths once after `write_briefing`, then always runs downstream side effects through the same path shape.

## Changes

- Added `publisher.paths.normalize_archive_publish_path(path, *, archive_root)`.
- Normalized every `_stage_publish_segments` `write_briefing` return before storing it in the segment archive-path map.
- Converted absolute paths under the active archive root to repo/archive-relative paths.
- Raised `PublisherIOError` for absolute paths outside the active archive root.
- Removed the `all(not path.is_absolute())` publish side-effect branch.
- Updated publish side-effect tests to return absolute archive paths and exercise normalization directly.
- Moved DEBT-062 to Resolved in `docs/TECH-DEBT.md`.

## Validation

```bash
uv run --extra dev pytest tests/unit/publisher/test_paths.py tests/unit/orchestrator/test_stage_publish.py tests/unit/orchestrator/test_run_pipeline.py tests/unit/publisher/test_site_index.py tests/unit/publisher/test_weekly_digest.py
uv run --extra dev ruff check src/investo/publisher src/investo/orchestrator tests/unit/publisher tests/unit/orchestrator
uv run --extra dev ruff format --check src/investo/publisher src/investo/orchestrator tests/unit/publisher tests/unit/orchestrator
uv run --extra dev mypy src
```

Result: all commands passed. Focused pytest result was 134 passed.

## Notes

- Production relative archive paths remain unchanged.
- Absolute test/caller paths under the archive root now still trigger index, heatmap, OG, quality, forecast, watchlist, monthly, and weekly side effects.
- Rollback snapshots continue to cover downstream side-effect paths inside the same publish try block.
- No TECH-DEBT item was added; DEBT-062 was resolved.
