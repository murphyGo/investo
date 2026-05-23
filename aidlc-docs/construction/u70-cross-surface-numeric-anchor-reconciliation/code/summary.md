# u70 cross-surface-numeric-anchor-reconciliation — Code Generation Summary

**Date**: 2026-05-24
**Unit**: u70 cross-surface-numeric-anchor-reconciliation
**Status**: Complete (6/6 steps)

## Goal

For every core market anchor shown to the reader, one canonical anchor payload must feed the top anchor table, body-prose availability/data-limited gating, trace-visible numeric evidence, the compact chart card (ticker/price/change), and the expanded chart metadata — so the same symbol carries the same label, value, timestamp/provenance, and data-limited status everywhere in the generated bundle (plan Goal). u70 is **not** a second numeric validator: u55 owns numeric verification/freshness/fact gates; u49 owns deterministic anchor generation; u50 owns chart embedding; u67 owns domestic index/FX fallback. u70's only responsibility is cross-surface reconciliation (AC-70.5).

## Scope

In scope: single typed anchor handoff shared by table/body/trace/chart; index label normalization (Nasdaq Composite vs Nasdaq 100); missing/stale anchor blocking of precise body claims; regression tests for domestic missing-core, US index-label drift, and crypto price divergence.
Out of scope: new market data providers; changing u55 numeric tolerance; rewriting LLM prompt stages beyond consuming anchor availability flags; historical archive correction.

## Stage Decision

- **Functional Design — SKIP**. The domain concept already exists as market anchors / core facts (u49/u55). This unit tightens producer-consumer wiring; no new entity. Confirmed at closeout — no FD file created.
- **NFR Requirements — SKIP**. No new network call, dependency, secret, or source. Deterministic data plumbing + validation under the existing UTC-window/retry budget. Confirmed at closeout — no NFR file created.

## P1-2 Relationship (extension, not replacement)

The existing `src/investo/orchestrator/pipeline.py::_reconcile_anchor_closes` (single-close reconciliation) is **retained unchanged** as the close reconciler. u70 does **not** create a second close reconciler. It extends that path:

- **(a) Chart injection moved onto the reconciled payload** — chart injection previously consumed the **un-reconciled** `market_anchors_by_segment`, which was the root cause of chart-vs-table divergence. It now consumes the same reconciled `anchor_table_input` the table uses.
- **(b) Symbol→label registry added** — `AnchorLabel` registry + `anchor_label(symbol)` in `briefing/market_anchor.py`.
- **(c) Body-assertion gate added** — precise move claims are gated on anchor availability in the payload.

## Single Anchor Payload Contract

The single reconciled `anchor_table_input` map (per-segment `MarketAnchor` tuples produced once by `_reconcile_anchor_closes`) is the canonical source for **table + compact card + expanded metadata + body gate**. No separate `MarketAnchorDisplay` type was needed; the label dimension is a side registry keyed by symbol so existing `MarketAnchor` consumers are unchanged.

| Surface | Canonical input | Label source | Missing/stale behavior |
|---------|-----------------|--------------|------------------------|
| Top anchor table | `render_anchor_table(anchor_table_input)` | `anchor_label(symbol)` | absent from payload => row not rendered |
| Compact chart card | `_inject_chart_blocks_into_segments(anchors_by_segment=anchor_table_input)` | `data-label` = `anchor_label(symbol)` | absent => no chart (history-keyed) |
| Expanded chart metadata | same div `data-close`/`data-pct`/`data-label` | `anchor_label(symbol)` | absent => no conflicting value shown |
| Body prose | `enforce_anchor_assertions(available_symbols=anchors)` | n/a | absent => precise move claim gated |
| Trace footer | item titles/metadata (`_snapshot_close_by_ticker` feeds reconciliation) | unchanged schema | — |
| Telegram snapshot | `notifier.summary._market_snapshot_line` via `anchor_label` registry | `anchor_label(symbol)` | — |

Label = `anchor_label(symbol)`. Missing/stale = absence from the payload (enforced by the body gate). `data-close` formatting is unchanged; only `data-label` was added.

## Key Deliverables

- **New** `src/investo/publisher/anchor_assertion_gate.py`: `gate_body_assertions` / `enforce_anchor_assertions` / `NumericAnchorReconciliationError`. A blocked claim = core label + movement verb (급등/급락/상승/하락/반등/폭락/폭등/강세/약세) + explicit magnitude (%/포인트/원/달러/$) when the matching anchor is absent. Isolated sentence => deterministic idempotent data-limited callout; interleaved/structural => `NumericAnchorReconciliationError`.
- **Changed** `src/investo/briefing/market_anchor.py`: canonical `AnchorLabel` registry + `anchor_label()`; `^IXIC` -> 나스닥 종합 / "Nasdaq" (Nasdaq Composite); `^NDX` -> 나스닥 100 registered as a distinct symbol/label.
- **Changed** `src/investo/publisher/charts.py`: compact card carries `data-label`.
- **Changed** `src/investo/notifier/summary.py`: Telegram snapshot label routes through the registry (fixes the hard-coded `^IXIC`->"NDX" mislabel).
- **Changed** `src/investo/orchestrator/pipeline.py`: reconciled `anchor_table_input` computed once and supplied to chart/table/body-gate; `NumericAnchorReconciliationError` added to the reader-format `except` (-> FAILED + alert).
- **Changed** `src/investo/publisher/briefing_replay.py`: cross-surface parity findings `anchor-close-divergence` and `anchor-ixic-mislabel`.
- **Changed** `site_docs/assets/investo-chart-init.js`: renders `data-label`.
- **Tests**: `test_anchor_assertion_gate.py`, `test_anchor_label.py`, `test_chart_placeholder.py` (`^IXIC` label), `test_briefing_replay.py` (`anchor-close-divergence` / `anchor-ixic-mislabel` / `anchor_surfaces_agree`).

## Module Boundary

`anchor_assertion_gate.py` is publisher-internal and consumes prepared display anchors only (no `briefing.numeric_verify` / `briefing.freshness` import). The orchestrator assembles the prepared display anchors; publisher surfaces consume prepared data only. Orchestrator-only cross-unit import rule upheld.

## AC Traceability

| AC | Statement | Status | Evidence |
|----|-----------|--------|----------|
| AC-70.1 | Table, body, trace, compact chart card, and expanded chart metadata consume one canonical anchor payload | MET | single `anchor_table_input` feeds table + chart injection + body gate; `test_replay_anchor_surfaces_agree` |
| AC-70.2 | `^IXIC` labeled Nasdaq Composite, never Nasdaq 100 | MET | `AnchorLabel` registry; `test_anchor_label.py`; replay `anchor-ixic-mislabel` |
| AC-70.3 | Precise move body claims blocked / marked data-limited when core anchor missing/stale | MET | `enforce_anchor_assertions`; `test_anchor_assertion_gate.py` (domestic missing-core KOSPI) |
| AC-70.4 | Crypto anchor values do not diverge across reader surfaces | MET | chart injection on reconciled payload; `test_replay_flags_anchor_close_divergence` (BTC/ETH) |
| AC-70.5 | No new data provider or numeric-verification rule introduced | MET | reuses `MarketAnchor` / `_reconcile_anchor_closes` / u55 gates; only a label registry + body gate added |

## FD Divergences Ratified

None. FD was SKIP (no entity). No code-vs-spec divergence to ratify.

## TECH-DEBT Registered

None. No new debt candidate surfaced by this unit.

## Potential Risks

- The body-assertion gate's move-verb / magnitude heuristic is conservative — it requires an explicit signed percent/point/price. Ambiguous claims with no numeric magnitude (e.g. "코스피 큰 폭 급락" with no figure) are **not** gated. This matches the plan's Step 4 definition ("precise signed percent/point/price"); broader rhetorical-claim detection is intentionally out of scope.
- `data-52w-high`/`data-52w-low` remain history-derived inside the renderer (candlestick axis fidelity); the summary close matches the table. A missing anchor produces no chart, so no conflicting value is shown.

## Verification Gate

- ruff check: clean
- mypy --strict: 139 files clean
- pytest: 2528 passed (integration 42)
- mkdocs build --strict: pass
