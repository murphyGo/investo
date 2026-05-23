# Code Generation Plan: `u75 chart-data-externalization-and-mobile-performance`

**Date**: 2026-05-24
**Unit**: u75 chart-data-externalization-and-mobile-performance
**Stage**: Code Generation
**Status**: Complete (5/5 steps) — closed 2026-05-24
**Source**: 2026-05-24 mobile/user-quality review after compact chart-card implementation
**Estimated Effort**: ~4-6 h
**Dependencies**:
- u50 lightweight-charts-embed
- Compact market chart card change, commit `4b78384 Compact market chart cards`:
  - `src/investo/publisher/charts.py` now emits compact summary attributes `data-close` and optional `data-pct`.
  - `site_docs/assets/investo-chart-init.js` renders ticker/price/change plus a small line sparkline by default.
  - Full candlestick chart is expanded on click/open.

---

## Problem Statement

The chart UI is now visually compact: the user sees ticker, price/change, and a small line sparkline; the full candlestick chart expands on click. However, each chart placeholder can still embed large OHLC history JSON inline in the markdown/HTML. That means the reader pays the payload cost before interacting with the chart, especially on mobile.

The visual problem was solved; the payload problem remains.

Existing compact-card contract to preserve:
- Compact card renders without heavyweight history fetch.
- Placeholder keeps ticker, display label, `data-close`, and optional `data-pct`.
- Expanded chart still uses the existing self-hosted lightweight-charts bundle.
- No CDN, no paid chart API, no server endpoint.

---

## Goal

Externalize heavy chart history into deterministic archive-local sidecar JSON files and lazy-load them only when the user expands the chart (or when an explicit viewport-triggered enhancement is chosen). Compact cards must render without fetching heavy history.

---

## Existing Coverage / Deduplication

This unit is not a chart redesign.

- u50 added lightweight-charts embedding and chart placeholder helpers.
- The compact card change already reduced visual prominence and added compact ticker/price/sparkline behavior.

u75 only changes payload ownership and lazy loading:
- Inline summary data stays small.
- Full OHLC history moves to sidecar JSON.
- Existing chart library and visual semantics remain.

---

## Scope Boundary

In scope:
- Sidecar JSON generation/staging next to segment assets.
- Placeholder schema changes from inline `data-history` to sidecar URL/path.
- Lazy fetch in `site_docs/assets/investo-chart-init.js`.
- Small error/loading state for sidecar fetch failure.
- Payload-size regression tests.

Out of scope:
- New chart provider.
- CDN or server endpoint.
- Changing the full candlestick chart design.
- Replacing lightweight-charts.
- Historical archive backfill unless a fixture requires a minimal generated sidecar.

---

## Stage Decision

- **Functional Design — SKIP**. This is an asset-packaging and client-loading refactor over existing chart artifacts.
- **NFR Requirements — SKIP**. No new dependency or external service. Performance improves by reducing initial payload; cost remains zero.

---

## Implementation Steps

### Step 1 — Define sidecar file contract `[x]`
- [x] Use deterministic path: `{segment_archive_stem}.assets/charts/{chart_id}.json`, relative to the markdown file. Example: `2026-05-24.assets/charts/us-equity-aapl.json`.
- [x] Derive `chart_id` as `{segment}-{normalized_ticker}` lowercased, replacing non `[a-z0-9]+` runs with `-`; if duplicate, append `-{ordinal}` in source order.
- [x] Sidecar JSON schema:
  - `schema_version`: integer, fixed `1`.
  - `chart_id`: string.
  - `ticker`: original ticker string.
  - `label`: display label.
  - `summary`: object with string fields `close`, optional `pct`, optional `ath`, optional `high_52w`, optional `low_52w`.
  - `history`: array sorted ascending by date, rows `{t:"YYYY-MM-DD", o:string, h:string, l:string, c:string, v:string|null}`.
  - `provenance`: object with deterministic `source` and `run_date`; no wall-clock timestamp.
- [x] Numeric values are serialized as strings using the same Decimal formatting as existing chart placeholders; JSON uses compact separators and stable key order.
- **Acceptance**: contract test serializes a chart sidecar with deterministic path/content.

### Step 2 — Change publisher placeholder generation `[x]`
- [x] Replace full inline history with compact summary data plus `data-history-src` containing the relative sidecar JSON path.
- [x] Preserve existing `data-close` / `data-pct` compact rendering.
- [x] Ensure no HTML/script injection vector is introduced through the path or JSON.
- **Acceptance**: placeholder HTML contains no full OHLC history and contains the sidecar reference.

### Step 3 — Stage sidecar assets with archive output `[x]`
- [x] Update orchestrator/publisher staging so sidecar JSON files are written and staged with the segment markdown/assets.
- [x] Preserve idempotent rerun behavior.
- [x] Ensure missing sidecar fails gracefully in UI and replay validation.
- **Acceptance**: integration/fixture test shows markdown plus sidecar paths staged together.

### Step 4 — Lazy-load expanded chart data `[x]`
- [x] Update `investo-chart-init.js` to render compact card without fetching sidecar.
- [x] Fetch sidecar only on explicit click or keyboard activation of the expand control. Viewport entry must not fetch the sidecar in v1.
- [x] Show loading/error state if fetch fails; do not break other chart cards.
- [x] Keep dark/light theme behavior and existing MutationObserver semantics.
- **Acceptance**: JS unit/static checks prove no fetch is required before expansion and failed fetch degrades per-card only.

### Step 5 — Payload and regression tests `[x]`
- [x] Add test asserting generated markdown/HTML payload does not include full history JSON: no `data-history`, no serialized OHLC row arrays, and max inline chart attributes under 1 KB per card in the multi-card fixture.
- [x] Add sidecar JSON escaping/path tests.
- [x] Add staging/static validation that sidecar JSON appears under the archive asset directory and is reachable by the relative `data-history-src` path.
- [x] Add replay validation that a missing sidecar is reported as a chart payload finding while the compact card still renders.
- [x] Add `node --check` for JS changes.
- [x] Run targeted chart publisher tests, ruff/mypy on changed source, mkdocs strict if assets/site config changes.

---

## Acceptance Criteria

- **AC-75.1** — Full OHLC history is not embedded inline in segment markdown/HTML.
- **AC-75.2** — Archive-local sidecar JSON is deterministic, staged with the briefing, and GitHub Pages compatible.
- **AC-75.3** — Compact chart cards render ticker/price/change without fetching the sidecar.
- **AC-75.4** — Expanded candlestick charts lazy-load sidecar data only on explicit click/keyboard expand and degrade per-card on failure.
- **AC-75.5** — Existing chart visual semantics and bundled chart library remain unchanged.

---

## Tests / Validation

Expected test areas:
- `tests/unit/publisher/test_chart_placeholder.py`
- `tests/unit/publisher/test_chart_assets.py`
- `tests/unit/orchestrator/test_run_pipeline*.py` if staging changes
- `site_docs/assets/investo-chart-init.js` checked with `node --check`

Minimum local gate:
- Targeted chart/orchestrator pytest.
- `uv run ruff check` on changed source/tests.
- `uv run mypy --strict` on changed source files if signatures change.
- `node --check site_docs/assets/investo-chart-init.js`.
- `uv run mkdocs build --strict` if site assets are touched.

---

## Non-Goals

- Visual redesign.
- CDN adoption.
- Paid chart data.
- Backfilling old archive chart payloads.
