# Code Generation Plan: `u106 money-energy-volatility-source-expansion`

**Date**: 2026-06-18
**Unit**: u106 money-energy-volatility-source-expansion
**Stage**: Code Generation
**Status**: Complete
**Source**: 2026-06-18 ten-agent data-source expansion review.
**Estimated Effort**: ~6-8 h
**Dependencies**:
- u102 source-adapter-registry-completeness
- u49 market anchors
- u55 numeric-freshness-and-market-fact-gates
- u74 market-channel-depth-v2

---

## Problem Statement

Current rates and commodity context is price-heavy. `treasury-rates` provides Treasury curve data, `fred-macro` provides a small macro series set, and Stooq/YFinance provide proxies such as `TLT`, `USO`, `CL=F`, `GC=F`, and VIX. The briefing still lacks official funding-market rates, petroleum supply facts, and option-tail risk measures.

## Goal

Add official/free source adapters for NY Fed reference rates, EIA weekly petroleum data, and Cboe volatility indices. These sources should explain market moves through funding, energy supply, and volatility structure rather than duplicating price snapshots.

## Existing Coverage / Deduplication

- `treasury-rates` stays the source for Treasury curve shape and spreads.
- `fred-macro` stays the source for configured FRED macro series.
- `stooq-price` and `yfinance-price` stay the source for traded price proxies.
- This unit excludes FRED ICE BofA OAS series because the review found restrictive redistribution language.

## Scope Boundary

In scope:
- NY Fed SOFR/EFFR/OBFR/BGCR/TGCR actual rates, volumes, and percentile fields.
- EIA weekly crude/gasoline/distillate inventories, production, imports, and refinery utilization.
- Cboe VVIX and SKEW official CSVs; VIX only as metadata cross-check.
- Delayed/weekly data labels in raw metadata and reader context.

Out of scope:
- Paid credit spread datasets.
- Full EIA petroleum report PDF/table extraction.
- Intraday options flow or put/call ratio until an official CSV/JSON path is confirmed.
- New chart types.

## Stage Decision

Functional Design: skip. This unit adds bounded source adapters and reuses existing channel/numeric presentation surfaces.

NFR Requirements: skip. Official/free source use, bounded retry, and delayed-data labeling are pinned here.

## Implementation Steps

- [x] Add `src/investo/sources/nyfed_reference_rates.py`.
- [x] Add `src/investo/sources/eia_petroleum_weekly.py`.
- [x] Add `src/investo/sources/cboe_volatility_indices.py`.
- [x] Register adapters in source imports, tiers, market-window sets, and segment routing.
- [x] Add raw metadata fields for units, release date, source lag, and as-of date.
- [x] Add source summaries/raw metadata that label weekly and delayed data explicitly.
- [x] Record replay-style unit fixtures for each source and failure shape.
- [x] Add tests proving no restricted FRED ICE BofA series enters default config.

## Acceptance Criteria

1. NY Fed reference rates emit official observed values and volumes without API key or paid dependency.
2. EIA petroleum rows emit weekly supply facts with source lag and release-date metadata.
3. Cboe volatility rows prioritize VVIX/SKEW and do not duplicate VIX price snapshots as a new core source.
4. Weekly and delayed data cannot be described as intraday or current-session facts in prompt context.
5. Adapter failures are isolated and visible in source outcomes.
6. No source in this unit requires a billing account or paid tier.

## Tests / Validation

- `uv run pytest tests/unit/sources/test_nyfed_reference_rates.py tests/unit/sources/test_eia_petroleum_weekly.py tests/unit/sources/test_cboe_volatility_indices.py -q`
- `uv run pytest tests/unit/publisher/test_channel_anchor_block.py tests/unit/briefing -q -k 'macro or channel or source'`
- `uv run pytest tests/unit/sources/test_plugin_contract.py tests/unit/sources/test_aggregator.py -q`
- `uv run ruff check src/investo/sources src/investo/publisher tests/unit/sources`
- `uv run mypy --strict src/investo/sources src/investo/publisher`
- `uv run python scripts/check_no_paid_apis.py`

## Source Declaration

- Source URL: NY Fed Markets API, EIA Open Data or Weekly Petroleum Status public data, Cboe official volatility CSV endpoints
- Auth: none for NY Fed and Cboe; EIA free key only when selected endpoint requires it
- Free-tier rate limit: one bounded fetch per source group per run
- No paid tier required: official/free endpoints only

## Non-Goals

- No paid credit spreads.
- No intraday option flow.
- No technical-analysis indicator package.
- No archive backfill.
