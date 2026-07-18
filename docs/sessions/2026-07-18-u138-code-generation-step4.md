# Session Log: 2026-07-18 - u138 - Code Generation Step 4

## Overview

- **Date**: 2026-07-18
- **Unit**: u138 price-source-endpoint-lifecycle-repair
- **Stage**: Code Generation
- **Step**: 4 of 6 - Retire Stooq and preserve Korean legs

## Work Summary

Removed both dead Stooq production adapters and replaced their Korean duties
with independent Yonhap index and FRED DEXKOUS FX adapters. Registry, source
spec, segment-core, and domestic-anchor trust paths now use truthful source
identities without a retired endpoint or route.

## Files Changed

- Created: `src/investo/sources/yonhap_index_close.py`
- Created: `src/investo/sources/fred_fx_close.py`
- Removed: `src/investo/sources/stooq_kr_market.py`
- Removed: `src/investo/sources/stooq_price.py`
- Modified: source discovery, specs, tiers, core routing, and domestic quarantine
- Created: focused Yonhap/FRED adapter tests and a Yonhap-identity fixture copy
- Removed: retired Stooq adapter tests
- Modified: plugin/spec/segment/domestic-anchor tests and source declarations
- Modified: u138 plan and `aidlc-docs/aidlc-state.md`

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Keep Yonhap fixed to KOSPI/KOSDAQ and one RSS request | Preserve the proven u67 parser without claiming FX or inventing missing values |
| Give DEXKOUS a dedicated price adapter | Keep KRW-per-USD metadata, freshness, and timestamps out of macro defaults |
| Preserve FRED observation date and New York noon | Represent the H.10 observation honestly instead of relabeling it as a KRX close |
| Apply source-aware u109 freshness | FRED may use age 0-7 values; Yonhap, KRX, and large-cap sources remain exact-date |
| Remove the orphan mixed-market route | `us-with-crypto-signal` existed only for the retired Stooq adapter |
| Retain historical Stooq fixtures | They remain endpoint-retirement evidence while production and active tests use replacement identities |

## Code Review Results

| Category | Status |
|----------|--------|
| Correctness | Pass after FRED/u109 boundary fix |
| Safety | Pass |
| Reliability | Pass |
| Maintainability | Pass |
| Test Coverage | Pass for Step 4 scope |

## Validation

- Full source suite: 824 passed
- Registry/spec/plugin/segment routing suite: 81 passed
- Adapter and domestic-quarantine boundary suite: 33 passed
- `uv run ruff check src tests`: passed
- `uv run ruff format --check src tests`: passed for 495 files
- `uv run mypy src`: passed for 228 source files
- `uv run python scripts/check_no_paid_apis.py`: passed
- `uv run mkdocs build --strict`: passed
- Retired endpoint/identity static checks: no runtime matches
- `git diff --check`: passed
- Fresh-eyes re-review: no remaining Step 4 findings

## Potential Risks

- The broader briefing coverage/diagnostic tests still contain retired Stooq
  expectations. Their production paths reject the retired identity correctly;
  Step 5 owns the planned derived-view and diagnostic sweep.
- DEXKOUS depends on the existing optional `FRED_API_KEY`; absence degrades only
  the FRED macro and FX adapters.

## TECH-DEBT Items

- None.

## Next Step

Step 5 updates every remaining coverage, staleness, badge, trace, and diagnostic
expectation to the replacement registry and adds final reconciliation diagnostics.
