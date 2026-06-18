# Code Generation Plan: `u105 macro-actual-source-of-record`

**Date**: 2026-06-18
**Unit**: u105 macro-actual-source-of-record
**Stage**: Code Generation
**Status**: Complete (7/7 steps — 2026-06-18)
**Source**: 2026-06-18 ten-agent data-source expansion review.
**Estimated Effort**: ~6-9 h
**Dependencies**:
- u102 source-adapter-registry-completeness
- u43 FOMC/FRED lookahead adapters
- u59 macro-actual-priority-and-lineage
- DEBT-079 macro calendar/actual event-key join

---

## Problem Statement

Investo already tracks many macro release dates through `fred-economic-calendar` and some actual series through `fred-macro`. The gap is source-of-record actual release detail for BLS and BEA events. For market-moving releases such as CPI, payrolls, PCE, and GDP, the briefing needs official actual/prior/period metadata and canonical event keys that line up with calendar entries.

## Goal

Add BLS and BEA official actual data adapters for a bounded macro release allow-list. The output should support u59 macro lifecycle and priority behavior without inventing consensus, forecast, or surprise values.

## Existing Coverage / Deduplication

- `fred-economic-calendar` already provides release schedules for CPI, PPI, Employment Situation, GDP, PCE, industrial production, retail sales, JOLTS, housing starts, and existing home sales.
- `fred-macro` already provides a small set of macro observations.
- u59 owns macro lifecycle and drop diagnostics. This unit only adds source-of-record actual inputs and event-key metadata.
- u55 owns numeric gates. This unit does not create a separate numeric validation engine.

## Scope Boundary

In scope:
- BLS Public Data API actuals for CPI, core CPI, payroll employment, unemployment rate, average hourly earnings, labor force participation, PPI, and JOLTS.
- BEA API actuals for GDP and PCE/core PCE from bounded NIPA tables.
- Canonical `macro_event_key` stamping for schedule/actual joins.
- Official source URLs and release-period metadata.

Out of scope:
- Consensus, economist forecast, survey median, and surprise calculation.
- ISM/S&P Global PMI implementation.
- Global central bank calendars.
- Rewriting existing macro lifecycle semantics.

## Stage Decision

Functional Design: skip. This is a source-adapter expansion that uses existing macro lineage contracts.

NFR Requirements: skip. Free official API and graceful-degradation contracts are pinned here.

## Implementation Steps

- [x] Add `src/investo/sources/bls_macro_actuals.py` with bounded series configuration and `retry_get`.
- [x] Add `src/investo/sources/bea_macro_actuals.py` with bounded dataset/table/line configuration and `retry_get`.
- [x] Add optional free-key env handling for BLS/BEA only when the endpoint requires it; missing keys produce `SourceFetchError(transient=False)`.
- [x] Register adapters in imports, tiers, market-window sets, and segment routing.
- [x] Stamp `macro_event_key`, `release_period`, `actual_value`, `prior_value` when official data provides prior values, `unit`, `source_url`, and `observed_at`.
- [x] Update macro prompt/context rendering to prioritize official actual rows using existing candidate caps.
- [x] Add R10 fixtures for BLS current release, BEA current release, empty payload, malformed payload, missing-key behavior, and source failure.

## Acceptance Criteria

1. CPI, payrolls, PCE, and GDP actual rows are available from official BLS/BEA sources when configured keys and endpoints are available.
2. Official actual rows carry canonical `macro_event_key` values that join with existing calendar rows.
3. The pipeline never renders consensus or surprise values unless official source fields provide those values directly.
4. Missing API keys or endpoint errors degrade per adapter and keep sibling sources running.
5. R13 tests prove secret values do not enter logs, raw metadata, fixtures, or public markdown.
6. Macro lifecycle tests show a scheduled event and actual row collapse to one confirmed event for at least CPI/PCE/GDP sample cases.

## Tests / Validation

- `uv run pytest tests/unit/sources/test_bls_macro_actuals.py tests/unit/sources/test_bea_macro_actuals.py -q`
- `uv run pytest tests/unit/briefing/test_macro_carryover.py tests/unit/briefing/test_market_anchor.py -q`
- `uv run pytest tests/unit/sources/test_plugin_contract.py tests/unit/sources/test_aggregator.py -q`
- `uv run ruff check src/investo/sources src/investo/briefing tests/unit/sources`
- `uv run mypy --strict src/investo/sources src/investo/briefing`
- `uv run python scripts/check_no_paid_apis.py`

## Source Declaration

- Source URL: BLS Public Data API and BEA API endpoints for bounded official datasets
- Auth: none or free API key, depending on endpoint requirements at implementation time
- Free-tier rate limit: documented in PR body; adapter calls are bounded to release allow-list
- No paid tier required: only official free endpoints are allowed

## Non-Goals

- No paid macro calendar provider.
- No forecast/surprise data.
- No LLM fact checking.
- No global central bank implementation in this unit.
