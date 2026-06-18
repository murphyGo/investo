# Code Generation Plan: `u107 cftc-positioning-layer`

**Date**: 2026-06-18
**Unit**: u107 cftc-positioning-layer
**Stage**: Code Generation
**Status**: Complete
**Source**: 2026-06-18 ten-agent data-source expansion review.
**Estimated Effort**: ~5-8 h
**Dependencies**:
- u102 source-adapter-registry-completeness
- u66 crypto-channel-depth
- u67 domestic-channel-depth
- u74 market-channel-depth-v2

---

## Problem Statement

Investo has domestic investor flows, crypto funding/OI, Fear & Greed, global crypto market structure, and broad market prices. It does not have regulated futures positioning that explains whether leveraged funds, asset managers, dealers, or commercials are leaning into equity index, rates, FX, commodity, VIX, or crypto futures moves.

## Goal

Add a CFTC COT/TFF positioning layer for a bounded contract allow-list. The data must be clearly labeled as weekly and delayed, because CFTC reports are released on Friday and generally reflect Tuesday positions.

## Existing Coverage / Deduplication

- Complements `krx-foreign-flows`; it does not replace domestic investor-flow data.
- Complements `bybit-derivatives` and `okx-derivatives`; it does not replace crypto-native funding/OI.
- Complements `alternative-fng`; it is positioning data, not sentiment survey data.
- Does not implement paid liquidation, exchange netflow, or private positioning APIs.

## Scope Boundary

In scope:
- Official CFTC public data access for COT/TFF reports.
- Bounded contract allow-list covering S&P 500, Nasdaq, VIX, Treasury futures, USD/FX, WTI, gold, and crypto futures where official contract rows exist.
- Raw metadata for report date, as-of date, release date, trader category, net positioning, open interest, and units.
- Reader-facing delayed-data labels.

Out of scope:
- Full historical backfill.
- Unbounded contract universe.
- Positioning signal trading rules.
- Coinglass, CryptoQuant, Glassnode, paid netflow, or paid liquidation feeds.

## Stage Decision

Functional Design: skip. The unit is a bounded source adapter and presentation-labeling extension.

NFR Requirements: skip. Official no-key data, R10 fixture, and weekly lag constraints are pinned here.

## Implementation Steps

- [x] Add `src/investo/sources/cftc_cot_positioning.py`.
- [x] Define a contract allow-list with reader labels and segment routing for each contract group.
- [x] Fetch official CFTC public data using bounded query parameters or yearly compressed files with current-year filtering.
- [x] Parse report rows into `NormalizedItem` values with `category="macro"`.
- [x] Register adapter import, tier, market-window behavior, and segment routing.
- [x] Add a presentation helper or extend channel-depth rendering so weekly delayed positioning appears as context, not current-session data.
- [x] Record fixtures for current report, holiday-delayed report, unmapped contract, malformed row, and source failure.

## Acceptance Criteria

1. CFTC positioning data is collected from official public endpoints without token or paid dependency.
2. Only allow-listed contracts are emitted; unmapped contracts are ignored.
3. Report metadata includes as-of date and release date.
4. Published context labels CFTC data as weekly/delayed and never as intraday flow.
5. Adapter failure is isolated and visible in source outcomes.
6. Tests prove paid liquidation/netflow providers remain absent from source files and config.

## Tests / Validation

- `uv run pytest tests/unit/sources/test_cftc_cot_positioning.py tests/unit/sources/test_plugin_contract.py -q`
- `uv run pytest tests/unit/briefing/test_segments*.py tests/unit/publisher/test_channel_anchor_block.py -q`
- `uv run pytest tests/unit/sources/test_aggregator.py -q`
- `uv run ruff check src/investo/sources src/investo/briefing src/investo/publisher tests/unit/sources`
- `uv run mypy --strict src/investo/sources src/investo/briefing src/investo/publisher`
- `uv run python scripts/check_no_paid_apis.py`

## Source Declaration

- Source URL: CFTC Commitments of Traders public reporting and historical compressed report endpoints
- Auth: none
- Free-tier rate limit: one bounded current-report fetch per run or one current-year file fetch per run
- No paid tier required: official public CFTC data

## Non-Goals

- No paid positioning products.
- No crypto liquidation/netflow implementation.
- No trading recommendation or positioning score.
- No archive backfill.
