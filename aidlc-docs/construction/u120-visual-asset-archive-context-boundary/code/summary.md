# u120 visual-asset-archive-context-boundary Code Summary

**Date**: 2026-06-25
**Stage**: Code Generation
**Status**: Complete

## Summary

u120 removed the hidden visuals-to-publisher archive dependency. Visual asset preparation now receives archive context through `_internal.archive_layout.ArchiveLayout`, and the orchestrator supplies that layout from the existing publish root.

## Changes

- Added required `archive_layout: ArchiveLayout` input to `prepare_segment_visual_assets`.
- Updated visual path helpers to accept optional explicit `ArchiveLayout` and default only to the repo-relative archive root for standalone callers.
- Removed lazy `investo.publisher.paths` imports from `src/investo/visuals`.
- Updated `_stage_prepare_segment_visual_assets` to construct `ArchiveLayout(ARCHIVE_ROOT)` at the orchestrator boundary.
- Added an AST guard that blocks `investo.publisher` imports anywhere under `src/investo/visuals`, including function-body lazy imports.
- Updated visual tests to pass temp archive layouts directly instead of monkeypatching publisher globals through visuals.

## Validation

```bash
uv run --extra dev pytest tests/unit/_internal/test_module_boundary.py tests/unit/_internal/test_archive_layout.py tests/unit/visuals tests/unit/orchestrator/test_run_pipeline.py
uv run --extra dev ruff check src/investo/visuals src/investo/orchestrator tests/unit/_internal tests/unit/visuals tests/unit/orchestrator
uv run --extra dev ruff format --check src/investo/visuals src/investo/orchestrator tests/unit/_internal tests/unit/visuals tests/unit/orchestrator
uv run --extra dev mypy src
```

Result: all commands passed. Focused pytest result was 267 passed.

## Notes

- Relative image links remain archive-adjacent and unchanged in rendered markdown.
- Orchestrator rollback still receives the generated asset and manifest paths.
- No visual styling, image generation policy, archive layout, source adapter, or publishing transaction behavior was intentionally changed.
- No TECH-DEBT item was added.
