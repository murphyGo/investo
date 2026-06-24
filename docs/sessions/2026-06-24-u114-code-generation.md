# Session Log: 2026-06-24 - u114 shared-domain-contract-boundary - Code Generation

## Overview

- **Date**: 2026-06-24
- **Unit**: u114 shared-domain-contract-boundary
- **Stage**: Code Generation

## Work Summary

Promoted shared domain contracts out of `briefing` and into `models` or
`_internal`. The behavior modules in `briefing` remain compatibility owners
where needed, but non-briefing units now import shared vocabulary from the
foundation layer.

## Files Changed

- Created:
  - `src/investo/models/time_state.py`
  - `src/investo/models/market_anchor.py`
  - `src/investo/models/watchlist.py`
  - `src/investo/_internal/briefing_extract.py`
  - `src/investo/_internal/watchlist_matching.py`
  - `tests/unit/models/test_shared_domain_contracts.py`
  - `aidlc-docs/construction/u114-shared-domain-contract-boundary/code/summary.md`
- Modified:
  - `briefing`, `models`, `publisher`, `notifier`, `visuals`, and `sources`
    import paths for shared vocabulary.
  - Boundary and compatibility tests.
  - AIDLC plan/state/audit files.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Keep behavior in `briefing` | Segment routing, watchlist matching/grouping, and summary validation are behavior owners, not pure DTOs. |
| Use compatibility re-exports | Existing imports continue working while new code has a clean canonical owner. |
| Move private matcher primitive to `_internal` | `visuals.curated` needed the pure matcher without depending on `briefing.watchlist`. |
| Allow `briefing.summary_quality` behavior import | Replay validation uses briefing-owned validation behavior; only prefix/extract vocabulary moved. |

## Validation

- Code review found no Critical/High issues.
- Review Medium/Low follow-ups were addressed before commit:
  - `briefing.extract` now re-exports the prefix literals for compatibility.
  - `investo.models` top-level API now re-exports the new canonical model
    contracts.
  - Module-boundary AST tests now catch `from investo.briefing import segments`
    style package-level bypasses.
- `uv run --extra dev pytest ...` targeted compatibility/boundary set - 164 passed
- `uv run --extra dev pytest ...` extended u114 validation set - 1188 passed
- `uv run --extra dev ruff check src/investo ...` - passed
- `uv run --extra dev mypy src` - passed

## TECH-DEBT

None.
