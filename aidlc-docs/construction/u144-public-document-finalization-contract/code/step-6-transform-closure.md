# Step 6.2 Assembly Transform Closure

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-22

The complete documented phase-one producer call graph is now represented by an
explicit test matrix. Each producer boundary is paired with every canonical
forbidden public phrase plus concrete samples for each pattern-only form. The
matrix injects that output into a reader-visible owned region, then runs the
production terminal sequence:

1. `project_public_markdown()`;
2. `repair_surface_artifacts()`; and
3. `PublicDocumentLayout.reindex()`.

The independent read-only `find_reader_visible_public_label_leaks()` traversal
must return no evidence for every pair. The matrix covers generated body,
supplements, anchor/structure transforms, shared and segment enrichments,
compliance/watchpoints, navigation/disclaimers, viewport/summary repair, and
body-used accounting. Protected diagnostics, exact disclaimer bytes, and
fenced code keep their existing typed policies and are not used as artificial
injection surfaces.

## Validation

- terminal projection test module: 291 passed;
- 18 producer boundaries by 14 forbidden token samples: 252 closure cases;
- scoped Ruff and format check: passed.
