# Code Generation Plan: `u8 market-aware-source-window`

**Date**: 2026-05-07
**Unit**: u8 market-aware-source-window
**Stage**: Code Generation

---

## Goal

Fix the post-u7 coverage regression where US equity and crypto segments can receive zero routed items because all source adapters are filtered through a KST trading-day window.

---

## Definition of Done

- [x] `FetchWindow` can represent an arbitrary market local-date window while preserving the existing KST helper.
- [x] Aggregator passes KST windows to domestic sources, New York windows to US-market sources, and UTC windows to crypto sources.
- [x] A US/crypto item published after the KST cutoff but inside its own market date is retained.
- [x] Existing segmented briefing routing and orchestrator tests remain green.

---

## Steps

### Step 1 — Source Window Model

- [x] Add `FetchWindow.from_local_date(target_date, tz)` for market-specific local-day boundaries.
- [x] Keep `FetchWindow.from_kst_date()` as the compatibility helper for existing domestic sources and tests.
- [x] Add anchor tests for New York and UTC windows.

### Step 2 — Aggregator Window Selection

- [x] Add source-name groups for US-market and crypto adapters.
- [x] In `fetch_all(target_date)`, pass each adapter its market-specific window.
- [x] Keep future-dated item filtering relative to the window assigned to that adapter.

### Step 3 — Regression Tests

- [x] Assert `nasdaq-stocks-news` receives a New York window for `2026-05-06`.
- [x] Assert `coingecko-price` receives a UTC window for `2026-05-06`.
- [x] Assert `2026-05-06T18:00:00Z` US/crypto items survive collection.
- [x] Re-run u7 segment/orchestrator tests.

### Step 4 — Docs and State

- [x] Document FR-001's market-day filtering requirement.
- [x] Add u8 to the unit map and state tracker.
- [x] Write cross-check evidence.
