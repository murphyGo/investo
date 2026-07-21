# Session: u144 Code Generation Step 1.4

## Overview

- **Date**: 2026-07-21
- **Unit**: u144 public-document-finalization-contract
- **Stage**: Code Generation
- **Step**: Step 1, checklist 4 of 6 — notification/watchpoint contracts
- **Outcome**: Complete; Step 1 checklist 5 is next

## Work Summary

Completed and exported the immutable `PublicNotificationSummary` compatibility
DTO with closed segment, date, coverage, label, conclusion, and optional
watchlist validation. Added publisher-private bounded issue codes for the later
terminal summary extractor.

Added `WatchpointRenderResult` with exact rendered/limited invariants and a new
typed pure renderer. The legacy string renderer delegates without changing its
empty-input behavior, and no production call site was switched.

## Fresh-Eyes Corrections

Review rejected substring-based same-day idempotency because malformed or
forged card headings could claim rendered availability. The final implementation
recognizes only a complete canonical card grammar, applies the normal usability
predicate, enforces the six-card bound, and byte-compares every parsed card with
canonical re-rendering. Mixed limited/card bodies, unusable complete cards,
raw URLs, and trace tokens all fail closed to a typed limited result. Review
also required the publisher summary error to reject arbitrary issue codes.

## Validation

- Scoped Ruff lint/format — passed
- Strict mypy for models and publisher — passed (69 files)
- Focused notification/watchpoint tests — 83 passed
- Full models and publisher suites — 821 passed
- `git diff --check` — passed
- Fresh-eyes re-review — approved

## Scope

No production finalizer, notifier, writer, orchestrator, or watchpoint caller
was switched. Unrelated u140/generated/settings/worktree changes were left
untouched.
