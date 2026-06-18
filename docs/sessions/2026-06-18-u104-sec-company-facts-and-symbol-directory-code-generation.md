# Session Log: 2026-06-18 - u104 - Code Generation

## Overview

- **Date**: 2026-06-18
- **Unit**: u104 sec-company-facts-and-symbol-directory
- **Stage**: Code Generation
- **Step**: Steps 1-9

## Work Summary

Added bounded official SEC company facts and Nasdaq Trader symbol-directory adapters with fixtures, registration, and focused tests.

## Files Changed

- Created: `aidlc-docs/construction/u104-sec-company-facts-and-symbol-directory/code/summary.md`
- Created: `docs/sessions/2026-06-18-u104-sec-company-facts-and-symbol-directory-code-generation.md`
- Created: `src/investo/sources/sec_company_facts.py`
- Created: `src/investo/sources/nasdaq_symbol_directory.py`
- Created: `tests/unit/sources/test_sec_company_facts.py`
- Created: `tests/unit/sources/test_nasdaq_symbol_directory.py`
- Created: `tests/unit/sources/fixtures/api/sec-company-facts/`
- Created: `tests/unit/sources/fixtures/api/nasdaq-symbol-directory/`
- Modified: `aidlc-docs/audit.md`
- Modified: `aidlc-docs/aidlc-state.md`
- Modified: `aidlc-docs/construction/plans/u104-sec-company-facts-and-symbol-directory-code-generation-plan.md`
- Modified: `src/investo/briefing/segments.py`
- Modified: `src/investo/sources/__init__.py`
- Modified: `src/investo/sources/aggregator.py`
- Modified: `src/investo/sources/tiers.py`
- Modified: `tests/unit/briefing/test_segments.py`
- Modified: `tests/unit/sources/test_plugin_contract.py`

## Key Decisions

| Decision | Rationale |
| --- | --- |
| Emit one compact item per SEC company | Keeps Stage 2 candidate volume bounded and avoids raw filing excerpts. |
| Cap SEC companies at 8 | Matches current watchlist scale and prevents accidental bulk SEC pulls. |
| Use a fixed XBRL concept allow-list | Avoids broad taxonomy ingestion while covering first-slice high-signal facts. |
| Fetch only two Nasdaq directory files | Official, no-key, and bounded request count. |
| Emit static reference items as `macro` | Prevents company/listing metadata from satisfying required `news` coverage. |
| Space SEC requests and isolate company failures | Keeps bounded SEC access below bursty request rates and preserves good company items. |
| Add an adapter-level SEC budget | Prevents the sequential SEC company loop from dominating source collection wall-clock. |
| Exclude static reference sources from item thresholds | Prevents company/listing metadata from promoting sparse live coverage to normal. |

## Code Review Results

| Category | Status |
| --- | --- |
| Correctness | Blocking review issues fixed: static reference items now emit as `macro`. |
| Safety | Blocking review issues fixed: SEC requests are spaced, budgeted, and still no paid/API-key path. |
| Reliability | Per-company SEC failures are isolated unless every configured company fails. |
| Maintainability | Focused source adapters and explicit segment/source contract tests retained. |
| Test Coverage | Added category, request-spacing, adapter-budget, partial-failure, and coverage-mask regressions. |

## Potential Risks

- The SEC adapter intentionally emits compact current context rather than a full fact-history model. Future units can add richer fact-context rendering if a specific reader surface needs it.

## TECH-DEBT Items

- None added.

## Validation

- `uv run pytest tests/unit/sources/test_sec_company_facts.py tests/unit/sources/test_nasdaq_symbol_directory.py tests/unit/sources/test_plugin_contract.py -q` -> 25 passed
- `uv run pytest tests/unit/briefing/test_segments*.py -q` -> 85 passed
- `uv run pytest tests/unit/briefing tests/unit/publisher -q -k 'fact or watchlist or source'` -> 169 passed, 1154 deselected
- `uv run ruff check src/investo/sources tests/unit/sources tests/unit/briefing/test_segments.py src/investo/briefing/segments.py` -> clean
- `uv run mypy --strict src/investo/sources src/investo/briefing` -> clean over 98 source files
- `uv run python scripts/check_no_paid_apis.py` -> clean
