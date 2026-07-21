# Step 4.9 Staged Promotion and Later-I/O Rollback

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-21

`run_pipeline()` now owns one context-managed temporary artifact root around
the complete stage sequence. `GenerateStage` passes that root explicitly to
the visual and chart writers, so current file-backed supplements create no
archive destination before E6. Text-only carryover remains in memory.

Visual, carryover, and chart producers return or register their exact typed
`PublicDocumentSupplement` values. Visual and chart files return immutable
`StagedArtifact` descriptors. `_build_public_document_context()` groups those
values by segment and relies on the existing E1 referential checks: every
artifact is referenced once by a same-segment/same-kind supplement, and every
declared supplement matches its marker-backed generated input.

After the pure finalizer returns E6, `_stage_publish_segments()` validates and
promotes only `FinalizedPublicBundle.promotion_manifest`. Promotion joins the
existing pre-git snapshot transaction before sealed Markdown, index, OG,
quality, watchlist, and weekly writes. Any promotion or later covered I/O
failure restores previous bytes or removes newly created destinations. The
temporary root exits and is removed on success, E8, covered failure,
programmer error, or cancellation. Commit/push behavior remains unchanged and
is still outside the promised byte-rollback boundary. Cancellation drains an
already-started worker before the staging root is removed or the public-byte
rollback runs, so a background thread cannot write after transaction cleanup.
Atomic text/byte helpers also remove their temporary sibling after a failed
`os.replace()` while preserving the prior destination bytes.

## Regression evidence

- E8 after real visual staging leaves a pre-existing public asset byte-equal,
  creates no reader-facing destination, skips publish I/O/notification, and
  removes the observed temporary root.
- A writer failure after real E6 promotion restores the prior Markdown and
  prior visual bytes, removes every other newly promoted file, performs no git
  call, and removes the temporary root.
- Visual preparation concurrency still preserves canonical segment order and
  now proves the same staging root reaches every worker.
- Deterministic cancellation regressions directly block a visual worker and a
  post-promotion Markdown writer, then prove cancellation waits for the worker
  before staging cleanup or public-byte rollback.
- Failed atomic text and byte replacement preserves the previous destination
  and leaves no `.tmp` sibling.
- Existing manifest tests continue to cover digest/path/symlink validation,
  full-set validation before writes, and exact destination snapshots.

## Validation

- publisher, orchestrator, staging, atomic-I/O, and pipeline integration scope: 1,122
  passed;
- Ruff check/format and strict mypy over all 243 source files: passed;
- no new dependency, source, secret, network call, or persisted schema.
