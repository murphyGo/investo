# Session Log: 2026-08-04 - u135 - Code Generation Step 2

## Overview

- **Date**: 2026-08-04
- **Unit**: `u135 watchpoint-current-value-and-deterministic-fallback`
- **Stage**: Code Generation
- **Step**: 2 of 7 — Current-value resolution

## Work Summary

Implemented immutable, segment-scoped deterministic current-value resolution
behind an explicit watchpoint payload. Source-shaped current fields now resolve
from exact canonical tokens or leave through the existing invalid-row path.

## Files Changed

- Modified: `src/investo/publisher/watchpoint_matrix.py`
- Modified: `tests/unit/publisher/test_watchpoint_matrix.py`
- Modified: u135 plan/state/audit records
- Created: Step 2 evidence and this session log

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Snapshot metadata into immutable scalar tuples | Prevents post-construction mutation from changing public output. |
| Gate every candidate family by segment and CFTC group | Preserves domestic quarantine and prevents cross-market resolution. |
| Prefer the longest exact matching token | Lets `BTC 펀딩` beat generic `BTC` price without fuzzy matching. |
| Keep payload optional until Step 4 wiring | Preserves existing callers while isolating Step 2 construction. |

## Code Review Results

Fresh-eyes review found one High, two Medium, and one Low issue covering segment
gates, deep immutability, render-segment identity, and numeric domains. All were
fixed with focused regressions; re-review approved with no remaining findings.

## Validation

- Watchpoint matrix tests: 55 passed
- Scoped Ruff and format: passed
- Scoped mypy: passed
- `git diff --check`: passed

## TECH-DEBT Items

- None.
