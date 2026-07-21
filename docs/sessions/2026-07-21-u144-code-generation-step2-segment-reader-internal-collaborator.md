# Session: u144 Code Generation Step 2.2

## Overview

- **Date**: 2026-07-21
- **Unit**: u144 public-document-finalization-contract
- **Stage**: Code Generation
- **Step**: Step 2, checklist 2 of 6 — segment-reader internal collaborator
- **Outcome**: Complete; supplement routing is next

## Work Summary

Moved the default production dependency from `segment_reader_format` to the
`public_document` assembly boundary. The reader module now owns only its
existing text transforms and surface repair; surface scan/error policy is
outside it. A compatibility observer preserves current blocking and partial
publication behavior until the Step 4 terminal validator replaces it.

## Fresh-Eyes Correction

The first implementation scanned the assembled batch after every segment had
run. That allowed a later compliance/numeric failure to outrank an earlier
surface blocker. The final callback executes immediately after each segment's
repair and retains the old pre/post warning and block order. A direct
two-segment precedence regression pins that behavior.

## Validation

- Scoped Ruff lint/format — passed
- Strict mypy over publisher/orchestrator — 59 source files passed
- Focused tests — 19 passed
- Publisher suite — 597 passed
- Orchestrator suite — 374 passed
- Reader/bundle integration — 14 passed
- Boundary/public-document tests — 28 passed
- Fresh-eyes re-review — approved

## Scope

No blocker or partial-publication contract was weakened. The sealed writer and
terminal finalizer remain unswitched, and unrelated worktree changes were left
untouched.
