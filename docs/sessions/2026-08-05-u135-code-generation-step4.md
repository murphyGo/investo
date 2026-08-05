# Session Log: 2026-08-05 - u135 - Code Generation Step 4

## Overview

- **Date**: 2026-08-05
- **Unit**: `u135 watchpoint-current-value-and-deterministic-fallback`
- **Stage**: Code Generation
- **Step**: 4 of 7 — Pre-seal wiring, compliance filtering, quality metadata

## Work Summary

Connected the Step 2 payload and Step 3 fallback to the u144 phase-1 reader
chain. Synthesized cards are individually fail-open filtered, the final public
document remains subject to the existing compliance scan, and a typed private
count reaches the quality-history snapshot without a public marker.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Carry count through draft and seal | Avoids parsing sealed public Markdown and preserves u144 ownership. |
| Drop compliance failures per synthesized row | One closed-template defect cannot block an otherwise publishable segment. |
| Re-recognize exact deterministic subsets on rerun | Preserves diagnostics after partial drops without fuzzy matching or public metadata. |
| Re-run numeric emphasis after card creation | Makes newly resolved numbers byte-idempotent on the first reader pass. |

## Validation

- Changed-impact tests: 274 passed
- Publisher/orchestrator tests: 1,453 passed before final subset refinement
- Final affected tests: 22 passed
- Scoped Ruff, format, mypy, and diff checks: passed
- Fresh-eyes re-review: approved, no remaining finding

## TECH-DEBT Items

- None.
