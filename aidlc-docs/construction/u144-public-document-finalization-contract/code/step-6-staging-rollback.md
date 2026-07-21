# Step 6.7 Staging and Rollback

**Unit**: u144 public-document-finalization-contract
**Completed**: 2026-07-22

The staging boundary now has end-to-end failure coverage on both sides of E6:

- a finalization E8 leaves every non-metadata public destination byte-identical,
  performs no writer/git call, and removes the run-owned staging root; and
- an injected failure on the second real artifact promotion proves the first
  promotion is rolled back, newly created paths are removed, existing and
  unrelated bytes are restored exactly, publication remains uncommitted, git
  is not called, and the staging root is removed.

The promotion test patches only the atomic byte writer inside the real
`promote_finalized_bundle_artifacts()` path. It snapshots the entire public
archive file map before the run and compares the exact relative-path/byte map
after the orchestrator's existing rollback completes.

## Validation

- staged-artifact unit tests plus E8/promotion integration cases: 7 passed;
- scoped Ruff and format check: passed.
