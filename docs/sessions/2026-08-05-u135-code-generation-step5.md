# Session Log: 2026-08-05 - u135 - Code Generation Step 5

## Overview

- **Date**: 2026-08-05
- **Unit**: `u135 watchpoint-current-value-and-deterministic-fallback`
- **Stage**: Code Generation
- **Step**: 5 of 7 — Exact incident regressions

## Work Summary

Pinned the two production failure families and the empty-payload terminal state
in a dedicated u135 fixture. The crypto case forced a source-aware price tie
correction; the US case verifies range/CFTC fallback order and typed count.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Semantic indicators outrank price candidates | Prevents funding/OI cards from receiving a BTC price across separators. |
| Source cue breaks equivalent asset-token ties | Lets a CoinGecko-labelled price card use its named snapshot instead of the anchor. |
| Mark the US low-distance field synthetic | The public archive lacks that raw field, so the fixture must not imply a full payload replay. |

## Validation

- Focused tests: 68 passed
- Publisher tests: 1,022 passed
- JSON, Ruff, format, mypy, and diff checks: passed
- Fresh-eyes re-review: approved after High finding closure

## TECH-DEBT Items

- None.
