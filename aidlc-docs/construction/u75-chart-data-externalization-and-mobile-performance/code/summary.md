# u75 chart-data-externalization-and-mobile-performance — Code Generation Summary

**Date**: 2026-05-24
**Unit**: u75 chart-data-externalization-and-mobile-performance
**Status**: Complete (5/5 steps)

## Goal

Keep the compact chart card visually small *and* shrink the HTML payload. The compact-card change solved the visual-prominence problem but each placeholder still embedded large inline OHLC history JSON (`data-history`), so the reader paid the payload cost before interacting — costly on mobile. u75 externalizes heavy chart history into deterministic archive-local sidecar JSON files and lazy-loads them only when the user expands a chart. Compact cards now render ticker/price/change with no history fetch.

## Scope

In scope: sidecar JSON generation/staging next to segment assets; placeholder schema change from inline `data-history` to a `data-history-src` relative path; lazy fetch on explicit expand in `investo-chart-init.js`; per-card loading/error state; payload-size regression tests.
Out of scope: new chart provider; CDN or server endpoint; full candlestick chart redesign; replacing lightweight-charts; historical archive backfill of pre-existing committed briefings.

## Stage Decision

- **Functional Design — SKIP** (per plan). This is an asset-packaging and client-loading refactor over existing chart artifacts (u50). No new shared domain model is introduced — `chart_sidecar` is a publisher-internal contract over already-built chart data. Confirmed at closeout — no FD file created.
- **NFR Requirements — SKIP** (per plan). No new dependency or external service. Performance improves by reducing the initial payload; the sidecar fetch is a same-origin relative read of a statically-staged file (GitHub Pages compatible). Cost remains zero. Confirmed at closeout — no NFR file created.

## Deduplication / Non-Overlap (extends u50, preserves the compact card)

u75 changes **payload ownership and lazy loading only** — it does not redesign the chart.

- **u50 consumed as-is**: lightweight-charts embedding and chart placeholder helpers stay. The expanded candlestick chart, ATH / 52w price-line overlays, dark/light `MutationObserver` theme behavior, and the self-hosted bundled lightweight-charts (no CDN) are unchanged.
- **u70 label registry preserved**: `data-label` (e.g. `^IXIC` → "나스닥 종합") still emitted on the placeholder.
- **Compact card UI invariant**: `details`/`summary`, `data-close` / `data-pct` compact summary attributes, and the expand-on-click candlestick are unchanged. Only the data source for the expanded history moved from inline to sidecar.

## Key Deliverables

- **New** `src/investo/publisher/chart_sidecar.py`: the sidecar contract.
  - `chart_id` = `{segment}-{normalized_ticker}`, lowercased, non-`[a-z0-9]` runs collapsed to `-`.
  - Path = `{segment_archive_stem}.assets/charts/{chart_id}.json`, relative to the segment markdown (e.g. `2026-05-24.assets/charts/us-equity-aapl.json`).
  - `to_json_bytes()` — `schema_version` fixed `1`, stable key order, compact separators, Decimal values serialized as strings, `history` sorted ascending by date, `provenance.run_date` = the target date (no wall-clock timestamp → deterministic byte output).
  - `write_chart_sidecar()` — atomic (tmp + `os.replace`) and idempotent.
- **Changed** `src/investo/publisher/charts.py`: `build_chart_artifacts()` now returns `ChartArtifacts(block, sidecars)`; `render_chart_placeholder` emits `data-history-src` instead of inline `data-history`; `_serialize_history` / `_data_history_attr` removed; duplicate `chart_id` collisions disambiguated with `-{ordinal}` in source order.
- **Changed** `site_docs/assets/investo-chart-init.js`: compact cards render from summary attrs only (no inline history, no prefetch sparkline); `loadSidecarBars(src)` lazy-fetches **inside the toggle handler only** (no viewport prefetch); per-card loading/error states in Korean; dead sparkline / `safeParse` paths removed.
- **Changed** `src/investo/publisher/briefing_replay.py`: `_check_chart_sidecars` reports a `chart-sidecar-missing` **warning** when `data-history-src` is unresolved — the compact card still renders (graceful degradation, not a publish-blocking failure).
- **Changed** `src/investo/orchestrator/pipeline.py`: `_inject_chart_blocks_into_segments` now takes `target_date`, writes the sidecars, and returns `(briefings, sidecar_paths)`; the call site merges sidecar paths into `visual_asset_paths` so they are snapshotted / staged / committed alongside the segment markdown.
- **Tests**: new `tests/unit/publisher/test_chart_sidecar.py`; updated `test_chart_placeholder.py` / `test_chart_assets.py` / `test_briefing_replay.py` / `test_run_pipeline.py`.

## Sidecar Contract

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | int | fixed `1` |
| `chart_id` | string | `{segment}-{normalized_ticker}`, deterministic |
| `ticker` | string | original ticker |
| `label` | string | display label (u70 registry) |
| `summary` | object | `close`, optional `pct` / `ath` / `high_52w` / `low_52w` (strings) |
| `history` | array | rows `{t,o,h,l,c,v}` sorted ascending by date; numbers as strings; `v` string\|null |
| `provenance` | object | deterministic `source` + `run_date` (target date, no wall clock) |

JSON uses compact separators and stable key order → byte-deterministic for idempotent reruns and fixture replay.

## Lazy-Load Design

- Compact card renders with `data-close` / `data-pct` only — **no** sidecar fetch on render, **no** viewport prefetch in v1.
- `loadSidecarBars(src)` runs only when the user explicitly expands (click / keyboard activation of the `details` control).
- A failed fetch shows a per-card Korean error state and does not break sibling chart cards.
- Theme (`MutationObserver`) and ATH / 52w price-line overlays unchanged on the expanded chart.

## Payload Reduction (252-row AAPL fixture)

- Per-card inline `div` is now ~102 B (was 7–15 KB with inline `data-history`).
- A one-card block is 575 B; the ~18 KB history moves to the lazily-fetched sidecar.

## AC Traceability

| AC | Statement | Status | Evidence |
|----|-----------|--------|----------|
| AC-75.1 | Full OHLC history not embedded inline in segment markdown/HTML | MET | `render_chart_placeholder` emits `data-history-src`; `_serialize_history`/`_data_history_attr` removed; payload test asserts no `data-history` / no serialized OHLC row arrays |
| AC-75.2 | Archive-local sidecar JSON deterministic, staged with the briefing, GitHub Pages compatible | MET | `chart_sidecar.to_json_bytes()` stable-order/compact/no-wall-clock; orchestrator merges sidecar paths into `visual_asset_paths`; staging fixture in `test_run_pipeline.py` |
| AC-75.3 | Compact cards render ticker/price/change without fetching the sidecar | MET | JS renders compact card from summary attrs only; no fetch before expand (static check) |
| AC-75.4 | Expanded charts lazy-load only on explicit expand and degrade per-card on failure | MET | `loadSidecarBars` inside toggle handler; per-card Korean loading/error state; `briefing_replay` `chart-sidecar-missing` warning keeps compact card rendering |
| AC-75.5 | Existing chart visual semantics and bundled chart library unchanged | MET | compact card UI / candlestick / ATH-52w price-line / theme observer / bundled lightweight-charts untouched; u70 `data-label` preserved |

## FD Divergences Ratified

None. FD was SKIP (asset-packaging / client-loading refactor over existing u50 chart artifacts; no new entity). No code-vs-spec divergence to ratify.

## TECH-DEBT Registered

- **DEBT-077** (Low) — pre-existing committed `archive/` briefings still carry the old inline `data-history`; without a sidecar they are now non-expandable (the JS hides a `details` whose `data-history-src` is absent). Backfill is out of scope. Additive fix = a one-shot regeneration / migration pass that emits sidecars for historical archive charts.
- **DEBT-078** (Low) — the compact-card pre-fetch sparkline was removed (it required the now-externalized inline history). Re-introducing a tiny `data-spark` polyline is a product decision, currently unimplemented.

## Potential Risks

- **Legacy archive non-expandable** (DEBT-077): older committed briefings with inline `data-history` have no sidecar, so the expand control is hidden for them. Compact summary still renders; new briefings are unaffected. Backfill deferred.
- **Compact sparkline removed** (DEBT-078): the small line sparkline on the compact card is gone because it depended on inline history. Cards still show ticker/price/change. Re-adding a `data-spark` polyline is a product call.

## Verification Gate

- ruff check: clean
- ruff-format: clean
- mypy --strict: 144 files clean
- `node --check site_docs/assets/investo-chart-init.js`: ok
- mkdocs build --strict: pass
- pytest: 2628 passed

## Project Rules Upheld

무료 API only (no external call; deterministic render + same-origin relative static fetch, no server), Anthropic SDK 금지 (untouched), 모듈 경계 (`chart_sidecar` imports only `briefing.market_anchor`; charts/briefing_replay publisher-internal; orchestrator-only cross-unit import preserved), 면책조항 + 채널 분리 gates untouched, R13 no secret (sidecar carries no `raw_metadata` / secret — pinned by test), static-site compatibility (relative same-origin fetch, no server endpoint), `defusedxml` not invoked. No new data source / numeric-verification rule / dependency.
