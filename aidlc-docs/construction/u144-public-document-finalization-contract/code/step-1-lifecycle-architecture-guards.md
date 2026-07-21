# Step 1.6 Lifecycle and Architecture Guards

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

Step 1 closes with executable guards over the lifecycle and sealed boundary:

- direct or handler-mediated phase skips fail with bounded phase-transition
  invariants;
- digest, embedded briefing date, notification date, notification segment, and
  non-canonical segment mismatches leave public destinations untouched;
- `write_finalized_document()` rejects publisher-private E2 drafts;
- production E2 allocation remains single-owned by `_construct_draft`, E5
  allocation by `_seal_document`, and the seal call by the segment finalizer;
- before the planned Step 5 switch there are zero production calls to the
  sealed writer.

The AST guard resolves canonical symbols through direct imports, renamed
symbols, module aliases, `from package import module` aliases, and publisher
relative imports. Synthetic regressions prove those paths cannot bypass the
guard and that unrelated local same-name symbols do not create false positives.

The allowlist is intentionally phase-specific: Step 5 must update the sealed
writer call expectation when the single default production call lands.
