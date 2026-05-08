# Code Generation Plan: `u42 quality-kpi-history`

**Date**: 2026-05-09
**Unit**: u42 quality-kpi-history
**Stage**: Code Generation
**Status**: 📋 Planned
**Source**: 10-persona evaluation 2026-05-09 — persona #9 (회의주의자) + persona #7 (첫 방문자)
**Estimated Effort**: ~3-4 h
**Dependencies**:
- Builds on `u32 trust-traceability-deep-dive` (`briefing/quality_eval.py` + `publisher/site_index.py::update_quality_page` + `site_docs/quality.md` already exist).
- Builds on `u31 operations-resilience` (`archive/_meta/coverage.jsonl` time series already appended each publish).
- Builds on `u24 visual-provenance-and-layout` (SVG render conventions, manifest sidecars).

---

## Goal

Replace the current `site_docs/quality.md` placeholder ("지난 7일 측정 가능한 게시 없음") with a 30-day rolling KPI history that includes a deterministic SVG sparkline. Every publish appends one quality-snapshot line to a new append-only time series at `archive/_meta/quality_history.jsonl`, and on each publish the quality page is re-rendered atomically with a 30-day sparkline + the current 7-day KPIs (already computed by u32). Persona #9 ("trust-but-verify") gets a single page proving that the briefing pipeline maintains its quality bar over time; persona #7 ("first-time visitor") gets a quick-glance signal that this is a real, ongoing project rather than a one-off.

---

## Persona evidence

> Persona #9 (회의주의자, P1): "site_docs/quality.md 가 '지난 7일 측정 가능한 게시 없음' 한 줄만 떠 있으면 신뢰성 검증 자체가 안 된다. 30일치 추세선 sparkline 정도는 자동으로 박혀 있어야 '아 이 사람들이 quality 지표를 정말 측정하고 있구나' 가 된다."

> Persona #7 (첫 방문자, P2): "site_docs/quality.md 라는 페이지가 메뉴에 있으면 일단 들어가 본다. 들어갔는데 한 줄짜리 placeholder 면 첫인상이 망함. 30일 추세선 + 현재 KPI 가 같이 보여야 한다."

---

## Definition of Done

- [ ] `archive/_meta/quality_history.jsonl` append-only time series exists and gets one new line per publish. Each line is a JSON object with: `date` (ISO-8601 KST date), `source_liveness` (float 0..1), `figures_presence` (float 0..1), `fallback_ratio` (float 0..1), `published_segments` (int 0..3), `total_items` (int), `total_failed_sources` (int).
- [ ] Append is **atomic** (write to `.tmp` + rename) and idempotent on same-day re-publish (re-publish overwrites the day's line — anti-regression test pinned).
- [ ] `briefing/quality_eval.py` (existing module from u32) gains a new `compute_quality_history(days: int = 30)` function that reads the JSONL, returns a list of daily KPI rows with missing-day gaps preserved (no synthetic interpolation).
- [ ] New module `visuals/quality_sparkline.py::render_quality_sparkline(rows: list[QualityHistoryRow]) -> bytes` produces a deterministic SVG (same input → byte-identical output) with three stacked mini-sparklines (source_liveness / figures_presence / fallback_ratio) covering 30 days. Empty / sparse history degrades gracefully with a `데이터 부족` placeholder. Sparkline embeds via `<style>` block matching u26's font / dark-mode contract.
- [ ] `publisher/site_index.py::update_quality_page` (existing from u32) gains the sparkline render path: the rewritten `site_docs/quality.md` includes the inline-SVG sparkline at the top, followed by the existing 7-day KPI table, followed by a new "최근 30일 추세" section.
- [ ] Quality page render is idempotent: re-running `update_quality_page` against the same `quality_history.jsonl` produces a byte-identical `site_docs/quality.md`.
- [ ] Orchestrator publish path threads the new `quality_history.jsonl` write atomically alongside the existing `coverage.jsonl` append (u31), `quality.md` rewrite (u32), and segment archive writes — all under one snapshot/rollback envelope (the u33 atomic-publish contract).
- [ ] Anti-regression: a regression test that pre-seeds `quality_history.jsonl` with 30 rows of varied KPIs and asserts the rendered `site_docs/quality.md` contains the sparkline SVG inline + a `최근 30일 추세` heading.
- [ ] Anti-regression: missing-day handling — pre-seed with 25 rows (5 gaps), assert sparkline rendering does not crash and visually represents gaps as broken segments rather than as zero values.
- [ ] Full quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅, `mkdocs build --strict` ✅.

---

## Steps

### Step 1 — `quality_history.jsonl` Append Path

- [ ] Create `briefing/quality_history.py::append_quality_snapshot(target_date, *, kpis, segments, total_items, total_failed_sources, history_path)` that atomically appends a JSON line to `archive/_meta/quality_history.jsonl`.
- [ ] Same-day re-publish: read existing lines, replace the line with `date == target_date` (or append if absent), atomic temp-file + rename.
- [ ] Files affected:
  - `src/investo/briefing/quality_history.py` (new)
- [ ] Unit tests at `tests/unit/briefing/test_quality_history.py`:
  - first-publish creates a new file with 1 line.
  - second-day publish appends → 2 lines.
  - same-day re-publish replaces → 2 lines (anti-regression on idempotence).
  - corrupt JSONL line → re-publish skips and appends; warning logged; no crash.
  - atomic-write: simulated write failure does not corrupt the existing file.

### Step 2 — `compute_quality_history` in `briefing/quality_eval.py`

- [ ] Extend `briefing/quality_eval.py` (existing module) with `compute_quality_history(days: int = 30, *, history_path) -> list[QualityHistoryRow]`.
- [ ] Returns rows in ascending date order; missing days preserved as `None` row entries (do not synthesize zeros).
- [ ] Files affected:
  - `src/investo/briefing/quality_eval.py`
  - `src/investo/briefing/__init__.py` (re-export `QualityHistoryRow`, `compute_quality_history`)
- [ ] Unit tests:
  - 30 days, all present → 30 rows.
  - 30 days, 5 gaps → 30 entries with 5 `None` rows.
  - empty file → empty list.
  - days=7 → at most 7 rows.

### Step 3 — Sparkline SVG Renderer

- [ ] Create `visuals/quality_sparkline.py::render_quality_sparkline(rows) -> bytes` producing deterministic SVG (3 stacked mini-sparklines: liveness, figures, fallback).
- [ ] SVG dimensions: 600 × 180. Each mini-sparkline 600 × 60. Y axis 0..1 fixed.
- [ ] Style: import the u26 `_CARD_STYLE` block (font-family Noto Sans KR / Arial / sans-serif, prefers-color-scheme dark-mode hooks, class names `card-bg` / `card-frame` / `card-title` / `card-text`).
- [ ] Missing days: render the sparkline as broken segments (don't connect points across a None gap).
- [ ] `VisualProvenanceManifest` sidecar (per u24): `source_type="generated_svg"`, `generator="investo.visuals.quality_sparkline"`, `version=_investo_version()`.
- [ ] Files affected:
  - `src/investo/visuals/quality_sparkline.py` (new)
- [ ] Unit tests at `tests/unit/visuals/test_quality_sparkline.py`:
  - 30-day full input → SVG bytes are deterministic (same input → byte-equal output).
  - empty input → `데이터 부족` placeholder SVG.
  - missing-day input → segments break correctly (regex check on `<polyline>` `points` attribute count).
  - SVG dimensions are 600 × 180.
  - manifest sidecar fields are populated correctly.

### Step 4 — `update_quality_page` Sparkline Integration

- [ ] Extend `publisher/site_index.py::update_quality_page` to: (1) call `compute_quality_history(30)`, (2) call `render_quality_sparkline(rows)`, (3) embed the SVG inline at the top of `site_docs/quality.md`, (4) keep the existing 7-day KPI table below, (5) add a new `## 최근 30일 추세` heading.
- [ ] The update is idempotent: re-rendering against the same JSONL produces byte-identical markdown.
- [ ] Files affected:
  - `src/investo/publisher/site_index.py`
- [ ] Unit tests at `tests/unit/publisher/test_quality_page.py` (extending the existing test file):
  - 30-day input → rendered markdown contains the sparkline SVG + the `최근 30일 추세` heading.
  - empty input → rendered markdown contains the `데이터 부족` placeholder + the existing 7-day fallback message.
  - re-render against same input → byte-identical markdown (idempotence).

### Step 5 — Orchestrator Wire-Through (Append + Rewrite, Atomic)

- [ ] In `orchestrator/pipeline.py::_stage_publish_segments`, after the existing `coverage.jsonl` append (u31) and `quality.md` rewrite (u32) calls, also call `append_quality_snapshot(target_date, ...)`.
- [ ] Snapshot the existing `quality_history.jsonl` before the append so the existing snapshot/rollback envelope (u33) covers it.
- [ ] Files affected:
  - `src/investo/orchestrator/pipeline.py`
- [ ] Unit tests:
  - successful publish appends one line to `quality_history.jsonl`.
  - publish failure (simulated mid-stage exception) rolls back the JSONL append.
  - dry-run mode skips the append (existing `INVESTO_DRY_RUN=1` invariant from u31).

### Step 6 — Verification

- [ ] Run targeted quality + visuals + publisher tests + the full quality gate.
- [ ] Manual: with a freshly seeded `quality_history.jsonl` of 30 days, render `site_docs/quality.md` locally, run `mkdocs serve`, confirm the sparkline renders in both light and dark mode (browser devtools color-scheme toggle) without layout reflow.

---

## Project rule compliance

- **Anthropic SDK ban**: not applicable.
- **Module boundary**: changes touch `briefing/`, `visuals/`, `publisher/`, `orchestrator/` — all already shared via the orchestrator entry; no new cross-module import beyond the existing patterns.
- **R10 (record/replay fixtures, no fabrication)**: not applicable — no new external HTTP source. The `quality_history.jsonl` is a derived in-repo artifact, not external data.
- **R13 (secret hygiene)**: not applicable — no new env var, no secret. The JSONL contains only numeric KPIs.
- **u24 visual-provenance contract**: respected — sparkline carries a `VisualProvenanceManifest` sidecar with `source_type="generated_svg"`.
- **u26 visual-delivery-integrity contract**: respected — sparkline reuses the `_CARD_STYLE` block + dark-mode hooks; same font-family chain.
- **Disclaimer enforcement**: not applicable to `site_docs/quality.md` (this is a meta page, not an archive briefing).

---

## Quality gate

- [ ] `uv run ruff check .` ✅
- [ ] `uv run ruff format --check .` ✅
- [ ] `uv run mypy --strict src/` ✅
- [ ] `uv run pytest -q` ✅ (expect ~20-25 new tests)
- [ ] `uv run mkdocs build --strict` ✅

---

## Out of scope

- **Per-segment KPI breakdown** — sparkline shows aggregate KPIs across all segments. Per-segment trends are a future enrichment if persona feedback demands it.
- **Interactive sparkline (hover-tooltip)** — SVG is static. Tooltips would require client-side JS, which the static-site contract avoids.
- **KPI alerting on regression** — no alert is fired when source liveness drops. The sparkline is a passive display surface; regression alerting belongs in u31's operator-chat path (and consecutive-fail detection already covers source failures).
- **Backfill of historical days** — `quality_history.jsonl` starts populating from the first publish after this unit lands. Historical backfill from `coverage.jsonl` + archive scan is a separate ops-time script.
- **Retention beyond 30 days** — the JSONL grows unboundedly; retention pruning is a future ops unit. At ~150 bytes/line × 365 days/year = ~55 KB/year, growth is negligible.

---

## Open questions

- **Sparkline aesthetic**: 3 stacked mini-sparklines vs. 1 combined sparkline with 3 colored series. Default to 3 stacked for clarity (each KPI has a distinct shape); revisit if persona #9 prefers compact.
- **Missing-day visual representation**: broken segments vs. dotted line. Default to broken segments (cleaner trust signal — "data is missing" is more honest than a dotted interpolation).
- **Determinism vs. cross-platform font rendering**: SVG bytes are deterministic; rendered pixel output may vary by browser font availability. The unit tests pin SVG bytes, not pixel output.
