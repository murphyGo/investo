# Step 3.4 Protected Diagnostic and Metadata Boundary

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

The terminal projection's existing region-policy behavior is now pinned as an
explicit boundary contract:

- the exact `diagnostics:quality` region keeps its raw operator labels byte for
  byte;
- an arbitrary `<details>` block inside a reader-visible owned region is not a
  diagnostic exemption and its identical raw label crosses the shared safe
  wording projection;
- E2 keeps the original `source_briefing` identity, structured fields, and
  original generated Markdown as private metadata; and
- the separately owned `layout.markdown` advances with projected public bytes.

The last distinction enforces E2 invariant I9: once the draft exists, the
original `source_briefing.rendered_markdown` is evidence/metadata and is not a
publishable public view. Step 5 will ensure all default consumers use sealed
layout bytes rather than those generated fields.

This slice adds characterization rather than a second wording or scanning
implementation. Step 3.5 remains the separate read-only terminal traversal
over reader-visible owned regions.

## Validation

- projection, surface-quality, and lifecycle boundary set: 67 passed;
- Ruff check and format check: passed;
- fresh-eyes review: 58 focused tests plus Ruff/format/mypy/scoped diff check,
  approved with no blocker.
