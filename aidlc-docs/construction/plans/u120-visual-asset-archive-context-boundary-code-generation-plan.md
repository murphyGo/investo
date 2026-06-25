# Code Generation Plan: `u120 visual-asset-archive-context-boundary`

**Date**: 2026-06-25
**Unit**: u120 visual-asset-archive-context-boundary
**Stage**: Code Generation
**Status**: Complete (2026-06-25)
**Source**: Clean Code & Software Architecture guide review, 2026-06-25. Focus: hidden side effects, explicit dependencies, and ports/adapters.
**Estimated Effort**: ~2-4 h
**Dependencies**:
- u78 visuals/publisher boundary guard is complete.
- u86 curated context assets are complete; preserve curated selection behavior.
- u113 publish transaction atomicity is complete; do not weaken rollback path coverage.

---

## Problem Statement

`visuals/assets.py::prepare_segment_visual_assets` computes the archive-adjacent markdown path by lazily importing `investo.publisher.paths` inside the function and reading `ARCHIVE_ROOT`.

That keeps the top-level AST boundary green, but the dependency is still hidden. A visual asset generator needs an archive target path; it should not know that the publisher stores that path in `publisher.paths.ARCHIVE_ROOT`. The guide calls this out as a dependency inversion and information-hiding problem: the volatile storage decision leaks into a sibling adapter.

## Goal

Make the visual asset target explicit and inward-owned:

- `prepare_segment_visual_assets` receives an `_internal.archive_layout.ArchiveLayout` from its caller.
- The visual package computes the per-segment markdown path from that layout, target date, and segment, without importing publisher code.
- Production orchestrator/publisher wiring supplies the current archive root.
- `visuals` has zero imports of `publisher`, including lazy/function-body imports.

## Existing Coverage / Deduplication

- `_internal.archive_layout.ArchiveLayout` already exists and was introduced to dissolve the previous `visuals -> publisher` edge.
- u113 already snapshots visual side-effect paths before publish gates; keep that rollback contract.
- u86 already defines curated asset selection and no-runtime-scraping constraints; this unit changes only path ownership.

## Scope Boundary

In scope:
- Add a required keyword-only `archive_layout: ArchiveLayout` parameter to `prepare_segment_visual_assets`.
- Update orchestrator visual preparation call sites to pass the target explicitly.
- Remove the lazy `import investo.publisher.paths` from `visuals/assets.py`.
- Add a boundary test that walks all AST imports, not only module-level imports, and blocks `visuals -> publisher`.
- Preserve asset relative links, sidecar paths, provenance manifests, curated asset copies, and rollback path lists.

Out of scope:
- No visual redesign.
- No SVG/PNG rendering change.
- No archive layout change.
- No new image dependency.
- No change to OpenAI image policy or external image scraping flags.

## Stage Decision

Functional Design: skip. This is a hidden-dependency cleanup over an existing visual/publish path.

NFR Requirements: skip. No new dependency, source, secret, cost, workflow, or runtime budget.

## Fixed Contracts

### Visual Asset Target

```python
def prepare_segment_visual_assets(..., archive_layout: ArchiveLayout) -> PreparedVisualAssets:
    markdown_path = archive_layout.briefing_path(target_date, segment)
```

Rules:
- `ArchiveLayout` from `investo._internal.archive_layout` is the canonical target shape.
- Production callers may read `publisher.paths.ARCHIVE_ROOT`, but only outside the `visuals` package.
- Tests that use temp archive roots must pass the explicit target rather than monkeypatching publisher globals through visuals.

## Implementation Steps

- [x] Add an AST test that detects any `investo.publisher` import anywhere inside `src/investo/visuals`.
- [x] Update `prepare_segment_visual_assets` signature with an explicit target parameter.
- [x] Remove the function-body import of `investo.publisher.paths`.
- [x] Update orchestrator call sites that prepare segment visual assets.
- [x] Update visual unit tests to pass the target explicitly.
- [x] Verify generated markdown still uses the same relative image links.
- [x] Write `aidlc-docs/construction/u120-visual-asset-archive-context-boundary/code/summary.md`.

## Acceptance Criteria

1. `src/investo/visuals` contains no `investo.publisher` imports at module level or function-body level.
2. `prepare_segment_visual_assets` can be tested with a temp target without monkeypatching publisher globals.
3. Production asset paths remain archive-adjacent and rollback-visible to the publish stage.
4. Existing curated, external, AI, data-confidence, market-snapshot, price-snapshot, and watchlist visual asset behavior is unchanged.
5. `tests/unit/_internal/test_module_boundary.py` pins the no-lazy-import boundary.

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/_internal/test_module_boundary.py tests/unit/visuals tests/unit/orchestrator/test_stage_generate.py tests/unit/orchestrator/test_run_pipeline.py
uv run --extra dev ruff check src/investo/visuals src/investo/orchestrator tests/unit/_internal tests/unit/visuals tests/unit/orchestrator
uv run --extra dev mypy src
```

## Non-Goals

- No visual styling change.
- No image generation change.
- No publisher rollback redesign.
- No archive backfill.
