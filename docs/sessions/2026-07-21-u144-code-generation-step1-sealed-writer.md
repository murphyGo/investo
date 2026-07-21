# Session: u144 Code Generation Step 1.5

## Overview

- **Date**: 2026-07-21
- **Unit**: u144 public-document-finalization-contract
- **Stage**: Code Generation
- **Step**: Step 1, checklist 5 of 6 — sealed writer API
- **Outcome**: Complete; Step 1 checklist 6 is next

## Work Summary

Added and package-exported `write_finalized_document(document)`. The writer
rejects non-E5 values, validates sealed date/segment identity and exact UTF-8
digest, resolves the canonical segment path, validates both disclaimer forms,
and then reuses the existing atomic writer and cleanup behavior.

Production call sites remain on the legacy API until the planned sealed
publication switch.

## Fresh-Eyes Correction

Review found that comparing only document and notification segments allowed
both to be test-tampered to the same path-like string. The final writer checks
the canonical segment set before any segment-based path resolution. A
`../../escape` regression proves no archive directory or escaped destination is
created. Review also required explicit briefing/notification date mismatch,
valid segment mismatch, and real package re-export tests.

## Validation

- Scoped Ruff lint/format — passed
- Strict mypy for writer/package export — passed
- Writer tests — 18 passed
- Full publisher suite — 580 passed
- `git diff --check` — passed
- Fresh-eyes re-review — approved; reviewer independently reran writer tests

## Scope

No orchestrator, finalizer, segmented production writer call, derived public
consumer, asset promotion, or notifier path was switched. Unrelated
u140/generated/settings/worktree changes were left untouched.
