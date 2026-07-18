# u139 Code Generation Step 4 — Private Renderer and Manual Runner

**Date**: 2026-07-18
**Status**: Complete
**Plan**: `aidlc-docs/construction/plans/u139-sector-dashboard-private-core-radar-validation-code-generation-plan.md`

## Delivered Surface

- `src/investo/sector_dashboard/private_render.py` creates canonical
  `snapshot.json` and `report.md` projections with one shared SHA-256 snapshot ID,
  fixed private/NAV labels, coverage-aware C1-C8 sections, bounded diagnostics, and
  closed forbidden-field/claim checks.
- The same module implements an exclusive owner-only, recoverable two-file
  transaction. Output, prepared, and backup directories are pinned by directory
  descriptors; regular files and the transaction marker require exact owner modes,
  stable identities, and single-link invariants.
- `scripts/validate_sector_dashboard_private.py` requires explicit absolute manifest
  and output paths, acquires/recoveries the output session before reading private
  input, supports explicit `--replace`, and emits only bounded one-line status.
- `tests/unit/sector_dashboard/test_private_render.py` and
  `test_private_cli.py` cover deterministic rendering, all coverage states,
  serialization properties, privacy/path policy, pair replacement, phase recovery,
  CLI exit codes, and negative public integration.

## Transaction and Privacy Contracts

1. The marker is an append-only newline-committed phase journal held under one
   non-blocking `flock`; an incomplete trailing record replays from the last complete
   phase without replacing the locked inode.
2. Candidate and backup snapshot IDs plus exact report digests are durable journal
   anchors. Canonical-but-wrong current, prepared, or backup pairs are rejected and
   preserved rather than adopted or deleted.
3. Every phase has an explicit current-pair invariant. Known two-file intermediate
   states are accepted only when each remaining component byte-matches the anchored
   candidate or backup pair.
4. After the durable `cleaning_up` commit point, validated partial/empty cleanup is
   recoverable. Cleanup I/O failure returns the already committed result while
   preserving the marker for the next run; corrupt evidence still fails closed.
5. Output and managed-directory operations use pinned `dir_fd` targets, so a path
   rename/symlink swap cannot redirect private bytes into the repository. Marker and
   artifact hardlinks, unsafe modes, wrong owners, path overlaps, and public roots are
   rejected.
6. At-rest reads revalidate canonical snapshot bytes and the exact deterministic
   report, not only labels or the embedded marker. Raw row/cell/path values and open
   rank-reason vocabulary cannot enter either projection or an error line.

## Review and Verification

Fresh-eyes review iteratively reproduced and closed transaction-journal corruption,
managed/output path swaps, hardlinked markers, canonical evidence substitution,
phase-current disagreement, interrupted directory creation/cleanup, descriptor
lifecycle, raw exception leakage, and reverse public integration gaps. The final
review returned `APPROVED` with no remaining Critical, High, or Medium finding.

Local validation:

- focused Step 4 renderer/CLI tests — 61 passed;
- cumulative `tests/unit/sector_dashboard` — 126 passed;
- scoped and repository-wide Ruff check/format — passed;
- `mypy src/` — passed for 232 source files;
- `git diff --check` — passed.

The Step 4 regression suite scans `mkdocs.yml`, public workflows, source registry,
orchestrator, publisher, notifier/Telegram, briefing pipeline, and the tracked public
diff for forbidden reverse integration or private sentinel leakage.

## Remaining Step

Step 5 owns the full pytest/no-paid/mkdocs gates, synthetic repeat-run evidence,
operator-local smoke result, acceptance matrix, and the final public-artifact diff
audit. Step 4 adds no source adapter, scheduled job, Pages navigation, Telegram path,
or u140 public-source authorization.
