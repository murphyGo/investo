# Session Log: 2026-06-24 - u115 source-spec-registry-unification - Code Generation

## Overview

- **Date**: 2026-06-24
- **Unit**: u115 source-spec-registry-unification
- **Stage**: Code Generation

## Work Summary

Introduced `_internal.source_specs` as the canonical production source metadata
registry and derived tier, market-window, and segment membership compatibility
views from it.

## Files Changed

- Created:
  - `src/investo/_internal/source_specs.py`
  - `tests/unit/sources/test_source_specs.py`
  - `aidlc-docs/construction/u115-source-spec-registry-unification/code/summary.md`
- Modified:
  - `src/investo/sources/tiers.py`
  - `src/investo/sources/aggregator.py`
  - `src/investo/briefing/segments.py`
  - `tests/unit/sources/test_plugin_contract.py`
  - AIDLC plan/state/audit files.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Put descriptors under `_internal` | Both `sources` and `briefing` consume source metadata, so the descriptor must be a shared leaf. |
| Keep explicit adapter imports | u1 plugin contract remains unchanged; no dynamic discovery or DI framework. |
| Preserve special routing behavior in `briefing.segments` | CFTC and `stooq-price` routing decisions are behavior, not descriptor mechanics. |

## Validation

- Code review found no Critical/High issues.
- Review Medium/Low follow-ups were addressed before commit:
  - Added subprocess discoverability coverage for `import investo.sources`.
  - Added a single-source assertion for the CFTC contract-group routing source.
- `uv run --extra dev pytest ...` focused u115 source/segment set - 175 passed
- `uv run --extra dev ruff check ...` - passed
- `uv run --extra dev mypy src` - passed

## TECH-DEBT

None.
