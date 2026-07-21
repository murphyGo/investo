# Session: u144 Code Generation Step 2.1

## Overview

- **Date**: 2026-07-21
- **Unit**: u144 public-document-finalization-contract
- **Stage**: Code Generation
- **Step**: Step 2, checklist 1 of 6 — phase-one publish mutations
- **Outcome**: Complete; segment-reader assembly migration is next

## Work Summary

Moved navigation, short/canonical disclaimers, summary repair, and body-used
evidence rendering out of direct publish-stage ownership and into pure phase-1
assembly collaborators. The production path preserves its previous transform
order, partial-segment navigation, evidence inputs, and terminal validator
behavior while establishing the finalizer-owned mutation boundary.

## Fresh-Eyes Correction

Review found that an identity-invariant `ValueError` could leave an already
staged visual asset behind. The pre-write assembly/gate catch now rolls back
all snapshots for ordinary exceptions and re-raises the original error. A
target-date mismatch regression creates a real SVG and proves it is removed.

## Validation

- Scoped Ruff lint/format — passed
- Strict mypy over publisher/orchestrator — 59 source files passed
- Focused phase-one tests — 6 passed
- Full publisher suite — 594 passed
- Full orchestrator suite — 374 passed
- Fresh-eyes re-review — approved

## Scope

The sealed writer and terminal finalizer remain unswitched. Unrelated
u140/generated/settings/worktree changes were left untouched.
