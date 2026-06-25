# Code Generation Plan: `u121 publish-archive-path-normalization`

**Date**: 2026-06-25
**Unit**: u121 publish-archive-path-normalization
**Stage**: Code Generation
**Status**: Complete (2026-06-25)
**Source**: Clean Code & Software Architecture guide review, 2026-06-25, plus existing `DEBT-062`.
**Estimated Effort**: ~1-2 h
**Dependencies**:
- u113 publish transaction atomicity is complete.
- DEBT-062 is the existing defect record for this exact issue.

---

## Problem Statement

`orchestrator/pipeline.py::_stage_publish_segments` branches on whether `write_briefing` returns absolute or relative archive paths. When paths are relative, it updates index pages, heatmap, OG card, quality page, and weekly digest. When tests or callers return absolute paths, those steps are skipped.

That couples production behavior to test fixture shape. The guide's clean-code smell is "shotgun/test-shape surgery": the function is carrying an incidental path representation decision instead of normalizing it at the boundary.

## Goal

Normalize archive paths once, immediately after `write_briefing`, so downstream publish side effects always receive the same relative-to-archive-root shape.

## Existing Coverage / Deduplication

- DEBT-062 already documents the issue and suggests option (a): always normalize archive paths to relative-to-archive-root.
- u113 already owns rollback snapshots and watchlist side-effect atomicity. This unit must preserve that envelope.
- `publisher.paths.archive_path` is already the canonical production path builder.

## Scope Boundary

In scope:
- Add `publisher.paths.normalize_archive_publish_path(...)` as the single path normalization helper.
- Normalize absolute paths returned by `write_briefing` to the same relative shape as production before index/heatmap/OG/quality/weekly steps.
- Remove or collapse the `if all(not path.is_absolute() ...)` branch.
- Remove test helpers that only coerce absolute paths back to relative shape, if they become unnecessary.
- Add regression tests for absolute and relative `write_briefing` returns.
- Mark DEBT-062 resolved if implementation closes it.

Out of scope:
- No archive directory layout change.
- No publish rollback redesign.
- No weekly digest behavior change.
- No mkdocs or Pages workflow change.
- No new public page.

## Stage Decision

Functional Design: skip. This is a bounded internal publish-path contract repair.

NFR Requirements: skip. No new dependency, source, secret, workflow, cost, or runtime budget.

## Fixed Contracts

### Archive Path Normalization

Add one helper with explicit behavior:

```python
def normalize_archive_publish_path(path: Path, *, archive_root: Path) -> Path:
    """Return the repo/archive-relative publish path used by downstream renderers."""
```

Rules:
- Relative input is returned unchanged after `Path(...)` normalization.
- Absolute input under `archive_root` is returned relative to `archive_root.parent`, so `/tmp/run/archive/us-equity/2026/06/2026-06-25.md` becomes `archive/us-equity/2026/06/2026-06-25.md`.
- Absolute input outside the archive root raises `PublisherIOError` or a local publish contract error rather than silently skipping side effects.
- The helper is pure and filesystem-free.

## Implementation Steps

- [x] Add failing tests showing absolute `write_briefing` paths still update index/heatmap/OG/quality/weekly paths.
- [x] Add the path normalization helper and unit tests for relative, absolute-under-root, and absolute-outside-root inputs.
- [x] Use the normalized path map in `_stage_publish_segments`.
- [x] Remove the branch that skips downstream side effects for absolute paths.
- [x] Remove obsolete test coercion helper if present.
- [x] Update `docs/TECH-DEBT.md` DEBT-062 as resolved, if and only if the branch is gone.
- [x] Write `aidlc-docs/construction/u121-publish-archive-path-normalization/code/summary.md`.

## Acceptance Criteria

1. `_stage_publish_segments` runs index, heatmap, OG, quality, and weekly side effects for both relative and absolute archive path returns.
2. Absolute paths outside the archive root fail loudly.
3. Rollback snapshots still cover all files touched by downstream side effects.
4. The production relative-path behavior remains unchanged.
5. DEBT-062 is resolved or explicitly left open with a reason.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/publisher/test_paths.py tests/unit/orchestrator/test_stage_publish.py tests/unit/orchestrator/test_run_pipeline.py tests/unit/publisher/test_site_index.py tests/unit/publisher/test_weekly_digest.py
uv run --extra dev ruff check src/investo/publisher src/investo/orchestrator tests/unit/publisher tests/unit/orchestrator
uv run --extra dev mypy src
```

## Non-Goals

- No monthly/weekly feature change.
- No archive migration.
- No git commit/push behavior change.
- No broad publish-stage decomposition.
