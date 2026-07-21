# Session: u144 Code Generation Step 1.3

## Overview

- **Date**: 2026-07-21
- **Unit**: u144 public-document-finalization-contract
- **Stage**: Code Generation
- **Step**: Step 1, checklist 3 of 6 — canonical region index
- **Outcome**: Complete; Step 1 checklist 4 is next

## Work Summary

Implemented the pure `RegionSpec`/`PublicRegionExpectation` boundary and full
newline-preserving layout reindex. Exact H1, five numbered sections,
watchpoints, diagnostics, canonical/short disclaimers, segment-specific anchor
tables, active conditional producers, typed supplement markers, and residual
first-viewport spans now form one deterministic partition.

Replacement splices only `content_start:content_end`, preserves wrappers, and
fully reindexes. Marker omission preserves an empty paired shell. Tests pin
empty/non-empty anchors, equity/crypto headers, condition mismatches, marker
pairing, carryover heading ownership, duplicated evidence in two marker blocks,
stable replacement IDs, omission, duplicate/missing headings, and unexpected
circled-number H2s.

## Fresh-Eyes Design Correction

Initial review found that current visual/chart producers place assets directly
below section/watchpoint H2s. The original FD simultaneously required one
contiguous region per H2 body, non-overlap with higher-priority marker regions,
and ownership of prose after the marker; those constraints cannot be represented
by the E3 single-span DTO. The implementation preserves current reader layout
and minimally refines FD rows 14-15 with deterministic continuation IDs. It
does not allow overlap or introduce a multi-span entity.

The same review found that checking only circled digits 1-7 would admit `⑧` or
`⓪-C`. Detection now uses the Unicode circled digit/number class and permits
only the exact canonical allowlist.

## Validation

- Scoped Ruff lint/format — passed
- Strict mypy for all publisher modules — passed (47 files)
- Focused lifecycle/region tests — 28 passed
- Full publisher suite — 565 passed
- A committed real domestic briefing shape was reindexed successfully with
  macro/channel/cause/thesis ordering

## Scope

No production finalizer, writer, asset promotion, phase algorithm, or notifier
path was switched. Unrelated u140/generated/settings/worktree changes were left
untouched.
