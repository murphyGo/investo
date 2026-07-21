# Session: u144 Code Generation Step 1.1

## Overview

- **Date**: 2026-07-21
- **Unit**: u144 public-document-finalization-contract
- **Stage**: Code Generation
- **Step**: Step 1, checklist 1 of 6 — lifecycle types and seal factory
- **Outcome**: Complete; Step 1 checklist 2 is next

## Work Summary

Added the publisher-owned E1-E8 immutable contract surface and a pure,
module-private E5 seal factory. Context construction freezes mappings and checks
canonical segment order, known absences, timezone-aware entity observation,
coverage identity, ordered supplements, marker-free bodies, globally unique
artifact IDs/public paths, and exact one-supplement artifact references.

The seal factory accepts only a draft created by the ordered private transition
path with its terminal-validation witness, produces a final compatibility
`Briefing` whose Markdown is the layout bytes, and hashes those exact UTF-8
bytes. Public E2/E5 construction is disabled. E6 is also factory-only and
derives the exact staged-artifact descriptor objects from E1 rather than
accepting a caller-supplied manifest. E8 keeps the typed cause without including
its text in the bounded public error message.

Context snapshotting defensively copies and freezes `NormalizedItem.raw_metadata`
plus `BundleContext.segments` and per-segment thesis lines, closing nested
mutable-container leaks in otherwise frozen models.

The minimal notification DTO shell was added as an E2/E5 type dependency. Its
validation/export and the typed watchpoint result remain the explicit fourth
Step 1 checklist item. No production finalizer or writer call site was switched.

## Validation

- Scoped Ruff lint/format — passed
- Strict mypy for the two new source modules — passed
- Publisher unit suite — 544 passed
- `git diff --check` — passed

## Code Review Results

Fresh-eyes re-review returned `APPROVE`. The initial review found and the final
snapshot closes three contract holes: direct fake-validated draft sealing,
same-ID staged-descriptor substitution in E6, and mutable dicts nested inside
frozen E1 models. The reviewer confirmed transition-witness enforcement, exact
E1 descriptor reuse, defensive nested snapshots, bounded exports, and no
production call-site switch.

## Scope

Unrelated u140, generated archive/site, settings, and worktree changes were not
edited. No network, filesystem, environment, clock, or subprocess operation was
added to the lifecycle module.
