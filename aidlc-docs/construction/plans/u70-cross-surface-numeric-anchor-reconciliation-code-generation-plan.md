# Code Generation Plan: `u70 cross-surface-numeric-anchor-reconciliation`

**Date**: 2026-05-24
**Unit**: u70 cross-surface-numeric-anchor-reconciliation
**Stage**: Code Generation
**Status**: Complete (6/6 — closed 2026-05-24; FD + NFR SKIP confirmed; gate green)
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

### Step 1 — Map current anchor producers and consumers `[x]`
- [x] Trace current flow from source-collected market anchors to top table, body, trace/footer, and chart placeholders.
- [x] Identify every place that independently formats symbol labels or price/change values.
- [x] Record which surfaces can currently render when an anchor is missing/stale.
- **Acceptance**: implementation notes list each consumer and its canonical input after the change.

  Findings: producer is `orchestrator.pipeline._load_market_anchors_for_run` (+ `_build_kr_anchors_from_items`). Consumers and their canonical input *after* this change:
  - top anchor table — `render_anchor_table(anchor_table_input)` (reconciled payload).
  - compact + expanded chart card — `_inject_chart_blocks_into_segments(anchors_by_segment=anchor_table_input)` (was the un-reconciled `market_anchors_by_segment` — the divergence root cause; now the same reconciled payload).
  - body prose availability — gated by `enforce_anchor_assertions(available_symbols=anchors)` against the same payload's tickers.
  - trace footer — item titles/metadata (cites the price-snapshot close `_snapshot_close_by_ticker` feeds into reconciliation; unchanged schema).
  - Telegram snapshot line — `notifier.summary._market_snapshot_line` now labels via the shared `anchor_label` registry (was the hard-coded `NDX` mislabel for `^IXIC`).
  Independent label formatters removed: the Telegram line's inline `"NDX"`/`"SPX"` strings now route through the registry; the chart card gained `data-label`.
  Missing/stale rendering: previously the body could assert a precise move for a symbol absent from the payload (domestic missing-core KOSPI case). Now gated.

### Step 2 — Define single anchor payload contract `[x]`
- [x] Reuse existing `MarketAnchor` / orchestrator-prepared anchor data. The single reconciled `anchor_table_input` map (per-segment `MarketAnchor` tuples from `_reconcile_anchor_closes`) is the canonical payload; no separate `MarketAnchorDisplay` was needed. The label dimension is added as a side registry (`AnchorLabel` in `market_anchor.py`) keyed by symbol so existing `MarketAnchor` consumers stay unchanged.
- [x] Symbol/value/change/pct live on `MarketAnchor`; display label resolves via `anchor_label(symbol)`; freshness/data-limited is expressed by *presence in the payload* (absent ⇒ data-limited, enforced by the body gate). Provenance/timestamp remain on the source items the trace footer surfaces.
- [x] Decimal/string formatting stability preserved — chart placeholder tests still pass (`data-close` formatting unchanged; only `data-label` added).
- **Acceptance**: one payload renders table row + compact chart card without recomputing labels or values (table render and chart injection both consume `anchor_table_input`).

### Step 3 — Reconcile label and symbol registry `[x]`
- [x] `^IXIC` → 나스닥 종합 / "Nasdaq" (Nasdaq Composite) in the `_ANCHOR_LABELS` registry; the Telegram `NDX` mislabel fixed.
- [x] Nasdaq 100 uses the distinct `^NDX` symbol/label (registered but the pipeline does not fetch it today, so it never appears unless added).
- [x] Tests added: `test_anchor_label.py` (`^GSPC`/`^IXIC`/`^DJI`/`^NDX`), chart-card `^IXIC` label test, replay `anchor-ixic-mislabel` finding.
- **Acceptance**: no test/fixture labels `^IXIC` as Nasdaq 100; replay flags it as an error if it ever appears.

### Step 4 — Gate body assertions on anchor availability `[x]`
- [x] Integration point: `enforce_anchor_assertions` runs inside `_apply_reader_format_to_segments` (reader-format pass), consuming the reconciled payload's tickers as `available_symbols`.
- [x] A blocked precise claim = core label + movement verb (급등/급락/상승/하락/반등/폭락/폭등/강세/약세) + explicit magnitude (%/포인트/원/달러/$) when the matching anchor is absent.
- [x] Failure behavior: isolated sentence → deterministic data-limited callout (idempotent); interleaved/structural → `NumericAnchorReconciliationError` (caught by the publish-stage reader-format handler → FAILED + alert).
- [x] u67 domestic fallback precedence unchanged — `_build_kr_anchors_from_items` still runs first; the gate only fires when no KR anchor was produced.
- **Acceptance**: domestic missing-core (`available_symbols=()`) cannot produce an unqualified KOSPI move assertion (test_anchor_assertion_gate).

### Step 5 — Wire chart placeholders to the same payload `[x]`
- [x] Chart injection reordered to run *after* `_reconcile_anchor_closes` and now consumes `anchor_table_input` — `data-close` / `data-pct` come from the same canonical anchor the table uses.
- [x] Compact card and expanded metadata read the same div attributes; both now also carry `data-label` (canonical registry label).
- [x] `data-52w-high`/`data-52w-low` stay history-derived inside the renderer (candlestick axis fidelity), but the summary close matches the table. A missing anchor → no chart for that ticker (history-keyed), so no conflicting value is shown.
- **Acceptance**: replay `anchor-close-divergence` test confirms table close == chart card close for the same symbol.

### Step 6 — Replay / regression tests `[x]`
- [x] Domestic missing-core assertion block — `test_anchor_assertion_gate.py::test_isolated_kospi_claim_without_anchor_is_rewritten` + `test_enforce_raises_on_blocking_finding`.
- [x] US index label drift — `test_anchor_label.py` + `test_chart_placeholder.py` (`^IXIC` label) + replay `test_replay_flags_ixic_nasdaq_100_mislabel`.
- [x] Crypto/value divergence across surfaces — `test_replay_flags_anchor_close_divergence` (generalised parity check covers BTC/ETH too) + gate crypto test.
- [x] `briefing_replay` rendered-artifact regression — `test_replay_anchor_surfaces_agree` checks table/chart agreement on a generated markdown fixture.
- [x] Targeted tests + ruff + mypy on changed source — all green; full suite 2528 passed; `mkdocs build --strict` ok.

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
