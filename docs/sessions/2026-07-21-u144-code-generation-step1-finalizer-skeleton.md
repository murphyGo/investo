# Session: u144 Code Generation Step 1.2

## Overview

- **Date**: 2026-07-21
- **Unit**: u144 public-document-finalization-contract
- **Stage**: Code Generation
- **Step**: Step 1, checklist 2 of 6 — pure finalizer skeleton
- **Outcome**: Complete; Step 1 checklist 3 is next

## Work Summary

Added publisher-private segment and bundle coordinators parameterized by pure
phase handlers. The segment coordinator enforces the five-state order and
asserts that handlers cannot change segment/date or swap the original generated
briefing. Only validated-witness drafts reach the seal, and selected artifact
IDs must already exist in E1 for that segment.

The bundle coordinator validates exact generated briefing keys and target date,
emits typed `generation_absent` and `trust_blocked` outcomes in canonical order,
raises bounded E8 for zero survivors, and delegates E6 creation to the factory
that reuses exact E1 staged descriptors. It deliberately does not expose a
half-implemented public finalizer or switch production.

The bundle boundary also converts phase skips, segment/date changes, generated-
briefing identity swaps, invalid draft factories, artifact-selection errors,
and other phase-handler `ValueError` paths into bounded E8 values. Regression
tests pin phase-skip and briefing-swap issue codes and retained causes.

## Validation

- Scoped Ruff lint/format — passed
- Strict mypy for `publisher.public_document` — passed
- Lifecycle/skeleton tests — 16 passed
- Full publisher suite — 553 passed
- `git diff --check` — passed

## Code Review Results

Initial fresh-eyes review requested one blocking correction: programmer
invariants escaped the bundle boundary as raw `ValueError`. The current snapshot
converts those paths plus unexpected handler exceptions to bounded E8 and adds
phase/identity/exception regression tests. Re-review returned `APPROVE` with no
remaining blocker.

## Scope

Concrete RegionSpec indexing, public projection, repair, specialized terminal
gates, active-survivor retries, writer wiring, and production routing remain
their registered later checklist items. Unrelated dirty files were untouched.
