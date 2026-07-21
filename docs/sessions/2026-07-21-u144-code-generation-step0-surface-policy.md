# Session: u144 Code Generation Step 0.5

## Overview

- **Date**: 2026-07-21
- **Unit**: u144 public-document-finalization-contract
- **Stage**: Code Generation
- **Step**: Step 0, checklist 5 of 6 — freeze surface disposition policy
- **Outcome**: Complete; Step 0 checklist 6 is next

## Work Summary

Added a closed publisher-private policy table for every current
`SurfaceQualityIssue.code` and every future u144 owned block kind. The table is
policy-only: `_internal.surface_quality` remains the sole detector/regex owner,
and no repair or finalization path is switched in this step.

The 13 current codes expand to one disposition for each of 16 block kinds.
Optional and conditional augmentations use the exact FD lookup: visual, chart,
carryover, and cause-map blocks omit; macro, indicator, channel-anchor, and
daily-thesis blocks replace. Watchpoints retain their dedicated replacement
policy. Protected diagnostics and unknown pairs fail closed.

An AST exhaustiveness test reads the production scanner. It fails if a
`SurfaceQualityIssue` code becomes dynamic or if a new static code is added
without updating the policy registry.

## Files Changed

- Added `src/investo/publisher/_public_document_policy.py`.
- Added `tests/unit/publisher/test_public_document_policy_u144.py`.
- Added `aidlc-docs/construction/u144-public-document-finalization-contract/code/surface-issue-disposition-baseline.md`.
- Marked Step 0 checklist 5 complete in the u144 code-generation plan.
- Updated AIDLC state/audit and added this session log.

Unrelated dirty u140, generated archive/site, settings, and worktree changes
were not edited.

## Validation

- Policy + existing surface regression scope — 36 passed
- Scoped Ruff and format checks — passed
- `uv run mypy --strict src/investo/publisher/_public_document_policy.py` — passed
- `git diff --check` — passed

## Code Review Results

Fresh-eyes review returned `APPROVE`. It confirmed all 208 code/block pairs,
the eight augmentation fallbacks versus required-watchpoint handling,
fail-closed diagnostics/unknown behavior, scanner/dynamic/registry-only
exhaustiveness guards, immutable closed types, and zero production call sites.
An intermediate formatting observation was resolved before the final review.

## TECH-DEBT

No new TECH-DEBT item was introduced. Finalizer consumption of the policy is a
later explicit u144 checklist item, not an untracked deferral.
