# u50 Lightweight Charts Embed — Code Generation Summary

**Date**: 2026-05-10
**Unit**: u50 lightweight-charts-embed
**Status**: Complete (5/5 steps)

## Goal

Translate the user's TradingView account + charting library availability into reader-facing UX. Embed TradingView Lightweight Charts (Apache-2.0, self-hosted) in segmented briefings so readers see interactive candlestick charts with ATH and 52w high/low markers — without paying for the TradingView data API. Data is supplied from u49's existing 1-year Yahoo Finance v8 fetch; the SVG cards from u24/u26 remain as a progressive-enhancement fallback.

## Steps

### Step 1 — Self-hosted vendor bundle (R10)

- `site_docs/assets/lightweight-charts.standalone.production.js` — TradingView Lightweight Charts v4.2.3, downloaded from `unpkg.com/lightweight-charts@4.2.3/dist/`. 163,684 bytes. sha256 `c7dda807d662a95b3d257119ed315cec669e3bdf5aaece75c480a39307f23540`.
- `site_docs/assets/lightweight-charts.LICENSE.txt` — Apache-2.0 (upstream relicensed; plan said MIT — both OSI-approved permissive licenses for self-hosting). sha256 `70c9d5382506dd184465425c08a99ad9bd6d9ac1313c252968ba0b585e5ef823`.
- No CDN: `extra_javascript` references local `assets/...` paths. R10 external dependency contained.

### Step 2 — `investo-chart-init.js` progressive-enhancement init

- ~7.6 KB. On `DOMContentLoaded`:
  - Scans `.investo-chart` divs (cap 5 / page).
  - Parses `data-history` JSON → `{time, open, high, low, close}` bars.
  - Builds `LightweightCharts.createChart(...).addCandlestickSeries(...)`.
  - Adds `priceLine` overlays for `data-ath` (Dashed), `data-52w-high` (Dotted), `data-52w-low` (Dotted).
  - Light/dark theme from `[data-md-color-scheme]` via `MutationObserver`.
  - Aria-label per chart from `data-ticker`.
  - Parse failure → collapse div + `console.warn`. The SVG card above remains the visible fallback (no JS path is self-explanatory).

### Step 3 — `publisher/charts.py` placeholder builder (pure)

- `render_chart_placeholder(anchor, history)`, `build_chart_block(anchors, history_by_ticker)`, `inject_chart_block(markdown, block)`.
- `MAX_CHARTS_PER_BRIEFING = 5` cap.
- HTML escape: attribute values via `html.escape(quote=True)`; `data-history` additionally escapes `'` → `&#39;` and `</` → `<\/` so the single-quoted attribute cannot be broken out of by malicious source data.
- Decimal-as-string round-trip: server emits string fields, JS coerces with `parseFloat` — server-side precision survives.
- ID slug: `^GSPC` → `chart-GSPC`, `BTC-USD` → `chart-BTC-USD`, non-ASCII-alnum → `_`.
- `inject_chart_block` lands the block immediately after `## ⑤ 주요 종목` and is idempotent on FR-006 same-day re-publish.

### Step 4 — Orchestrator wiring

- `_load_market_anchors_for_run` signature widened to return `(anchors_by_segment, history_by_ticker)`. The same Yahoo Finance v8 fetch (u49) supplies both the brief-header anchor line and the chart placeholders — single network round-trip.
- New `_inject_chart_blocks_into_segments(segment_briefings, *, anchors_by_segment, history_by_ticker)` mutates each segment's `Briefing` via `model_copy(update={"rendered_markdown": ...})` after `_stage_prepare_segment_visual_assets`. Chart blocks land *on top of* the SVG cards (progressive enhancement preserved).
- Best-effort: any history fetch failure → empty `history_by_ticker` → no chart block for that segment, briefing still publishes.

### Step 5 — Tests + quality gate

- `tests/unit/publisher/test_chart_placeholder.py` — 16 tests: rendering shape, HTML escape (apostrophe + closing-tag), Decimal round-trip, ID slug, MAX cap, idempotent inject, empty-anchor skip, anchor-without-history skip, missing 52w fields graceful.
- `tests/unit/publisher/test_chart_assets.py` — 11 tests: bundle exists, bundle sha256 invariant, init script exists, LICENSE exists + first-line substring "Apache License", `mkdocs.yml` references both bundle + init in `extra_javascript`, built `site/assets/...` after `mkdocs build` contains all three.

| Gate | Result |
|------|--------|
| `ruff check .` | passed |
| `ruff format --check` | 253 files already formatted |
| `mypy --strict src/` | 101 source files, no issues |
| `pytest -x` | **1694 passed** (1667 → 1694, +27 tests) |
| `mkdocs build --strict` | exit 0; bundle + init + LICENSE all copied to `site/assets/`, both `<script>` tags injected into rendered HTML |

## Watchlist mapping — actual chart tickers per segment

Sourced from `_ANCHOR_SEGMENT_ROUTING` (u49); first 5 win after the cap:

- **us-equity**: `^GSPC`, `^IXIC`, `^DJI`, `AAPL`, `MSFT` (NVDA/GOOGL/AMZN/META/TSLA available, capped at 5).
- **crypto**: `BTC-USD`, `ETH-USD`.
- **domestic-equity**: 0 — same Yahoo coverage gap u49 documented as DEBT-D49-A. Chart block stays empty, markdown untouched.

## Plan deviations (intentional)

- **License is Apache-2.0, not MIT** — upstream relicensed. LICENSE.txt is byte-equal from upstream `v4.2.3` and pinned by sha256. Both licenses permit self-hosting.
- **`data-52w-high` rendered as absolute price**, not percentage — the chart needs price coordinates in the same units as the candlestick series; the percentages already exist on the anchor line.
- **`<noscript>` fallback message added inside the chart wrapper** (Korean, points to the SVG card above) for self-explanatory no-JS path.

## Files changed

- `mkdocs.yml` (modified — `extra_javascript`)
- `src/investo/publisher/charts.py` (new — pure helpers)
- `src/investo/orchestrator/pipeline.py` (modified — history fetch widened, chart-block injector)
- `site_docs/assets/lightweight-charts.standalone.production.js` (new vendor — 163,684 bytes)
- `site_docs/assets/lightweight-charts.LICENSE.txt` (new — Apache-2.0)
- `site_docs/assets/investo-chart-init.js` (new — 7,648 bytes)
- `tests/unit/publisher/test_chart_placeholder.py` (new — 16 tests)
- `tests/unit/publisher/test_chart_assets.py` (new — 11 tests)

## TECH-DEBT candidates (not filed)

- **D50-A (Low)**: `_decimal_to_float_str` emits `"108.0"` not `"108"` — cosmetic, payload size unaffected.
- **D50-B (Low)**: `MutationObserver` per chart has no `disconnect()`. mkdocs Material is multi-page (page reload covers cleanup). Revisit if `navigation.instant` is ever enabled.
- **D50-C (Low)**: Bundle bump procedure is manual (download → paste new sha256 → run suite). Plan suggested quarterly review — runbook entry candidate.

## Out of scope (per plan)

TradingView Charting Library full version, intraday / real-time tick, paid TradingView data API, drawing tools, Telegram chart embedding, sales-style "buy" overlays, user watchlist customization UI.
