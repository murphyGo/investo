# Code Generation Plan: `u70 cross-surface-numeric-anchor-reconciliation`

**Date**: 2026-05-24
**Unit**: u70 cross-surface-numeric-anchor-reconciliation
**Stage**: Code Generation
**Status**: Backlog / Planned
**Source**: 2026-05-24 ten-subagent user-quality review of generated segmented briefings
**Estimated Effort**: ~5-7 h
**Dependencies**:
- u49 deterministic market anchor
- u50 lightweight-charts-embed
- u55 numeric-freshness-and-market-fact-gates
- u67 domestic-channel-depth

---

## Problem Statement

The same numeric fact can drift across reader surfaces. Review examples:
- Domestic briefing status said core price source data was missing/empty, but body prose still asserted a precise KOSPI direction/move.
- US equity top table rendered `^IXIC` while the surrounding label treated the value as Nasdaq 100, which is a different index.
- Crypto top prices, body prose, trace metadata, and chart placeholders could carry different values for the same asset.
- Chart cards now render compact ticker/price/change, so stale or mismatched placeholder metadata is visible even before expanding the full chart.

u55 verifies numeric freshness and facts, but the reader still sees multiple independently rendered numeric surfaces. u70 makes those surfaces consume a single anchor payload.

Important existing path: current code already reconciles display closes through `src/investo/orchestrator/pipeline.py::_reconcile_anchor_closes` before reader formatting. u70 must extend that path for label/status/provenance/chart parity. It must not create a second close reconciler.

---

## Goal

For every core market anchor shown to the reader, one canonical anchor object must feed:
- First-viewport/top anchor table
- Body prose availability and data-limited gating
- Trace-visible numeric evidence when such values already appear in item titles/metadata; u70 does not require a full trace-footer schema rewrite
- Compact chart card ticker/price/change
- Expanded chart payload metadata

The same symbol must have the same label, value, timestamp/provenance, and data-limited status everywhere in the generated bundle.

---

## Existing Coverage / Deduplication

This unit is not a second numeric validator.

- u55 owns numeric verification, freshness, corrupt-date detection, and fact/direction gates.
- u49 owns deterministic market anchor generation.
- u50 owns chart placeholder embedding.
- u67 owns domestic index/FX fallback collection.

u70's only responsibility is **cross-surface reconciliation**. If an anchor fails u55, u70 should propagate the data-limited state instead of deciding a new numeric truth.

Module-boundary rule: `publisher.*` must not import `briefing.numeric_verify` or `briefing.freshness` directly. The orchestrator assembles prepared display anchors from briefing/core-fact outputs; publisher surfaces consume only prepared display data.

---

## Scope Boundary

In scope:
- Typed anchor handoff shared by table/body/trace/chart surfaces.
- Label normalization for indices such as Nasdaq Composite vs Nasdaq 100.
- Missing/stale anchor blocking of precise body claims.
- Regression tests for domestic missing-core, US index-label drift, and crypto price divergence.

Out of scope:
- New market data providers.
- Changing u55 numeric tolerance rules.
- Rewriting LLM prompt stages except to consume existing anchor availability flags.
- Historical archive correction.

---

## Stage Decision

- **Functional Design — SKIP**. The domain concept already exists as market anchors/core facts. This unit tightens producer-consumer wiring.
- **NFR Requirements — SKIP**. No new network, dependency, secret, or source. The work is deterministic data plumbing and validation.

---

## Implementation Steps

### Step 1 — Map current anchor producers and consumers `[ ]`
- [ ] Trace current flow from source-collected market anchors to top table, body, trace/footer, and chart placeholders.
- [ ] Identify every place that independently formats symbol labels or price/change values.
- [ ] Record which surfaces can currently render when an anchor is missing/stale.
- **Acceptance**: implementation notes list each consumer and its canonical input after the change.

### Step 2 — Define single anchor payload contract `[ ]`
- [ ] Reuse existing `MarketAnchor` / orchestrator-prepared anchor data. If an additional display contract is unavoidable, place `MarketAnchorDisplay` in `src/investo/briefing/market_anchor.py`; do not place it in `publisher`.
- [ ] Include symbol, display label, close/current value, change, pct change, timestamp, provenance/source, freshness status, and data-limited reason.
- [ ] Preserve Decimal/string formatting stability required by chart placeholder tests.
- **Acceptance**: one payload can render table row and compact chart card without recomputing labels or values.

### Step 3 — Reconcile label and symbol registry `[ ]`
- [ ] Fix `^IXIC` label to Nasdaq Composite.
- [ ] Ensure Nasdaq 100 uses an explicit correct symbol/label only if the pipeline has that anchor.
- [ ] Add tests for common US index labels (`^GSPC`, `^IXIC`, `^DJI`, and Nasdaq 100 symbol if configured).
- **Acceptance**: no test or fixture can label `^IXIC` as Nasdaq 100.

### Step 4 — Gate body assertions on anchor availability `[ ]`
- [ ] Integration point: `_reconcile_anchor_closes` / anchor preparation marks missing/stale anchors before Stage 2 reader-format output is accepted; post-generation reader-format validation blocks precise unsupported claims.
- [ ] A blocked precise direction/move claim is any sentence containing a core index/asset label plus signed percent/point/price movement or verbs equivalent to 급등/급락/상승/하락 when the matching anchor is missing/stale.
- [ ] Failure behavior: deterministic data-limited callout replaces the unsupported sentence when the sentence is isolated; otherwise publish fails with a numeric-anchor reconciliation finding.
- [ ] Keep domestic u67 fallback precedence unchanged; consume its output when available.
- **Acceptance**: domestic missing-core fixture cannot produce an unqualified KOSPI move assertion.

### Step 5 — Wire chart placeholders to the same payload `[ ]`
- [ ] Compact chart `data-close` / `data-pct` values come from the canonical anchor payload, not a separate formatter.
- [ ] Expanded chart metadata agrees with the compact card summary.
- [ ] If chart history is present but anchor freshness fails, the card labels the limitation rather than displaying a conflicting value.
- **Acceptance**: crypto fixture values match across top table, trace, compact card, and expanded metadata.

### Step 6 — Replay / regression tests `[ ]`
- [ ] Add fixture or unit test for domestic missing-core assertion block.
- [ ] Add fixture or unit test for US index label drift.
- [ ] Add fixture or unit test for BTC/ETH/SOL value divergence across surfaces.
- [ ] Add a u65 `briefing_replay` rendered-artifact regression that checks table/body/trace-visible/chart agreement on one generated markdown fixture.
- [ ] Run targeted tests plus ruff/mypy on changed source.

---

## Acceptance Criteria

- **AC-70.1** — Table, body, trace, compact chart card, and expanded chart metadata consume one canonical anchor payload.
- **AC-70.2** — `^IXIC` is labeled Nasdaq Composite, never Nasdaq 100.
- **AC-70.3** — Precise market-move body claims are blocked or marked data-limited when the underlying core anchor is missing/stale.
- **AC-70.4** — Crypto anchor values do not diverge across reader surfaces.
- **AC-70.5** — No new data provider or numeric-verification rule is introduced.

---

## Tests / Validation

Expected test areas:
- `tests/unit/publisher/test_anchor_table*.py`
- `tests/unit/publisher/test_chart_placeholder.py`
- `tests/unit/briefing/test_numeric*.py`
- `tests/unit/orchestrator/test_run_pipeline*.py` if anchor handoff changes
- `tests/unit/orchestrator/test_anchor_close_reconcile.py`
- `tests/unit/publisher/test_briefing_replay.py`

Minimum local gate:
- Targeted pytest for changed publisher/briefing/orchestrator tests.
- `uv run ruff check` on changed source/tests.
- `uv run mypy --strict` on changed source files if signatures change.

---

## Non-Goals

- New intraday data.
- Backfilling archived numeric claims.
- Replacing lightweight-charts.
- Changing compliance disclaimer or investment-advice scanner.
