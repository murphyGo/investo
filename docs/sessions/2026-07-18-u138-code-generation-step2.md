# Session Log: 2026-07-18 - u138 - Code Generation Step 2

## Overview

- **Date**: 2026-07-18
- **Unit**: u138 price-source-endpoint-lifecycle-repair
- **Stage**: Code Generation
- **Step**: 2 of 6 - Consolidate Yahoo chart handling

## Work Summary

Consolidated Yahoo chart requests and parsing behind one query2/1y/1d module,
then moved both snapshot and history collection onto that contract. Snapshot
collection now completes the 13-ticker critical phase before starting the
14-ticker enrichment phase, skips enrichment when every critical request
fails, and preserves critical results when enrichment requests fail.

## Files Changed

- Created: `src/investo/sources/_yahoo_chart.py`
- Modified: `src/investo/sources/yfinance.py`
- Modified: `src/investo/sources/yfinance_history.py`
- Modified: `tests/unit/sources/test_yfinance.py`
- Modified: `tests/unit/sources/test_yfinance_history.py`
- Modified: u138 plan and `aidlc-docs/aidlc-state.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Return `YahooChartData` internally while retaining `fetch_chart_rows()` | Snapshot needs `chartPreviousClose` for one-row compatibility; history callers retain their fixed row interface |
| Run critical and enrichment as sequential phases under the existing concurrency limit | Critical coverage cannot be delayed or displaced by best-effort enrichment traffic |
| Remove enrichment tickers already present in the critical basket | Environment overrides cannot create duplicate requests or duplicate public items |
| Mark direct snapshot items with `provenance=query2-snapshot` | Later same-run fallback reconciliation can distinguish direct and derived outcomes truthfully |
| Keep the public history wrapper and parser functions | Existing callers and fixture tests retain their stable API while request/parsing logic is single-homed |

## Code Review Results

| Category | Status |
|----------|--------|
| Correctness | Pass |
| Safety | Pass |
| Reliability | Pass |
| Maintainability | Pass |
| Test Coverage | Pass |

## Validation

- Focused Yahoo/history/lifecycle/market-anchor/stage-context suite: 93 passed
- Registry/plugin-focused suite: 85 passed
- Full source suite: 850 passed, with one unrelated SEC timing test failing once and passing on immediate isolated rerun
- Scoped Ruff check and Ruff format check: passed
- `uv run mypy src`: passed for 227 source files
- Runtime `query1.finance.yahoo.com` scan under `src/`: no matches
- Fresh-eyes review: no findings

## Potential Risks

- Yahoo remains a single-provider dependency and can still rate-limit a run.
- Same-run history fallback and outcome reconciliation are intentionally deferred to Step 3.

## TECH-DEBT Items

- None.

## Next Step

Step 3 adds fresh same-run history fallback and reconciles direct, fallback,
failed, and partial outcomes without overstating source success.
